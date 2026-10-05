# Wzorce pyinfra (v3) do adopcji usług

Sprawdzone na pyinfra 3.10. Kod deployu wykonuje się raz na host; `host.data` zawiera
dane z host.yaml (`inventory_name`, `managed`, `owner`, `role`) i z `group_data/`.

## Plik 1:1 z repo na serwer

```python
cfg = files.put(
    name="app: config.toml",
    src=str(HERE / "config.toml"),
    dest="/opt/app/config.toml",
    user="root", group="root", mode="644",   # takie, jakie są TERAZ na serwerze
)
```
Właściciela i uprawnienia odczytasz: `ssh <host> stat -c '%U %G %a' <ścieżka>`.
Jeśli nie podasz `user`/`group`, pyinfra ich nie sprawdza (mniej fałszywych różnic).

## Plik z danymi (szablon Jinja2)

```python
files.template(
    name="caddy: Caddyfile",
    src=str(HERE / "Caddyfile.j2"),
    dest="/etc/caddy/Caddyfile",
    domain=host.data.get("domain"),
)
```
Przy adopcji zacznij od `files.put` z gotowym plikiem; szablon wprowadź później.

## Cały katalog

```python
files.sync(
    name="site: statyczne pliki",
    src=str(HERE / "public"),
    dest="/var/www/site",
    delete=False,          # przy adopcji NIE usuwaj plików, których nie ma w repo
)
```

## Restart tylko przy zmianie

```python
server.shell(
    name="app: compose up",
    commands=["cd /opt/app && docker compose up -d --remove-orphans"],
    _if=lambda: compose.did_change() or cfg.did_change(),
)
```

## Usługa systemd

```python
unit = files.put(
    name="worker: unit",
    src=str(HERE / "worker.service"),
    dest="/etc/systemd/system/worker.service",
    mode="644",
)
systemd.service(
    name="worker: działa i włączona",
    service="worker.service",
    running=True,
    enabled=True,
)
systemd.service(
    name="worker: reload + restart po zmianie unitu",
    service="worker.service",
    daemon_reload=True,
    restarted=True,
    _if=unit.did_change,     # przekazujesz funkcję, nie jej wynik
)
```

## Pakiety (Debian/Ubuntu)

```python
apt.packages(
    name="base: pakiety",
    packages=["curl", "git", "htop"],
    update=True,
    cache_time=3600,
)
```
Przy adopcji wpisuj tylko pakiety, które już są zainstalowane, żeby --dry było puste.

## Sekrety

Odszyfrowanie zawsze lokalnie (u użytkownika lub na runnerze) przez `sops -d`, wynik
trafia na serwer jako plik `.env` z `mode="600"`. Robi to `deploys/compose_stacks.py`
(`_env_from_sops`). Nie loguj wartości, nie wypisuj ich w `name=` operacji.

## Typowe źródła fałszywych różnic w --dry

- brak/obecność końcowej nowej linii w pliku,
- CRLF vs LF (pliki edytowane na Windows),
- inne `mode` (np. 600 vs 644) lub właściciel,
- ścieżka przez symlink (`/opt/app` -> `/srv/app`): użyj ścieżki docelowej,
- plik generowany przez samą usługę (wtedy nie zarządzaj nim w ogóle).
