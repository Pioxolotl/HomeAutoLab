#!/usr/bin/env python3
"""
Hook pre-commit: każdy plik przekazany w argumentach (hosts/*/secrets/*.sops.yaml|json) musi być
zaszyfrowany przez sops, czyli zawierać blok metadanych `sops:` (YAML) albo `"sops":` (JSON).
Zwraca 1 i wypisuje niezaszyfrowane pliki. Nie czyta wartości, tylko sprawdza obecność znacznika.
"""

from __future__ import annotations

import sys
from pathlib import Path


def is_encrypted(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(line.startswith("sops:") for line in text.splitlines()) or '"sops":' in text


def main(argv: list[str]) -> int:
    bad = [p for p in map(Path, argv) if p.exists() and not is_encrypted(p)]
    for p in bad:
        print(f"NIEZASZYFROWANY: {p} - uruchom: sops {p}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
