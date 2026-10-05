#!/usr/bin/env python3
"""
Zbiera fakty z jednego hosta przez pyinfra (SSH) i zapisuje je do
hosts/<nazwa>/facts.yaml. Wyłącznie ODCZYT: niczego nie zmienia na hoście.

Przykłady:
    python tools/collect_facts.py nas-vm                       # dane połączenia z hosts/nas-vm/host.yaml
    python tools/collect_facts.py proxmox-brat --target 100.64.0.12 --user root
    python tools/collect_facts.py nas-vm --sudo                # więcej szczegółów (ss -p, docker)
                                                               # gdy sudo wymaga hasła, pyinfra zapyta
                                                               # o nie w terminalu (uruchamia użytkownik)
    python tools/collect_facts.py laptop --target @local       # test lokalny
    python tools/collect_facts.py --all                        # odśwież wszystkie hosty

Jeśli istnieje hosts/<nazwa>/host.yaml, ssh_host/ssh_user/ssh_port/sudo są
brane stamtąd (argumenty z CLI mają pierwszeństwo).

Wynik facts.yaml jest przeznaczony do commita, dlatego:
  - zmienne środowiskowe kontenerów NIE są zapisywane (tylko ich nazwy),
  - nie zbieramy listy procesów (argumenty często zawierają hasła),
  - wszystkie stringi przechodzą przez redact() (hasła/tokeny w URL-ach, key=value).
Mimo to przejrzyj diff przed commitem.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import re
import sys
from pathlib import Path

import yaml

try:
    import pyinfra
    from pyinfra.api import Config, Inventory, State
    from pyinfra.api.connect import connect_all, disconnect_all
    from pyinfra.api.exceptions import PyinfraError
    from pyinfra.api.facts import get_facts
    from pyinfra.facts import docker, hardware, server, systemd
except ImportError:
    sys.exit("Brak pyinfra. Zainstaluj: pip install -r requirements.txt")

# Windows: konsola bywa w cp1250, a drukujemy polskie znaki
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
HOSTS_DIR = REPO / "hosts"

# Programy, których obecność mówi coś o roli maszyny.
INTERESTING_BINARIES = [
    "docker", "podman", "nginx", "caddy", "traefik", "apache2", "httpd",
    "psql", "postgres", "mysql", "mariadb", "redis-server", "mongod",
    "tailscale", "wg", "sops", "age", "git", "python3", "node",
    "restic", "borg", "rclone", "zfs", "pct", "qm", "pveversion",
    "ha", "synopkg", "nvidia-smi", "ollama", "certbot", "ufw", "fail2ban",
]

# Polecenia tylko do odczytu. Klucz = nazwa w facts.yaml.
# "sudo": True -> uruchamiane z sudo tylko przy --sudo.
READONLY_COMMANDS = {
    # DSM i busybox nie mają ss -> fallback na netstat (bez nagłówków)
    "listening_ports": {"cmd": "ss -tulnH 2>/dev/null || netstat -tuln 2>/dev/null | tail -n +3",
                        "sudo_cmd": "ss -tulnpH 2>/dev/null || netstat -tulnp 2>/dev/null | tail -n +3",
                        "sudo": True},
    # fallbacki, gdy fakty pyinfra Cpus/Memory zwrócą None (brak nproc/free)
    "cpu_fallback": {"cmd": "grep -c ^processor /proc/cpuinfo 2>/dev/null; grep -m1 'model name' /proc/cpuinfo 2>/dev/null"},
    "memory_fallback": {"cmd": "grep -E '^(MemTotal|MemAvailable|SwapTotal)' /proc/meminfo 2>/dev/null"},
    "disk_usage": {"cmd": "df -hT -x tmpfs -x devtmpfs -x overlay -x squashfs 2>/dev/null"},
    "running_services": {"cmd": "systemctl list-units --type=service --state=running --no-legend --plain 2>/dev/null"},
    "failed_services": {"cmd": "systemctl list-units --state=failed --no-legend --plain 2>/dev/null"},
    "timers": {"cmd": "systemctl list-timers --all --no-legend --plain 2>/dev/null"},
    "user_crontab": {"cmd": "crontab -l 2>/dev/null"},
    "cron_d": {"cmd": "ls -1 /etc/cron.d 2>/dev/null"},
    "compose_projects": {"cmd": "docker compose ls --all --format json 2>/dev/null", "sudo": True},
    "docker_volumes": {"cmd": "docker volume ls --format '{{.Name}}' 2>/dev/null", "sudo": True},
    "docker_networks": {"cmd": "docker network ls --format '{{.Name}} {{.Driver}}' 2>/dev/null", "sudo": True},
    "nginx_sites": {"cmd": "ls -1 /etc/nginx/sites-enabled /etc/nginx/conf.d 2>/dev/null"},
    "caddyfile_exists": {"cmd": "test -f /etc/caddy/Caddyfile && echo yes || echo no"},
    "apt_upgradable": {"cmd": "apt list --upgradable 2>/dev/null | tail -n +2 | wc -l"},
    "tailscale_ip": {"cmd": "tailscale ip -4 2>/dev/null || /var/packages/Tailscale/target/bin/tailscale ip -4 2>/dev/null"},
    # plik bywa czytelny tylko dla roota (DSM) - z --sudo zadziała
    "nginx_reverse_proxy": {"sudo": True, "cmd": r"""f=/etc/nginx/sites-enabled/server.ReverseProxy.conf; [ -e "$f" ] && wc -c < "$(readlink -f "$f")" | sed 's/^/bytes: /'; grep -hE '^\s*(server_name|listen|proxy_pass)' "$f" 2>/dev/null"""},
    "docker_socket": {"cmd": "ls -l /var/run/docker.sock 2>/dev/null"},
    "proxmox_version": {"cmd": "pveversion 2>/dev/null"},
    "proxmox_vms": {"cmd": "qm list 2>/dev/null", "sudo": True},
    "proxmox_containers": {"cmd": "pct list 2>/dev/null", "sudo": True},
    "gpu": {"cmd": "nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null || lspci 2>/dev/null | grep -iE 'vga|3d' || true"},
    "synology_dsm": {"cmd": "cat /etc.defaults/VERSION 2>/dev/null"},
    "synology_packages": {"cmd": "/usr/syno/bin/synopkg list --name 2>/dev/null"},
    # DSM trzyma strefę jako nazwę miasta z własnej listy (np. "Sarajevo" = wpis "Sarajevo, Skopje,
    # Warsaw, Zagreb"); fakt pyinfra Timezone pokazuje tylko cel symlinku /etc/localtime
    "synology_timezone": {"cmd": "grep -E '^timezone=' /etc/synoinfo.conf 2>/dev/null"},
    # tylko root: czy wbudowane konto admin jest wyłączone ("Expired: [true]" = wyłączone)
    "synology_admin_account": {"sudo": True, "cmd": "/usr/syno/sbin/synouser --get admin 2>/dev/null | grep -iE 'expired|user name'"},
    # udziały na wolumenach (katalogi @... to wewnętrzne DSM)
    "synology_shares": {"cmd": "for v in /volume[0-9]*; do [ -d \"$v\" ] && echo \"$v:\" && ls -1 \"$v\" 2>/dev/null | grep -v '^@'; done"},
    "home_assistant": {"cmd": "ha core info 2>/dev/null | head -20"},
}

FS_SKIP = {"tmpfs", "devtmpfs", "overlay", "squashfs", "proc", "sysfs", "cgroup", "cgroup2",
           "devpts", "mqueue", "debugfs", "tracefs", "securityfs", "pstore", "bpf",
           "configfs", "fusectl", "hugetlbfs", "autofs", "binfmt_misc", "nsfs", "efivarfs"}

# --- redakcja sekretów --------------------------------------------------------

_REDACTIONS = [
    # nagłówki Bearer (przed regułą key=value, żeby złapać sam token)
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{8,}"), r"\1<REDACTED>"),
    # user:haslo@ w URL-ach
    (re.compile(r"(\w+://[^:/\s]+:)[^@\s]+(@)"), r"\1<REDACTED>\2"),
    # klucz=wartosc / klucz: wartosc dla podejrzanych kluczy
    (re.compile(r"(?i)\b([\w.-]*(?:pass(?:word|wd)?|secret|token|api[_-]?key|auth|credential|private[_-]?key)[\w.-]*)\s*([=:])\s*(\"[^\"]*\"|'[^']*'|\S+)"),
     r"\1\2<REDACTED>"),
]


def redact(value):
    if isinstance(value, str):
        for pattern, repl in _REDACTIONS:
            value = pattern.sub(repl, value)
        return value
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [redact(v) for v in value]
    return value


def to_plain(value):
    """Zamienia typy pyinfra/pythona na coś, co yaml.safe_dump przyjmie."""
    if isinstance(value, dict):
        return {str(k): to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [to_plain(v) for v in value]
        return sorted(items, key=str) if isinstance(value, (set, frozenset)) else items
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def lines(output: str | None) -> list[str]:
    if not output:
        return []
    return [line.rstrip() for line in output.splitlines() if line.strip()]


# --- połączenie ---------------------------------------------------------------

def load_host_yaml(name: str) -> dict:
    path = HOSTS_DIR / name / "host.yaml"
    if path.exists():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {}


def connect(target: str, user: str | None, port: int | None, timeout: int,
            temp_dir: str | None = None):
    host_data = {}
    if user:
        host_data["ssh_user"] = user
    if port:
        host_data["ssh_port"] = port

    inventory = Inventory(([(target, host_data)], {}))
    # TEMP_DIR: pyinfra trzyma tam m.in. skrypt askpass dla sudo z hasłem; na Synology DSM
    # /tmp jest noexec, więc host.yaml może wskazać inny katalog (np. katalog domowy).
    config = Config(CONNECT_TIMEOUT=timeout, TEMP_DIR=temp_dir)
    state = State(inventory, config)
    try:
        connect_all(state)
        active = list(state.inventory.get_active_hosts())
    except PyinfraError:
        active = []
    if not active:
        raise SystemExit(
            f"Nie udało się połączyć z {target}. Sprawdź: ssh -o BatchMode=yes {target} true\n"
            "(klucz SSH w agencie? wpis w ~/.ssh/config? Tailscale włączony?)"
        )
    return state, active[0]


# --- zbieranie ----------------------------------------------------------------

class Collector:
    def __init__(self, state, host, use_sudo: bool):
        self.state = state
        self.host = host
        self.use_sudo = use_sudo
        self.errors: dict[str, str] = {}

    def fact(self, label: str, cls, sudo: bool = False, record_missing: bool = True, **kwargs):
        if sudo and self.use_sudo:
            kwargs["_sudo"] = True
        try:
            result = get_facts(self.state, cls, kwargs=kwargs or None, apply_failed_hosts=False)
            value = result.get(self.host)
            if value is None and record_missing and not label.startswith("which:"):
                self.errors[label] = "brak danych (fakt nieobsługiwany albo brak uprawnień)"
            return value
        except (PyinfraError, Exception) as exc:  # fakty bywają kruche na DSM/HAOS
            self.errors[label] = f"{type(exc).__name__}: {exc}"[:300]
            return None

    def docker_inspect(self, docker_bin: str):
        """`docker inspect` wszystkich kontenerów (także zatrzymanych) jako dict name->info,
        w formacie zgodnym z faktem pyinfra DockerContainers. None = brak danych."""
        if not self.use_sudo:
            self.errors["docker_containers"] = "brak danych (wymaga sudo)"
            return None
        cmd = f"ids=$({docker_bin} ps -aq 2>/dev/null); [ -z \"$ids\" ] && echo '[]' || {docker_bin} inspect $ids"
        out = self.fact("docker_containers", server.Command, sudo=True, record_missing=False, command=cmd)
        if out is None:
            self.errors["docker_containers"] = "brak danych (docker inspect nie zwrócił wyniku)"
            return None
        try:
            items = json.loads(out)
        except json.JSONDecodeError as exc:
            self.errors["docker_containers"] = f"nieparsowalny JSON z docker inspect: {exc}"[:200]
            return None
        return {item.get("Name", "?"): item for item in items}

    def command(self, label: str, spec: dict):
        cmd = spec["cmd"]
        sudo = spec.get("sudo", False) and self.use_sudo
        if sudo and "sudo_cmd" in spec:
            cmd = spec["sudo_cmd"]
        # "|| true": brak programu / pusty wynik to normalna sytuacja, nie błąd
        out = self.fact(label, server.Command, sudo=sudo, record_missing=False,
                        command=f"{{ {cmd} ; }} || true")
        return lines(out)


def slim_distribution(dist):
    if not dist:
        return dist
    meta = dist.get("release_meta") or {}
    return {
        "name": dist.get("name"),
        "major": dist.get("major"),
        "minor": dist.get("minor"),
        "pretty_name": meta.get("PRETTY_NAME"),
        "id": meta.get("ID"),
        "id_like": meta.get("ID_LIKE"),
        "version_id": meta.get("VERSION_ID"),
    }


def summarize_containers(raw) -> list[dict]:
    """Z pełnego `docker inspect` zostawia tylko to, co potrzebne do adopcji. Bez Env!"""
    result = []
    for name, info in (raw or {}).items():
        cfg = info.get("Config", {}) or {}
        hcfg = info.get("HostConfig", {}) or {}
        labels = cfg.get("Labels") or {}
        result.append({
            "name": name.lstrip("/"),
            "image": cfg.get("Image"),
            "state": (info.get("State") or {}).get("Status"),
            "restart_policy": (hcfg.get("RestartPolicy") or {}).get("Name"),
            "ports": sorted({
                f"{b.get('HostIp') or '0.0.0.0'}:{b.get('HostPort')}->{p}"
                for p, binds in (hcfg.get("PortBindings") or {}).items()
                for b in (binds or [])
            }),
            "mounts": [
                f"{m.get('Source') or m.get('Name')}:{m.get('Destination')}"
                for m in (info.get("Mounts") or [])
            ],
            "networks": sorted((info.get("NetworkSettings") or {}).get("Networks", {}).keys()),
            "env_var_names": sorted({e.split("=", 1)[0] for e in (cfg.get("Env") or [])}),
            "compose_project": labels.get("com.docker.compose.project"),
            "compose_file": labels.get("com.docker.compose.project.config_files"),
            "compose_workdir": labels.get("com.docker.compose.project.working_dir"),
        })
    return sorted(result, key=lambda c: c["name"])


def collect(state, host, use_sudo: bool) -> dict:
    c = Collector(state, host, use_sudo)

    mounts = c.fact("mounts", server.Mounts) or {}
    users = c.fact("users", server.Users) or {}
    netdevs = c.fact("network_devices", hardware.NetworkDevices) or {}
    systemd_status = c.fact("systemd_status", systemd.SystemdStatus) or {}

    data = {
        "system": {
            "hostname": c.fact("hostname", server.Hostname),
            "os": c.fact("os", server.Os),
            "distribution": slim_distribution(c.fact("distribution", server.LinuxDistribution)),
            "kernel": c.fact("kernel_version", server.KernelVersion),
            "arch": c.fact("arch", server.Arch),
            "uptime_seconds": c.fact("uptime", server.Uptime),
            "timezone": c.fact("timezone", server.Timezone),
            "load_average": c.fact("load_average", server.LoadAverage),
            "reboot_required": c.fact("reboot_required", server.RebootRequired),
        },
        "hardware": {
            "cpus": c.fact("cpus", hardware.Cpus, record_missing=False),
            "memory_mb": c.fact("memory", hardware.Memory, record_missing=False),
            "block_devices": {
                dev: info for dev, info in (c.fact("block_devices", hardware.BlockDevices) or {}).items()
                if dev.startswith("/dev/")
            },
            "gpu": c.command("gpu", READONLY_COMMANDS["gpu"]),
        },
        "network": {
            "ipv4": c.fact("ipv4", hardware.Ipv4Addrs),
            "devices": sorted(
                n for n in netdevs
                if not n.startswith(("veth", "br-", "docker", "lo", "fwbr", "fwln", "fwpr", "tap"))
            ),
            "tailscale_ip": c.command("tailscale_ip", READONLY_COMMANDS["tailscale_ip"]),
            "listening_ports": c.command("listening_ports", READONLY_COMMANDS["listening_ports"]),
        },
        "storage": {
            "mounts": {
                path: {"device": m.get("device"), "type": m.get("type")}
                for path, m in mounts.items()
                if m.get("type") not in FS_SKIP and not path.startswith(("/proc", "/sys", "/run", "/dev"))
            },
            "disk_usage": c.command("disk_usage", READONLY_COMMANDS["disk_usage"]),
        },
        "binaries": {
            b: path for b in INTERESTING_BINARIES
            if (path := c.fact(f"which:{b}", server.Which, command=b))
        },
        "services": {
            "systemd_enabled_or_running": sorted(k for k, v in systemd_status.items() if v),
            "running": c.command("running_services", READONLY_COMMANDS["running_services"]),
            "failed": c.command("failed_services", READONLY_COMMANDS["failed_services"]),
            "timers": c.command("timers", READONLY_COMMANDS["timers"]),
            "user_crontab": c.command("user_crontab", READONLY_COMMANDS["user_crontab"]),
            "cron_d": c.command("cron_d", READONLY_COMMANDS["cron_d"]),
        },
        "users": {
            name: {"home": u.get("home"), "shell": u.get("shell"), "groups": u.get("groups")}
            for name, u in users.items()
            if (u.get("uid") or 0) >= 1000 or name == "root"
            if not str(u.get("shell", "")).endswith(("nologin", "false"))
        },
        "updates": {"apt_upgradable": c.command("apt_upgradable", READONLY_COMMANDS["apt_upgradable"])},
    }

    if data["hardware"]["cpus"] is None:
        data["hardware"]["cpu_fallback"] = c.command("cpu_fallback", READONLY_COMMANDS["cpu_fallback"])
    if data["hardware"]["memory_mb"] is None:
        data["hardware"]["memory_fallback"] = c.command("memory_fallback", READONLY_COMMANDS["memory_fallback"])

    # Synology Container Manager trzyma docker poza PATH
    if "docker" not in data["binaries"]:
        dsm_docker = "/var/packages/ContainerManager/target/usr/bin/docker"
        if c.command("docker_dsm_bin", {"cmd": f"test -x {dsm_docker} && echo {dsm_docker}"}):
            data["binaries"]["docker"] = dsm_docker

    if "docker" in data["binaries"]:
        dbin = data["binaries"]["docker"]
        if dbin == "docker":
            containers = c.fact("docker_containers", docker.DockerContainers, sudo=True)
        else:
            # binarka poza PATH (Synology): fakt pyinfra woła gołe `docker`, więc inspect ręcznie
            containers = c.docker_inspect(dbin)

        def dcmd(label):
            spec = dict(READONLY_COMMANDS[label])
            spec["cmd"] = spec["cmd"].replace("docker ", f"{dbin} ", 1)
            return c.command(label, spec)

        data["docker"] = {
            # None = brak danych (zwykle brak sudo), [] = naprawdę zero kontenerów
            "containers": summarize_containers(containers) if containers is not None else None,
            "compose_projects": dcmd("compose_projects"),
            "volumes": dcmd("docker_volumes"),
            "networks": dcmd("docker_networks"),
            "socket": c.command("docker_socket", READONLY_COMMANDS["docker_socket"]),
        }

    web = {
        "nginx_sites": c.command("nginx_sites", READONLY_COMMANDS["nginx_sites"]),
        "caddyfile": c.command("caddyfile_exists", READONLY_COMMANDS["caddyfile_exists"]),
    }
    if rp := c.command("nginx_reverse_proxy", READONLY_COMMANDS["nginx_reverse_proxy"]):
        web["nginx_reverse_proxy"] = rp
    data["web"] = web

    platform = {}
    for key in ("proxmox_version", "proxmox_vms", "proxmox_containers",
                "synology_dsm", "synology_packages", "synology_shares",
                "synology_timezone", "synology_admin_account", "home_assistant"):
        out = c.command(key, READONLY_COMMANDS[key])
        if out:
            platform[key] = out
    if platform:
        data["platform"] = platform

    data["_meta"] = {
        "collected_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "pyinfra_version": pyinfra.__version__,
        "sudo_used": use_sudo,
        "errors": c.errors,
    }
    return redact(to_plain(data))


# Sekcje, które bez sudo są puste/None, a z sudo mają wartość. Przy zwykłym odświeżeniu
# przepisujemy je z poprzedniego facts.yaml, żeby nie kasować przebiegu użytkownika z --sudo.
SUDO_ONLY_PATHS = [
    ("docker",),
    ("network", "listening_ports"),
    ("web", "nginx_reverse_proxy"),
    ("platform", "synology_admin_account"),
]


def _get(d, path):
    for k in path:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def _set(d, path, value):
    for k in path[:-1]:
        d = d.setdefault(k, {})
    d[path[-1]] = value


def preserve_sudo_facts(facts: dict, previous_file: Path) -> None:
    """Gdy poprzedni plik powstał z --sudo, zachowaj z niego sekcje sudo-only i zaznacz to w _meta."""
    if not previous_file.exists():
        return
    try:
        prev = yaml.safe_load(previous_file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return
    prev_meta = prev.get("_meta") or {}
    # źródłem może być przebieg z --sudo albo plik, który sam już zachował takie sekcje
    source_ts = prev_meta.get("collected_at") if prev_meta.get("sudo_used")         else prev_meta.get("sudo_facts_preserved_from")
    if not source_ts:
        return
    kept = []
    for path in SUDO_ONLY_PATHS:
        old = _get(prev, path)
        if old in (None, [], {}):
            continue
        _set(facts, path, old)
        kept.append(".".join(path))
    if kept:
        facts["_meta"]["sudo_facts_preserved_from"] = source_ts
        facts["_meta"]["sudo_facts_preserved"] = kept
        facts["_meta"]["errors"].pop("docker_containers", None)


def run_one(name: str, target: str | None, args) -> bool:
    host_cfg = load_host_yaml(name)
    if host_cfg.get("disabled") and not target:
        print(f"Pomijam {name} (disabled: true w host.yaml)")
        return True
    target = target or host_cfg.get("ssh_host") or name
    user = args.user or host_cfg.get("ssh_user")
    port = args.port or host_cfg.get("ssh_port")
    use_sudo = args.sudo or bool(host_cfg.get("sudo", False))
    temp_dir = host_cfg.get("temp_dir")

    try:
        state, host = connect(target, user, port, args.timeout, temp_dir=temp_dir)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return False
    try:
        facts = collect(state, host, use_sudo)
        if not use_sudo:
            preserve_sudo_facts(facts, HOSTS_DIR / name / "facts.yaml")
    finally:
        disconnect_all(state)

    facts["_meta"]["target"] = target
    output = yaml.safe_dump(facts, sort_keys=False, allow_unicode=True, width=120)

    if args.stdout:
        print(output)
        return True

    out_dir = HOSTS_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "facts.yaml").write_text(output, encoding="utf-8")

    errs = facts["_meta"]["errors"]
    sysinfo = facts["system"]
    dist = sysinfo.get("distribution") or {}
    print(f"Zapisano {out_dir.relative_to(REPO)}/facts.yaml")
    print(f"  host: {sysinfo.get('hostname')} | os: {dist.get('name')} {dist.get('version_id') or ''} "
          f"| arch: {sysinfo.get('arch')}")
    if "docker" in facts:
        containers = facts["docker"]["containers"]
        print("  kontenery: " + ("brak danych (sudo?)" if containers is None else str(len(containers))))
    if facts["_meta"].get("sudo_facts_preserved_from"):
        print(f"  sekcje sudo-only zachowane z przebiegu {facts['_meta']['sudo_facts_preserved_from']}: "
              + ", ".join(facts["_meta"]["sudo_facts_preserved"]))
    print(f"  brakujące fakty: {len(errs)}" + (f" ({', '.join(list(errs)[:8])})" if errs else ""))
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("name", nargs="?", help="nazwa hosta (katalog w hosts/) albo adres, gdy hosta jeszcze nie ma")
    p.add_argument("--target", help="adres SSH, jeśli inny niż nazwa i brak host.yaml (alias, MagicDNS, IP, @local)")
    p.add_argument("--all", action="store_true", help="odśwież fakty wszystkich hostów z hosts/*/host.yaml")
    p.add_argument("--user", help="użytkownik SSH")
    p.add_argument("--port", type=int, help="port SSH")
    p.add_argument("--sudo", action="store_true",
                   help="użyj sudo dla bogatszych faktów; gdy sudo wymaga hasła, pyinfra zapyta w terminalu")
    p.add_argument("--timeout", type=int, default=10)
    p.add_argument("--stdout", action="store_true", help="wypisz YAML zamiast zapisywać plik")
    p.add_argument("-v", "--verbose", action="store_true", help="pokaż logi pyinfra")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.CRITICAL, format="%(message)s")
    logging.getLogger("pyinfra").setLevel(logging.INFO if args.verbose else logging.CRITICAL)

    if args.all:
        names = sorted(f.parent.name for f in HOSTS_DIR.glob("*/host.yaml"))
        results = {n: run_one(n, None, args) for n in names}
        failed = [n for n, ok in results.items() if not ok]
        sys.exit(f"Nieudane: {', '.join(failed)}" if failed else 0)

    if not args.name:
        p.error("podaj nazwę hosta albo --all")
    ok = run_one(args.name, args.target, args)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
