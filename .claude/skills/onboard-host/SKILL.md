---
name: onboard-host
description: Dodaje nową lub istniejącą maszynę do repo infra - sprawdza połączenie SSH, zbiera fakty przez pyinfra (tylko odczyt), tworzy hosts/<nazwa>/host.yaml, README.md i TODO.md z opisem roli, usług i ryzyk. Używaj zawsze, gdy użytkownik chce dodać serwer, VM, NAS, Raspberry Pi, VPS albo "zobaczyć, co jest na maszynie", zinwentaryzować ją, odświeżyć jej dane lub zacząć nią zarządzać pyinfra - nawet jeśli nie pada słowo "onboard".
---

# Onboarding hosta

Cel: zamienić "jakąś maszynę, do której mam SSH" w opisany, wersjonowany katalog
`hosts/<nazwa>/`, bez zmieniania czegokolwiek na samej maszynie. Najpierw dokumentujemy
rzeczywistość, dopiero potem (skillami `adopt-service` / `new-service`) przenosimy ją do kodu.

## Zasady, których pilnujesz

- Na hoście wykonujesz wyłącznie polecenia odczytu. `tools/collect_facts.py` jest
  zaprojektowany jako read-only; nie uruchamiaj na hoście niczego, co zapisuje,
  restartuje albo instaluje. Jeśli czegoś brakuje do diagnozy, zapytaj użytkownika.
- Nowy host zawsze dostaje `managed: observe`. Przełączenie na `managed` to świadoma
  decyzja użytkownika, nie Twoja.
- Serwery klientów nie trafiają do tego repo. Jeśli z rozmowy lub faktów wynika, że
  to maszyna klienta, zatrzymaj się i zaproponuj osobne repo (np. `klient-x-infra`).
- Nie zapisuj w repo haseł ani tokenów. Gdy w facts.yaml zobaczysz coś, co wygląda
  na sekret, którego redakcja nie złapała, usuń to z pliku i powiedz użytkownikowi.
- Nie obniżaj bezpieczeństwa hosta dla wygody zbierania faktów (NOPASSWD itp.).
- Wiedza o maszynie trafia do `hosts/<nazwa>/`. Wiedza o platformie (DSM, Proxmox, HAOS),
  która przyda się następnym hostom, trafia do tego skilla albo do `tools/collect_facts.py`.

## Kroki

1. **Ustal dane.** Potrzebujesz: krótkiej nazwy (kebab-case, np. `nas-vm`,
   `proxmox-brat`, `pi5-ha`), adresu SSH (alias z `~/.ssh/config`, nazwa MagicDNS
   z Tailscale albo IP), użytkownika, właściciela (`me` / `brother`) i jednego zdania
   o roli. Czego nie wiesz, o to zapytaj jednym pytaniem zbiorczym.

2. **Sprawdź połączenie** bez interakcji:
   `ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new <adres> true`
   (`accept-new` jest potrzebne przy pierwszym kontakcie, inaczej BatchMode odrzuci
   nieznany klucz hosta). Gdy się nie uda, pomóż w diagnozie (klucz w agencie,
   `~/.ssh/config`, VPN, użytkownik) zamiast próbować haseł.
   - Gdy użytkownik podał IP/port/usera, dopisz alias do `~/.ssh/config` i użyj go
     jako `ssh_host` - host.yaml zostaje czytelny, a port/klucz są w jednym miejscu.
   - `Permission denied (publickey,password)` = na hoście nie ma klucza. Wygeneruj
     dedykowany klucz (`ssh-keygen -t ed25519 -N "" -f ~/.ssh/<nazwa>`), nie czytaj
     go, a użytkownikowi podaj polecenie wgrywające klucz publiczny (to on wpisze
     hasło). Na Windows nie ma `ssh-copy-id`; użyj `ssh ... "mkdir -p ~/.ssh && echo '<klucz pub>'
     >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"`.
   - Platforma Synology DSM: przez SSH logują się tylko konta z grupy administrators; klucz
     zadziała tylko, gdy katalog domowy ma uprawnienia 755 lub ciaśniejsze (`chmod 755 ~`),
     a usługa "User Home" jest włączona. `sudo` pyta o hasło, więc `sudo: false`.
   - Synology DSM ma `/tmp` zamontowany `noexec`, a pyinfra kładzie tam skrypt askpass,
     którego sudo musi uruchomić. Objaw: `--sudo` pyta o hasło w kółko mimo poprawnego
     hasła. Rozwiązanie: `temp_dir: /var/services/homes/<user>` w host.yaml (sprawdź
     `mount | grep -E " /tmp | /volume1 "` - katalog docelowy nie może mieć `noexec`).
   - Synology DSM: SFTP pokazuje udziały jako `/docker`, `/homes`, `/home` zamiast `/volume1/...`
     (sprawdź: `printf 'ls /
' | sftp -b - <alias>`). pyinfra domyślnie wgrywa pliki przez SFTP
     i dostaje "No such file". Rozwiązanie: `ssh_file_transfer_protocol: scp` w host.yaml.

3. **Utwórz `hosts/<nazwa>/host.yaml`** według wzoru z `hosts/example-nas-vm/host.yaml`
   (bez linii `disabled`). `managed: observe`. `sudo: true` tylko wtedy, gdy użytkownik
   potwierdzi sudo bez hasła. Wypełnij dane dla deployów: `stacks_dir`, `docker_sudo`,
   `compose_bin` (Synology: `/volume1/docker`, `true`,
   `/var/packages/ContainerManager/target/usr/bin/docker-compose`; typowy Linux: `/opt`,
   zależnie od grupy docker, `docker compose`).

4. **Zbierz fakty:** `python tools/collect_facts.py <nazwa>` (Python z `.venv` repo,
   patrz CLAUDE.md). Skrypt zapisze `hosts/<nazwa>/facts.yaml` i wypisze podsumowanie.
   Sporo "brakujących faktów" jest normalne na Synology DSM, Home Assistant OS
   i minimalnych kontenerach. Opisz to w README, nie próbuj obchodzić.
   - `docker.containers: null` znaczy "brak danych" (zwykle brak sudo), `[]` to zero kontenerów.
     Gdy sudo wymaga hasła, NIE proponuj NOPASSWD: poproś użytkownika, żeby sam uruchomił
     `python tools/collect_facts.py <nazwa> --sudo` w swoim terminalu - pyinfra zapyta o hasło,
     Ty go nie widzisz. Przebieg bez sudo przepisuje sekcje sudo-only z poprzedniego pliku
     i oznacza to w `_meta.sudo_facts_preserved_from` - w README pisz, z której daty są.
   - Przy nieznanych portach/interfejsach najpierw poszukaj w sieci, zamiast odsyłać użytkownika.
   - Poproś o zrzut listy przekierowań portów z routera - to jedyne źródło wiedzy, co jest
     wystawione do internetu; porównaj z nasłuchującymi portami i oznacz reguły jako
     żywe / martwe / celowe (decyzja użytkownika).
   - Gdy fakty mają lukę, którą da się zamknąć poleceniem tylko do odczytu, dopisz fallback
     w `READONLY_COMMANDS` w `tools/collect_facts.py` zamiast dłubać ręcznie - następny host skorzysta.

5. **Napisz `hosts/<nazwa>/README.md` i `TODO.md`** według `templates/host/`. Wnioskuj z danych,
   ale oddzielaj fakty od przypuszczeń ("potwierdzone <data>", "prawdopodobnie", "do potwierdzenia").
   Ryzyka numeruj od najpoważniejszego; każde ryzyko, które wymaga działania, ma pozycję w TODO.

6. **Zaproponuj grupy** do `groups:` w host.yaml (np. `docker`, `synology`, `family`, `web`,
   `gpu`, `proxmox`, `homeassistant`, `public`) i dopisz je; użytkownik może zmienić.

7. **Sprawdź inventory:** `pyinfra inventory.py debug-inventory` powinno pokazać
   nowego hosta z poprawnymi grupami i danymi. Polskie znaki w `role` wyświetlą się jako
   `ę` itp. - to normalne (JSON), błąd to dopiero `Ä™` (cp1250).

8. **Pokaż `git diff --stat`**, wypunktuj ryzyka i zaproponuj komunikat commita
   w stylu `host(<nazwa>): onboarding`. Commit robi użytkownik albo Ty po jego zgodzie.

## Odświeżanie

Przy prośbie o odświeżenie istniejącego hosta uruchom tylko krok 4, potem porównaj
`git diff hosts/<nazwa>/facts.yaml` i opisz istotne zmiany (nowe/zniknięte kontenery,
porty, usługi, zajętość dysków, failed). README i TODO aktualizuj tam, gdzie zmiany tego
wymagają - w tym samym kroku, nie "później". Gdy użytkownik mówi, że coś zmienił na hoście
(wyłączył usługę, usunął regułę), odnotuj to w TODO jako zrobione z datą i dopisz
"do potwierdzenia przy następnym odświeżeniu", dopóki fakty tego nie pokażą.
Wszystkie hosty naraz: `python tools/collect_facts.py --all`.
