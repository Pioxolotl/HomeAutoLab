"""
Generyczny deploy stacków docker compose dla hosta z inventory.

Dla hosta `inventory_name` wdraża każdy katalog hosts/<host>/services/<stack>/ zawierający
compose.yaml. Zero kodu per stack: wszystko, co stack może nadpisać, siedzi w opcjonalnym
hosts/<host>/services/<stack>/stack.yaml (wzór: templates/stack/stack.yaml).

Co robi dla każdego stacka:
  1. katalog <remote_dir> (domyślnie <stacks_dir z host.yaml>/<stack>)
  2. compose.yaml 1:1 z repo
  3. dodatkowe pliki z `files:` w stack.yaml (configi montowane do kontenerów)
  4. .env z hosts/<host>/secrets/<stack>.sops.yaml (sops -d lokalnie; mode 600)
  5. `<compose_bin> up -d --remove-orphans` tylko, gdy coś z 2-4 się zmieniło

Uruchamianie (z katalogu repo):
  pyinfra inventory.py deploys/compose_stacks.py --limit <host> --dry --data no_secrets=true  # Claude: podgląd bez sops
  pyinfra inventory.py deploys/compose_stacks.py --limit <host> --dry                          # podgląd z .env
  pyinfra inventory.py deploys/compose_stacks.py --limit <host>                                # wdrożenie (człowiek)
  --data only=<stack>       wdraża jeden stack
  --data adopt_check=true   host w `observe`: pozwala na --dry (nigdy bez --dry)

Dane hosta używane tutaj (host.yaml): stacks_dir, docker_sudo, files_sudo, compose_bin, temp_dir, managed.

Sudo jest rozdzielone: `docker_sudo` dotyczy tylko `compose up` (Docker wymaga roota), a `files_sudo`
kopiowania plików (domyślnie False, bo katalog stacków zwykle jest zapisywalny dla użytkownika SSH).
Dzięki temu `--dry` nie dotyka sudo wcale: operacje shell nie zbierają faktów, więc pyinfra nie pyta
o hasło, a Claude może robić podgląd bez interakcji. Hasło pada dopiero przy prawdziwym wdrożeniu.
"""

import json
import subprocess
from io import StringIO
from pathlib import Path

import yaml
from pyinfra import config, host, logger
from pyinfra.operations import files, server

REPO = Path(__file__).resolve().parent.parent
NAME = host.data.get("inventory_name")
HOST_DIR = REPO / "hosts" / str(NAME)
STACKS_DIR = HOST_DIR / "services"
SECRETS_DIR = HOST_DIR / "secrets"

# Hosty z /tmp noexec (Synology DSM) wskazują w host.yaml katalog tymczasowy dla pyinfra.
if host.data.get("temp_dir"):
    config.TEMP_DIR = host.data.get("temp_dir")


def _truthy(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "tak"}


def _allowed() -> bool:
    if host.data.get("managed") == "managed":
        return True
    if _truthy(host.data.get("adopt_check")):
        logger.warning(f"{NAME}: host w trybie observe, adopt_check=true - używaj wyłącznie z --dry")
        return True
    logger.warning(f"{NAME}: host w trybie observe, pomijam wdrożenie stacków")
    return False


def _stack_config(stack_dir: Path) -> dict:
    cfg_file = stack_dir / "stack.yaml"
    if not cfg_file.exists():
        return {}
    return yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}


def _env_from_sops(secrets_file: Path) -> str:
    """Odszyfrowuje lokalnie (klucz age użytkownika) i buduje treść .env: KEY=value, alfabetycznie."""
    raw = subprocess.check_output(["sops", "-d", "--output-type", "json", str(secrets_file)])
    data = json.loads(raw)
    return "".join(f"{key}={value}\n" for key, value in sorted(data.items()))


def deploy_stack(stack_dir: Path) -> None:
    stack = stack_dir.name
    cfg = _stack_config(stack_dir)
    remote_dir = cfg.get("remote_dir") or f"{host.data.get('stacks_dir', '/opt')}/{stack}"
    docker_sudo = bool(cfg.get("sudo", host.data.get("docker_sudo", False)))
    files_sudo = bool(cfg.get("files_sudo", host.data.get("files_sudo", False)))
    compose_bin = cfg.get("compose_bin") or host.data.get("compose_bin") or "docker compose"
    changed_ops = []

    files.directory(
        name=f"{stack}: katalog {remote_dir}",
        path=remote_dir,
        present=True,
        _sudo=files_sudo,
    )

    changed_ops.append(files.put(
        name=f"{stack}: compose.yaml",
        src=str(stack_dir / "compose.yaml"),
        dest=f"{remote_dir}/compose.yaml",
        mode="644",
        _sudo=files_sudo,
    ))

    for extra in cfg.get("files", []):
        src = stack_dir / extra["src"]
        dest = extra.get("dest", extra["src"])
        changed_ops.append(files.put(
            name=f"{stack}: {extra['src']}",
            src=str(src),
            dest=f"{remote_dir}/{dest}",
            mode=str(extra.get("mode", "644")),
            _sudo=files_sudo,
        ))

    secrets_file = SECRETS_DIR / f"{stack}.sops.yaml"
    if secrets_file.exists():
        if _truthy(host.data.get("no_secrets")):
            logger.warning(
                f"{stack}: pomijam .env (no_secrets=true); wdrożenie zbuduje go z "
                f"{secrets_file.relative_to(REPO).as_posix()}"
            )
        else:
            changed_ops.append(files.put(
                name=f"{stack}: .env z sops",
                src=StringIO(_env_from_sops(secrets_file)),
                dest=f"{remote_dir}/.env",
                mode="600",
                _sudo=files_sudo,
            ))

    server.shell(
        name=f"{stack}: compose up",
        commands=[f"cd {remote_dir} && {compose_bin} up -d --remove-orphans"],
        _sudo=docker_sudo,
        _if=lambda ops=tuple(changed_ops): any(op.did_change() for op in ops),
    )


if _allowed():
    only = host.data.get("only")
    stack_dirs = sorted(p.parent for p in STACKS_DIR.glob("*/compose.yaml"))
    if only:
        stack_dirs = [d for d in stack_dirs if d.name == only]
        if not stack_dirs:
            logger.error(f"{NAME}: brak stacka '{only}' w {STACKS_DIR.relative_to(REPO).as_posix()}")
    if not stack_dirs:
        logger.info(f"{NAME}: brak stacków do wdrożenia w {STACKS_DIR.relative_to(REPO).as_posix()}")
    for stack_dir in stack_dirs:
        deploy_stack(stack_dir)
