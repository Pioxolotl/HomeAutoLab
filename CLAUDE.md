# Repo infra - zasady dla Claude

To repo opisuje maszyny domowego homelaba i usługi na nich, zarządzane przez pyinfra (v3).
Dokumentacja i komunikaty w repo po polsku, kod i nazwy plików po angielsku.

## Struktura
- `inventory.py` buduje grupy z `hosts/*/host.yaml` i przekazuje wszystkie klucze host.yaml do
  `host.data` (nie edytuj go przy dodawaniu hostów)
- `hosts/<host>/` - wszystko o jednej maszynie: host.yaml (ręcznie), facts.yaml (generowany),
  README.md, TODO.md, `services/<stack>/` (compose.yaml, README.md, configi, opcjonalny stack.yaml),
  `secrets/<stack>.sops.yaml` (wyłącznie zaszyfrowane sops/age)
- `deploys/compose_stacks.py` - jedyny deploy stacków: dla hosta wdraża `hosts/<host>/services/*/`.
  Nie pisz deploy.py per stack; nadpisania idą do `stack.yaml` (wzór `templates/stack/stack.yaml`)
- `templates/stack/`, `templates/host/` - wzory do **kopiowania** (README, compose, TODO)
- `group_data/` - dane grup; `tools/` - deterministyczne skrypty; `.claude/skills/` - skille
- `TODO.md` - tylko sprawy repo i narzędzi; zadania maszyny w `hosts/<host>/TODO.md`

Części wspólne (`tools/`, `templates/`, `deploys/`, `.claude/skills/`, ten plik) są **agnostyczne
wobec hostów**: mogą znać platformy (Synology DSM, Proxmox, HAOS), nie znają konkretnych maszyn,
adresów ani decyzji. To, co dotyczy maszyny, pisz w `hosts/<host>/`.

## Twarde zasady
1. Na serwerach wykonujesz tylko polecenia odczytu. Zmiany idą przez kod w repo.
2. pyinfra uruchamiasz wyłącznie z `--dry`, a deploy stacków dodatkowo z `--data no_secrets=true`,
   żeby nie uruchamiać `sops -d`. Wdrożenia (bez --dry) uruchamia człowiek.
3. Nigdy nie odszyfrowujesz sekretów (`sops -d`, `sops exec-*`) i nie czytasz kluczy age ani SSH
   (także `%APPDATA%\sops\age\`). Operujesz na nazwach sekretów, wartości wpisuje użytkownik
   w `sops <plik>`. Hasła sudo nie znasz: przebiegi wymagające sudo uruchamia użytkownik.
4. Nowe hosty mają `managed: observe`. Zmiana na `managed` tylko na wyraźne polecenie.
5. Serwery klientów nie należą do tego repo - mają osobne repo i osobne klucze.
6. Przed commitem sprawdź diff pod kątem sekretów (hasła, tokeny, klucze, prywatne URL-e
   z danymi logowania). Commity: `host(<nazwa>): ...`, `stack(<host>/<stack>): ...`, `tools: ...`,
   `docs: ...`, `skills: ...`.
7. Nie obniżaj bezpieczeństwa dla wygody narzędzi (NOPASSWD, otwieranie portów, goły docker.sock).
   Gdy czegoś nie da się zrobić bez tego, przedstaw to jako decyzję użytkownika z opisem ryzyka.

## Dokumentacja (obowiązkowa)
- Każdy host ma `README.md` i `TODO.md` według `templates/host/`, uzgodnione z facts.yaml.
- Każdy stack ma `README.md` według `templates/stack/README.md`: wszystkie sekcje wypełnione,
  w tym "Dla domowników" (prostym językiem albo wprost "tylko dla admina") i "Dane i backup"
  (brak backupu nazwij wprost i dopisz do TODO hosta). Stack bez README nie jest gotowy.
- Fakty od przypuszczeń oddzielaj słowami ("potwierdzone <data>", "prawdopodobnie", "do potwierdzenia").
- Gdy stan serwera się zmienia (nowe fakty, decyzja użytkownika), aktualizuj README i TODO hosta
  w tym samym kroku; nie zostawiaj dokumentacji w tyle za faktami.

## Przydatne polecenia
Python i pyinfra są w `.venv` w katalogu repo (na Windows `python` z PATH bywa tylko aliasem
Microsoft Store). Używaj `.venv/Scripts/python.exe` i `.venv/Scripts/pyinfra.exe`
(Linux/macOS: `.venv/bin/...`) albo aktywuj venv. Pliki w repo czytaj i zapisuj jako UTF-8.
- `python tools/collect_facts.py <host>` / `--all` - fakty (read-only; sekcje sudo-only
  zachowywane z poprzedniego przebiegu). `--sudo` uruchamia użytkownik.
- `pyinfra inventory.py debug-inventory` - podgląd hostów i grup
- `pyinfra inventory.py deploys/compose_stacks.py --limit <host> --dry --data no_secrets=true`
  (`--data only=<stack>` dla jednego stacka; `--data adopt_check=true` dla hosta w observe)

## Platforma: Synology DSM
Docker i compose poza PATH: `/var/packages/ContainerManager/target/usr/bin/{docker,docker-compose}`
(compose v2 jako osobna binarka, nie wtyczka) - w host.yaml `compose_bin`, `docker_sudo: true`,
`stacks_dir: /volume1/docker`. Docker wymaga roota, sudo pyta o hasło. `/tmp` jest `noexec`,
stąd `temp_dir` w host.yaml. Kontenery z CLI widać w GUI Container Manager, ale nie jako "projekt";
nie klikać w nich w GUI. Szczegóły w skillach onboard-host i new-service.
