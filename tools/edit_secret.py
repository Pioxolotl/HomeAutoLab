#!/usr/bin/env python3
"""
Tworzy lub edytuje sekret stacka: hosts/<host>/secrets/<stack>.sops.yaml.

    python tools/edit_secret.py <host> <stack>

Co robi:
  1. sprawdza, że host istnieje (hosts/<host>/host.yaml) i że sops jest w PATH,
  2. zakłada katalog hosts/<host>/secrets/, jeśli go nie ma (sops sam go nie tworzy),
  3. wybiera edytor: SOPS_EDITOR / EDITOR, a gdy brak - VS Code z --wait (jeśli jest),
  4. uruchamia `sops <plik>` ze ścieżką z ukośnikami (pasuje do reguł w .sops.yaml).

Uruchamia WYŁĄCZNIE człowiek: sops pokazuje w edytorze odszyfrowaną treść.
Claude tego skryptu nie uruchamia (patrz CLAUDE.md, zasada 3).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def fail(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(1)


def pick_editor(env: dict) -> None:
    if env.get("SOPS_EDITOR") or env.get("EDITOR"):
        return
    if shutil.which("code"):
        env["SOPS_EDITOR"] = "code --wait"
        print("Edytor: VS Code (--wait). Po zapisaniu ZAMKNIJ kartę pliku, wtedy sops zaszyfruje.")
        print('Na stałe: [Environment]::SetEnvironmentVariable("SOPS_EDITOR", "code --wait", "User")')
        return
    fail("Brak edytora dla sops. Ustaw SOPS_EDITOR, np. (PowerShell, na stałe):\n"
         '  [Environment]::SetEnvironmentVariable("SOPS_EDITOR", "code --wait", "User")')


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        fail("Użycie: python tools/edit_secret.py <host> <stack>")
    host, stack = argv
    for label, value in (("host", host), ("stack", stack)):
        if not NAME_RE.match(value):
            fail(f"Niepoprawna nazwa {label}: {value!r} (małe litery, cyfry, '-', '_')")

    host_dir = REPO / "hosts" / host
    if not (host_dir / "host.yaml").exists():
        fail(f"Nie ma hosta {host}: brak hosts/{host}/host.yaml")
    if not (host_dir / "services" / stack).is_dir():
        print(f"Uwaga: nie ma jeszcze katalogu hosts/{host}/services/{stack}/ - sekret powstanie mimo to.")
    if not shutil.which("sops"):
        fail("Nie znaleziono sops w PATH. Instalacja: winget install --id SecretsOPerationS.SOPS -e\n"
             "(po instalacji otwórz nowy terminal albo zrestartuj VS Code)")

    secrets_dir = host_dir / "secrets"
    if not secrets_dir.exists():
        secrets_dir.mkdir(parents=True)
        print(f"Utworzono katalog hosts/{host}/secrets/")

    env = os.environ.copy()
    pick_editor(env)

    rel = f"hosts/{host}/secrets/{stack}.sops.yaml"
    print(f"sops {rel}")
    return subprocess.call(["sops", rel], cwd=REPO, env=env)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
