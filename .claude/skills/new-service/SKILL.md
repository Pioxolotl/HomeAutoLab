---
name: new-service
description: Tworzy od zera nowy stack docker compose w hosts/<host>/services/<stack>/ - compose, opcjonalny stack.yaml, sekrety przez sops, README według szablonu - i doprowadza go do stanu, w którym pyinfra --dry pokazuje dokładnie to, co ma powstać. Używaj, gdy użytkownik chce "postawić", "zainstalować", "dodać" nową aplikację (Dozzle, Immich, Uptime Kuma, Minecraft...) na hoście z repo, zaplanować jej wdrożenie albo pyta, jak coś wdrożyć "porządnie". Dla usług, które już działają na serwerze, użyj adopt-service.
---

# Nowy stack od zera

Idea: stack powstaje najpierw w repo (kod + dokumentacja), potem jest wdrażany. Żadnego
"klikania w GUI, a potem przepisywania". Gotowe = `--dry` pokazuje tylko spodziewane zmiany,
README jest wypełnione, a użytkownik wie, co ma zrobić ręcznie.

## Zasady

- Działasz w repo. Na hoście tylko odczyt (sprawdzenie ścieżek, portów, wersji compose).
- pyinfra wyłącznie z `--dry --data no_secrets=true` (bez `sops -d`). Wdrożenie uruchamia
  użytkownik; gdy host wymaga sudo z hasłem, pyinfra go o nie zapyta. Hosty w `observe` są
  pomijane przez deploy; `--data adopt_check=true` pozwala na podgląd. Przełączenie na `managed`
  to decyzja użytkownika, przypomnij o niej.
- Sekrety: ustalasz **nazwy** zmiennych, plik `hosts/<host>/secrets/<stack>.sops.yaml` tworzy
  użytkownik (`sops <plik>`). Nie generuj haseł do czatu; jeśli trzeba hasha (bcrypt itp.),
  podaj polecenie, które użytkownik uruchomi sam.
- Jeden stack = jeden katalog `hosts/<host>/services/<stack>/`, nawet gdy ma pięć kontenerów.
  Nazwa katalogu = nazwa projektu compose = katalog na serwerze (`<stacks_dir>/<stack>`).
- Nie piszesz deploy.py. Wdraża `deploys/compose_stacks.py`; nadpisania (inna ścieżka, dodatkowe
  pliki) idą do `stack.yaml` według `templates/stack/stack.yaml`.
- Nie obniżaj bezpieczeństwa dla wygody: brak NOPASSWD, brak gołego docker.sock w kontenerach
  aplikacji, brak portów na 0.0.0.0, jeśli wystarczy adres LAN lub 127.0.0.1.

## Kroki

1. **Ustal z użytkownikiem** (jednym pytaniem zbiorczym, jeśli czegoś brakuje): host, po co
   ten stack, kto z niego korzysta (admin / domownicy), skąd ma być dostępny (LAN / VPN /
   internet), gdzie mają leżeć dane, czy jest coś do backupu. To od razu treść README.

2. **Sprawdź hosta** w `hosts/<host>/README.md`, `facts.yaml` i `host.yaml`: wolne porty, IP LAN,
   `stacks_dir`, `docker_sudo`, `compose_bin`, `temp_dir`, tabela przekierowań z routera (żeby nie
   wystawić przypadkiem portu, który router już kieruje na hosta). Platforma: sekcja niżej.

3. **Zaprojektuj compose** i opisz decyzje zanim napiszesz plik:
   - obrazy z przypiętym tagiem (nie `latest`), `restart: unless-stopped`, healthcheck gdy obraz go ma;
   - porty: `IP_LAN:port:port` albo `127.0.0.1:port:port` (gdy przed usługą będzie reverse proxy);
     nigdy sam `port:port`, bo to 0.0.0.0;
   - dane w `./data` (bind mount w katalogu stacka) - łatwiej backupować niż nazwane wolumeny;
     nie montuj `:ro`, jeśli dokumentacja aplikacji nie mówi wprost, że tam nie pisze
     (Dozzle pisze profile do `/data`, choć users.yml tylko czyta);
   - Docker API tylko przez **socket-proxy** (wzorzec niżej), nigdy goły `/var/run/docker.sock`
     w kontenerze aplikacji;
   - sekrety przez `env_file: .env` (deploy generuje `.env` z sops) albo plik montowany z `mode 600`
     przez `files:` w stack.yaml; żadnych haseł w compose.

4. **Utwórz `hosts/<host>/services/<stack>/`** z `templates/stack/`: `compose.yaml`, `README.md`
   (**wypełnij wszystkie sekcje**, także "Dla domowników" i "Dane i backup"; brak backupu wpisz
   wprost i dodaj do `hosts/<host>/TODO.md`), `stack.yaml` tylko gdy coś nadpisujesz.

5. **Sekrety:** wypisz użytkownikowi nazwy kluczy, gotowy wzór YAML do wklejenia i polecenie
   `python tools/edit_secret.py <host> <stack>` (zakłada `hosts/<host>/secrets/`, dobiera edytor,
   odpala sops). Nie każ zakładać katalogu ręcznie i nie podawaj gołego `sops <ścieżka>`.
   Tego skryptu nie uruchamiasz sam: pokazuje odszyfrowaną treść. Jeśli `.sops.yaml` ma jeszcze
   placeholder klucza age, zatrzymaj się: najpierw środowisko (README repo, sekcja "Start").
   Gdy sekret to cały plik (np. users.yml z hashem), dodaj go do `secret_files:` w stack.yaml.

6. **Sprawdź:**
   `pyinfra inventory.py deploys/compose_stacks.py --limit <host> --dry --data no_secrets=true --data only=<stack>`
   (plus `--data adopt_check=true`, gdy host jest w observe). Każdą pozycję w Change wyjaśnij
   użytkownikowi: to lista rzeczy, które wdrożenie zrobi. Ostrzeżenie o pominiętym `.env` jest
   oczekiwane, gdy stack ma sekrety.

7. **Dopisz stack do `hosts/<host>/README.md`** ("Co tu działa" z linkiem do README stacka, port
   w "Sieć", dane w "Dane i backup").

8. **Po pierwszym wdrożeniu poproś o logi** obu kontenerów z pierwszych minut (Dozzle albo
   `docker logs`) i przejrzyj je pod kątem `error`, `403`, `read-only`. Poprawki z logów opisz
   w "Historia i decyzje" i "Troubleshooting" README stacka.

9. **Przekaż użytkownikowi** listę kroków ręcznych w kolejności: sops, `managed`, wdrożenie, reguła
   reverse proxy w GUI (jeśli jest), test. Po wdrożeniu poproś o `collect_facts.py <host> --sudo`
   (jeśli host tego wymaga) i uzupełnij README stacka o "działa od <data>". Commit:
   `stack(<host>/<stack>): add`.

## Platforma: Synology DSM (Container Manager)

- Docker: `/var/packages/ContainerManager/target/usr/bin/docker`, compose jako osobna binarka
  `/var/packages/ContainerManager/target/usr/bin/docker-compose` (v2). Nie ma wtyczki `docker compose`.
  W host.yaml: `compose_bin`, `docker_sudo: true`, `stacks_dir: /volume1/docker`.
- Wszystko z Dockerem wymaga roota; pyinfra zapyta użytkownika o hasło. `/tmp` jest `noexec`,
  więc host.yaml musi mieć `temp_dir`. SFTP ma wirtualny widok udziałów, więc host.yaml musi mieć
  `ssh_file_transfer_protocol: scp` (inaczej `files.put` kończy się "No such file").
- Kontenery z CLI compose są widoczne w GUI Container Manager jako kontenery, ale nie jako
  "projekt". Nie klikać w nich w GUI - zmiany poszłyby obok repo.

## Wzorzec: Docker API przez socket-proxy

```yaml
services:
  socket-proxy:
    image: tecnativa/docker-socket-proxy:<tag>
    restart: unless-stopped
    environment:
      CONTAINERS: 1      # GET /containers/*
      EVENTS: 1
      INFO: 1
      VERSION: 1
      PING: 1
      POST: 0            # żadnych zmian przez API
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks: [internal]
    # celowo BEZ ports: proxy widoczne tylko dla kontenerów w sieci internal
  app:
    image: <obraz:tag>
    environment:
      DOCKER_HOST: tcp://socket-proxy:2375   # nazwa zmiennej zależy od aplikacji
    depends_on: [socket-proxy]
    networks: [internal]
networks:
  internal: {}
```
Uzasadnienie do README: kontener z gołym socketem to root na hoście; proxy ogranicza API
do odczytu i wybranych endpointów.

Gdy aplikacja w logach zgłasza `403 Forbidden ... Request forbidden by administrative rules`,
woła endpoint zablokowany w proxy. Kolejność: (1) sprawdź w dokumentacji aplikacji, czy tę
funkcję da się wyłączyć zmienną środowiskową (np. Dozzle: `DOZZLE_IMAGE_CHECK_MODE: off`),
(2) dopiero jeśli funkcja jest potrzebna, otwórz w proxy konkretny endpoint tylko do odczytu
(`IMAGES=1`, `DISTRIBUTION=1`...), nigdy `POST=1`. Decyzję opisz w README stacka.
Przed pierwszym wdrożeniem przejrzyj listę zmiennych aplikacji pod kątem funkcji, które
potrzebują dodatkowych endpointów (sprawdzanie aktualizacji, akcje, shell), i wyłącz zbędne.

## Dokumentacja - lista kontrolna przed "gotowe"

- [ ] README stacka ma wypełnione wszystkie sekcje szablonu (bez `<...>`).
- [ ] "Dla domowników" napisane prostym językiem albo wprost "tylko dla admina".
- [ ] "Dane i backup" mówi, co jest stanem, co cache, i czy backup istnieje.
- [ ] Porty i adresy zgodne z compose i z README hosta.
- [ ] Sekrety: tylko nazwy; plik sops istnieje albo jest w krokach dla użytkownika.
- [ ] `--dry` przejrzane, każda zmiana wyjaśniona.
