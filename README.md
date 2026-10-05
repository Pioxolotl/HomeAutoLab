# HomeAutoLab

Opis maszyn homelaba i usług na nich, zarządzany przez [pyinfra](https://pyinfra.com) v3,
z pomocą Claude Code (skille w `.claude/skills/`). Zadania repo: [TODO.md](TODO.md);
zadania maszyn: `hosts/<host>/TODO.md`.

Etap 1: **obserwacja**. Hosty są dodawane w trybie `observe`, zbieramy fakty, opisujemy,
a usługi przenosimy do kodu tak, by `pyinfra --dry` nie pokazywał zmian. Dopiero potem
przełączamy hosty na `managed` i wdrażamy z repo.

## Jak to jest poukładane

```
hosts/<host>/
  host.yaml                 połączenie, tryb, grupy, dane dla deployów (stacks_dir, docker_sudo, compose_bin)
  facts.yaml                generowany przez tools/collect_facts.py
  README.md  TODO.md        opis maszyny i jej zadania
  services/<stack>/         compose.yaml · README.md · configi · opcjonalny stack.yaml
  secrets/<stack>.sops.yaml sekrety stacka, zaszyfrowane age (tylko takie pliki trafiają do repo)
deploys/compose_stacks.py   JEDEN generyczny deploy: wdraża wszystkie stacki hosta (albo jeden: --data only=<stack>)
templates/stack/            wzór stacka (compose, README, stack.yaml) - kopiujesz, nie dziedziczysz
templates/host/             wzór README i TODO hosta
group_data/                 dane wspólne dla grup hostów
tools/                      skrypty (collect_facts.py); .claude/skills/ - skille Claude
```

**Wszystko, co dotyczy maszyny, leży w jej katalogu**: fakty, opis, zadania, stacki, sekrety.
Stack to jeden projekt docker compose niezależnie od liczby kontenerów (Immich = 1 stack).
Nazwa katalogu = nazwa projektu compose = katalog na serwerze (`<stacks_dir>/<stack>`).
Ta sama aplikacja na dwóch hostach to dwa katalogi i mogą mieć różne wersje. Kopiowanie
zamiast współdzielenia jest celowe: hosty mogą się rozjeżdżać świadomie, a poprawka wspólna
to świadome powtórzenie. Gdy to zacznie boleć, dojdzie katalog wzorców do kopiowania.

**Części wspólne są agnostyczne.** `tools/`, `templates/`, `deploys/`, `.claude/skills/`
i `CLAUDE.md` nie wiedzą nic o konkretnych hostach; wiedza o platformie (Synology DSM, Proxmox)
może tam być, wiedza o maszynie (adresy, porty, decyzje) tylko w `hosts/<host>/`. Dzięki temu
te katalogi da się kiedyś wydzielić do plugina wspólnego dla wielu repo infra.

**Każdy stack ma README według [szablonu](templates/stack/README.md):** po co i dlaczego tak,
jak działa (porty, zależności, na co wpływa), instrukcja dla domowników, instrukcja techniczna,
dane i backup, troubleshooting, historia decyzji. Bez wypełnionego README stack nie jest gotowy.

## Start (jednorazowo, na laptopie z Windows)

Polecenia dla PowerShella. Na Linux/macOS analogicznie (`.venv/bin/...`, `~/.config/sops/age/keys.txt`).

**1. Python i pyinfra.** Python jest przez `uv`; środowisko repo to `.venv`.

```powershell
uv venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\pyinfra.exe --version
```

**2. SSH.** Każda maszyna ma wpis w `~/.ssh/config` i własny klucz; `ssh_host` w host.yaml to ten alias.

```
Host <alias>
    HostName <ip albo nazwa>
    Port <port>
    User <user>
    IdentityFile ~/.ssh/<alias>
    IdentitiesOnly yes
```

Sprawdzenie: `ssh -o BatchMode=yes <alias> true` musi przejść bez pytania o hasło.

**3. age + sops** (potrzebne przed pierwszym sekretem, czyli przed pierwszym stackiem).

```powershell
winget install --id FiloSottile.age -e
winget install --id SecretsOPerationS.SOPS -e
```

Nowy terminal, potem klucz:

```powershell
New-Item -ItemType Directory -Force "$env:APPDATA\sops\age" | Out-Null
age-keygen -o "$env:APPDATA\sops\age\keys.txt"
```

`age-keygen` wypisze linię `Public key: age1...`. Wklej ją do `.sops.yaml` w miejsce
`age1TWOJ_KLUCZ_PUBLICZNY`. Plik `keys.txt` to klucz prywatny: **nie trafia do repo**, skopiuj
jego treść do menedżera haseł (i na papier). Bez niego nie odszyfrujesz niczego z `secrets/`.

Jak to działa bez wpisywania hasła: klucz age w `keys.txt` nie ma passphrase, a `sops` szuka
tego pliku domyślnie w `%APPDATA%\sops\age\keys.txt`. Każde `sops <plik>` i każdy deploy
odszyfrowują automatycznie. Kto ma plik, ten ma dostęp, dlatego pilnujemy pliku, nie hasła.
Dla automatu (runner CI) dochodzi drugi klucz "deployer", dopisany jako kolejny odbiorca
w `.sops.yaml`, z regułą tylko dla jego hosta.

`sops <plik>` otwiera edytor z `SOPS_EDITOR`/`EDITOR`; na Windows nie ma domyślnego, więc ustaw
go raz na stałe (VS Code z `--wait`, bo sops czeka na zamknięcie karty):

```powershell
[Environment]::SetEnvironmentVariable("SOPS_EDITOR", "code --wait", "User")
```

Sekrety stacków twórz i edytuj skryptem, który zakłada katalog `hosts/<host>/secrets/`
(sops sam go nie tworzy), dobiera edytor, gdy `SOPS_EDITOR` nie jest ustawiony, i podaje sops
ścieżkę pasującą do `.sops.yaml`. Test w nowym terminalu:

```powershell
.venv\Scripts\python.exe tools\edit_secret.py example-nas-vm test
```

Otworzy się edytor; wpisz `hello: world`, zapisz. Plik na dysku ma być zaszyfrowany
(zaczyna się od `hello: ENC[...]`). Potem go usuń.

**4. Ochrona przed wyciekiem** (hooki gita: gitleaks + kontrola, czy pliki `*.sops.yaml` są zaszyfrowane):

```powershell
.venv\Scripts\python.exe -m pip install pre-commit
.venv\Scripts\pre-commit.exe install
```

Pierwszy commit (albo `.venv\Scripts\pre-commit.exe run --all-files`) trwa kilka minut: pre-commit
sam pobiera toolchain Go i buduje gitleaks. Drugi hook, `tools/check_sops_encrypted.py`, pilnuje,
żeby pliki w `hosts/*/secrets/` były zaszyfrowane.

## Praca z Claude Code

Uruchom `claude` w katalogu repo. Przykładowe prośby:

- „Dodaj hosta nas-vm, to VM na Synology, user deploy” → skill `onboard-host`
- „Odśwież dane wszystkich maszyn i powiedz, co się zmieniło” → `onboard-host`
- „Postaw Dozzle na NAS-ie, Docker przez proxy” → `new-service`
- „Przenieś do pyinfra kontener z Uptime Kuma z nas-vm” → `adopt-service`
- „Strona dzieci nie działa, sprawdź co się dzieje” → `diagnose-host`

Zasady dla Claude są w `CLAUDE.md`, uprawnienia w `.claude/settings.json`. Claude nie odszyfrowuje
sekretów (podgląd wdrożenia robi z `--data no_secrets=true`), nie zna haseł sudo i nie wdraża sam;
`pyinfra` bez `--dry` uruchamiasz Ty.

## Ręcznie, bez Claude

```powershell
.venv\Scripts\python.exe tools\collect_facts.py <host>            # fakty hosta (bez sudo)
.venv\Scripts\python.exe tools\collect_facts.py <host> --sudo     # pełne fakty; pyinfra zapyta o hasło sudo
.venv\Scripts\python.exe tools\collect_facts.py --all
.venv\Scripts\pyinfra.exe inventory.py debug-inventory
.venv\Scripts\pyinfra.exe inventory.py deploys\compose_stacks.py --limit <host> --dry                      # podgląd wszystkich stacków
.venv\Scripts\pyinfra.exe inventory.py deploys\compose_stacks.py --limit <host> --dry --data only=<stack>  # jeden stack
.venv\Scripts\pyinfra.exe inventory.py deploys\compose_stacks.py --limit <host>                            # wdrożenie
```

Host w `observe` jest przez deploy pomijany; `--data adopt_check=true` pozwala na podgląd mimo to
(tylko z `--dry`). Synology: `sudo` pyta o hasło, więc wdrożenie jest interaktywne; `/tmp` jest tam
`noexec`, dlatego host.yaml ma `temp_dir`. Przebieg faktów bez sudo nie kasuje sekcji zebranych z sudo.

## Sekrety

```powershell
.venv\Scripts\python.exe tools\edit_secret.py <host> <stack>   # tworzy/edytuje, zapisuje zaszyfrowane
```

Deploy robi z tego plik `.env` w katalogu stacka (`KEY=value`, mode 600). W repo lądują wyłącznie
zaszyfrowane pliki. Hasła „ludzkie” (panele, konta domowników) trzymaj w menedżerze haseł, nie tutaj.

## Automatyzacja wdrożeń (później)

Dziś wdraża człowiek z laptopa. Docelowo runner (VM na NAS albo self-hosted GitHub Actions)
z własnym kluczem SSH i kluczem age "deployer" wdraża po merge do `master`. Otwarta kwestia:
sudo na Synology wymaga hasła, więc runner potrzebuje albo hasła w sekrecie CI, albo konta
z ograniczonym NOPASSWD tylko na `docker-compose`. To świadoma decyzja na później, nie domyślna.
