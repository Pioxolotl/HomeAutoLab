"""
Inventory budowane automatycznie z hosts/*/host.yaml.

Każdy host to katalog hosts/<nazwa>/ z plikami:
  host.yaml      - opis pisany ręcznie/przez skill onboard-host (połączenie, grupy, tryb, dane dla deployów)
  facts.yaml     - generowany przez tools/collect_facts.py, NIE edytować ręcznie
  README.md      - opis dla ludzi: rola, usługi, ryzyka, otwarte pytania
  TODO.md        - zadania dotyczące tej maszyny
  services/<stack>/   - stacki docker compose tego hosta (wdraża deploys/compose_stacks.py)
  secrets/<stack>.sops.yaml - sekrety stacków, zaszyfrowane sops/age

Wszystkie klucze z host.yaml (poza `disabled`) trafiają do host.data, więc deploye mogą czytać
np. stacks_dir, docker_sudo, compose_bin, temp_dir. Klucze ssh_* rozumie pyinfra.

Grupy powstają z pola `groups` oraz automatycznie:
  observe  - hosty tylko do obserwacji (managed: observe), deploye je pomijają
  managed  - hosty, którymi pyinfra może zarządzać
  owner_<x> - np. owner_me, owner_brother
"""

from collections import defaultdict
from pathlib import Path

import yaml

_HOSTS_DIR = Path(__file__).resolve().parent / "hosts"
_groups = defaultdict(list)

for _host_file in sorted(_HOSTS_DIR.glob("*/host.yaml")):
    _cfg = yaml.safe_load(_host_file.read_text(encoding="utf-8")) or {}
    if _cfg.get("disabled"):
        continue

    _name = _host_file.parent.name
    _target = _cfg.get("ssh_host", _name)
    _data = {k: v for k, v in _cfg.items() if k != "disabled" and v is not None}
    _data.update({
        "inventory_name": _name,
        "managed": _cfg.get("managed", "observe"),
        "owner": _cfg.get("owner", "me"),
        "role": _cfg.get("role", ""),
        "_sudo": bool(_cfg.get("sudo", False)),
    })
    _entry = (_target, _data)

    for _group in _cfg.get("groups", []):
        _groups[_group].append(_entry)
    _groups[_data["managed"]].append(_entry)
    _groups[f"owner_{_data['owner']}"].append(_entry)

# pyinfra traktuje listy na poziomie modułu jako grupy hostów
globals().update(_groups)
