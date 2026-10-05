# dozzle

> Strona w przeglądarce, na której widać na żywo logi wszystkich kontenerów na NAS-ie, bez logowania
> się przez SSH i bez klikania w Container Managerze.

| | |
|---|---|
| **Host** | `homelab-nas` (`hosts/homelab-nas/README.md`) |
| **Stack** | `/volume1/docker/dozzle` · obrazy: `amir20/dozzle:v11.3.0`, `tecnativa/docker-socket-proxy:v0.5.0` |
| **Adres** | `http://192.168.50.100:8080` (tylko LAN) · docelowo za reverse proxy z HTTPS |
| **Stan** | **działa od 2026-10-05** (healthcheck 200, port 8080 tylko na 192.168.50.100 - sprawdzone) |
| **Dla domowników** | nie, tylko admin |
| **Dane krytyczne** | nie |
| **Backup** | niepotrzebny: `data/users.yml` odtwarzany z repo (sops), profile UI to tylko preferencje |
| **Sekrety** | `hosts/homelab-nas/secrets/dozzle.sops.yaml`, klucz `USERS_YML` (treść users.yml z hashem bcrypt) |

## Po co i dlaczego tak

- **Problem:** żeby zobaczyć, czemu kontener nie działa, trzeba było wejść przez SSH, zrobić sudo
  i wołać `docker logs` pełną ścieżką DSM. Przy kilku stackach to męczące, a logi wielu kontenerów
  naraz w ogóle nie dało się oglądać.
- **Dlaczego Dozzle:** jeden mały kontener, zero bazy danych, logi na żywo z filtrowaniem, obsługa
  wielu hostów na później (VM, VPS) przez agentów. Alternatywy: Portainer (dużo więcej niż logi
  i pełne uprawnienia do Dockera), Grafana + Loki (osobny stos do utrzymania; sensowny dopiero
  przy wielu maszynach i potrzebie historii).
- **Decyzje architektoniczne:**
  - **Docker API przez socket-proxy, nie goły socket.** Kontener z zamontowanym
    `/var/run/docker.sock` to w praktyce root na hoście. Proxy (HAProxy) przepuszcza tylko
    GET na `containers`, `events`, `info`, `version`, `_ping`; `POST=0` blokuje start/stop/exec.
    Nawet luka w Dozzle nie da nikomu kontroli nad Dockerem.
  - **Sprawdzanie aktualizacji obrazów wyłączone** (`DOZZLE_IMAGE_CHECK_MODE: off`). Wymagałoby
    otwarcia w proxy `/images` i `/distribution` (dockerd odpytywałby rejestry). Bez tego Dozzle
    sypał 403 co kilkanaście sekund. Wersje i tak zmieniamy w repo, nie z Dozzle.
  - **Proxy bez `ports`.** Jest widoczne wyłącznie w sieci compose `internal`; z LAN nie ma do niego
    dostępu, więc Docker API nie wycieka poza stack.
  - **Port 8080 tylko na 192.168.50.100.** Nie na 0.0.0.0, więc nie wystawi się przypadkiem na innym
    interfejsie. Router nie przekierowuje 8080, Dozzle nie jest dostępne z internetu.
  - **Logowanie włączone (simple auth).** Logi potrafią zawierać tokeny i adresy. Hasło jest
    hashowane bcrypt w `users.yml`, a sam plik leży w sops, nie jawnie w repo.
  - **Obrazy przypięte do wersji**, aktualizacja to zmiana tagu w repo i wdrożenie.
  - **Pierwszy stack w repo**, więc celowo prosty: testuje całą ścieżkę repo → pyinfra → NAS.

## Jak działa

- **Kontenery:** `socket-proxy` (HAProxy przed `/var/run/docker.sock`, tylko odczyt) i `dozzle`
  (UI + backend). Dozzle pyta proxy przez `tcp://socket-proxy:2375` o listę kontenerów i strumień
  logów; przeglądarka łączy się z Dozzle na 8080.
- **Sieć:** `192.168.50.100:8080 → dozzle:8080`. Sieć compose `internal` łączy oba kontenery;
  proxy nie ma portów na hoście. Nic nie jest wystawione na 0.0.0.0 ani do internetu.
- **Od czego zależy:** działający dockerd Container Managera, plik `data/users.yml` (bez niego
  Dozzle nie wpuści nikogo), poprawny adres LAN NAS-a w `ports`.
- **Na co wpływa:** na nic. Gdy Dozzle padnie, żaden inny kontener ani usługa DSM tego nie odczuje.
  Proxy też nie jest używane przez nic innego (na razie; w przyszłości może z niego korzystać np. Uptime Kuma).

## Dla domowników

Tylko dla admina. Dla domowników niewidoczna, jej awaria niczego domowego nie psuje.

## Instrukcja techniczna

### Pierwsze uruchomienie

1. **Plik użytkowników.** Polecenie `generate` tylko liczy hash bcrypt hasła i wypisuje gotowy
   YAML; kontener kończy się od razu, nic nie zostaje uruchomione. Bez `--password` Dozzle zapyta
   o hasło bez echa. Dwa równoważne warianty:
   - na NAS-ie (obraz zostanie w cache i wdrożenie go nie pobierze drugi raz):
     ```bash
     ssh homelab-nas "sudo /var/packages/ContainerManager/target/usr/bin/docker run -it --rm amir20/dozzle:v11.3.0 generate admin --email twoj@email --name Admin"
     ```
   - lokalnie w PowerShellu (Podman w PATH):
     ```powershell
     podman run -it --rm docker.io/amir20/dozzle:v11.3.0 generate admin --email twoj@email --name "Admin"
     ```
   Wynik to YAML `users:` z hashem bcrypt. Hasło zapisz w Bitwardenie.
2. **Sekret w sops** (skrypt zakłada katalog `secrets/`, wybiera edytor i odpala sops):
   ```powershell
   .venv\Scripts\python.exe tools\edit_secret.py homelab-nas dozzle
   ```
   W edytorze wklej (treść users.yml wcięta pod `USERS_YML: |`):
   ```yaml
   USERS_YML: |
     users:
       admin:
         email: twoj@email
         name: Admin
         password: $2a$11$...
         filter:
         roles:
   ```
   Zapisz i zamknij kartę. Plik na dysku ma być zaszyfrowany (`USERS_YML: ENC[...]`).
3. **Host na `managed`:** w `hosts/homelab-nas/host.yaml` zmień `managed: observe` na `managed: managed`.
4. **Podgląd** (można zrobić wcześniej, Claude robi to bez sekretów):
   ```powershell
   .venv\Scripts\pyinfra.exe inventory.py deploys\compose_stacks.py --limit homelab-nas --dry --data only=dozzle
   ```
5. **Wdrożenie** (pyinfra zapyta o hasło sudo przy `compose up`):
   ```powershell
   .venv\Scripts\pyinfra.exe inventory.py deploys\compose_stacks.py --limit homelab-nas --data only=dozzle
   ```
6. **Test:** `http://192.168.50.100:8080` → ekran logowania → po zalogowaniu host `homelab-nas`
   z listą kontenerów (na start: `dozzle-dozzle-1`, `dozzle-socket-proxy-1`).
7. Odśwież fakty (`collect_facts.py homelab-nas --sudo`), uzupełnij "Stan" w tabeli wyżej
   i README hosta.

### Wdrożenie i aktualizacja

Polecenia jak w punktach 4-5. Aktualizacja Dozzle lub proxy: nowy tag w `compose.yaml`
(sprawdź changelog Dozzle, duże wersje zmieniały format `users.yml`), commit, wdrożenie.
Po aktualizacji: logowanie działa, lista kontenerów się ładuje, healthcheck `healthy`
(`docker ps` pokazuje `(healthy)` przy dozzle).

### Konfiguracja i sekrety

Cała konfiguracja to zmienne w `compose.yaml` (`DOZZLE_*`). Jedyny sekret: `USERS_YML`
w `hosts/homelab-nas/secrets/dozzle.sops.yaml` → `data/users.yml` (mode 600). Zmiana hasła
lub dodanie użytkownika: wygeneruj nowy wpis poleceniem z punktu 1,
`python tools/edit_secret.py homelab-nas dozzle`, wdrożenie (zmiana pliku wywołuje `compose up`,
Dozzle czyta users.yml przy starcie).

### Logi i stan

- Logi samego Dozzle: `sudo /var/packages/ContainerManager/target/usr/bin/docker logs --tail 100 dozzle-dozzle-1`
  (proxy: `dozzle-socket-proxy-1`; proxy loguje każde żądanie, więc widać, o co Dozzle pyta).
- Zdrowie: `curl -s -o /dev/null -w '%{http_code}' http://192.168.50.100:8080/healthcheck` → `200`.
- W GUI Container Managera oba kontenery są widoczne, ale **nie klikać** w nich (restart/edycja
  poszłyby obok repo).

## Dane i backup

- **Stan:** `data/users.yml` - zarządza nim deploy, odtwarzalny z repo (sops) jednym wdrożeniem.
  Dozzle nie trzyma historii logów; pokazuje to, co ma dockerd.
- **Preferencje:** `data/<użytkownik>/` - profil UI zapisywany przez Dozzle (ulubione, ustawienia
  widoku). Utrata = ustawienia domyślne, nic więcej.
- **`data/session_secret`** - klucz podpisujący ciasteczka logowania, generowany przez Dozzle przy
  pierwszym starcie. Utrata = wszyscy zostają wylogowani. **Uwaga:** przez dziedziczone ACL udziału
  `docker` plik dostaje uprawnienia `rwxrwxrwx`; kto ma dostęp do udziału `docker` (np. przez SMB),
  może go odczytać i podrobić sesję. Dlatego dostęp do udziału `docker` tylko dla admina
  (zadanie w `hosts/homelab-nas/TODO.md`).
- **Backup:** **niepotrzebny.** Odtworzenie = wdrożenie z repo. Ostatni test odtworzenia: nigdy
  (zrobić przy okazji pierwszej aktualizacji: usunąć katalog `/volume1/docker/dozzle`, wdrożyć, zalogować się).

## Troubleshooting

| Objaw | Prawdopodobna przyczyna | Co zrobić |
|---|---|---|
| strona nie odpowiada | kontener dozzle nie działa albo zły adres w `ports` | `docker ps -a`, logi dozzle; sprawdź IP NAS-a w facts.yaml |
| ekran logowania odrzuca hasło / "no users" | brak lub zły `data/users.yml`, wcięcia w YAML | sprawdź, że `/volume1/docker/dozzle/data/users.yml` istnieje i zaczyna się od `users:`; wygeneruj ponownie |
| po zalogowaniu pusto, "no hosts" / błąd połączenia | socket-proxy nie wstał albo brakuje mu uprawnień | logi `dozzle-socket-proxy-1`; `CONTAINERS=1 EVENTS=1 INFO=1` muszą być ustawione |
| brakuje logów jednego kontenera | kontener używa innego log drivera niż json-file/journald | `docker inspect -f '{{.HostConfig.LogConfig.Type}}' <kontener>` |
| healthcheck `unhealthy` po aktualizacji | zmiana w nowej wersji Dozzle (np. format users.yml) | changelog Dozzle, logi; w razie czego wróć do poprzedniego tagu w repo |
| w logach dozzle `403 Forbidden ... administrative rules` | Dozzle woła endpoint, którego socket-proxy nie przepuszcza | logi `dozzle-socket-proxy-1` pokażą ścieżkę; najpierw wyłącz funkcję w Dozzle (`DOZZLE_*`), proxy poszerzaj tylko o GET i świadomie |
| `mkdir /data/...: read-only file system` | `./data` zamontowany jako `:ro` | Dozzle zapisuje profile w `/data`; montować bez `:ro` |
| po restarcie NAS nie wstało | Container Manager startuje później niż oczekiwano | `restart: unless-stopped` powinno wystarczyć; sprawdź `docker ps -a` po 2-3 min |

## Historia i decyzje

- 2026-10-05: utworzono jako pierwszy stack w układzie `hosts/<host>/services/<stack>/`. Wariant:
  LAN + HTTP + simple auth (opcja A), reverse proxy z HTTPS odłożony do czasu, aż pojawi się
  nginx/Traefik dla całego NAS-a. Docker API przez socket-proxy z `POST=0`.
- 2026-10-05: po pierwszym wdrożeniu dwie poprawki z logów: `DOZZLE_IMAGE_CHECK_MODE: off` zamiast
  poszerzania proxy o `/images` i `/distribution` (403 co kilkanaście sekund) oraz `./data` do
  zapisu, bo Dozzle zapisuje tam profile użytkowników. Przy okazji: DSM wymaga
  `ssh_file_transfer_protocol: scp` (SFTP ma wirtualny widok udziałów).
