---
name: diagnose-host
description: Diagnozuje problemy na serwerach z repo infra (nie działa strona, kontener się restartuje, brak miejsca, usługa padła, wolno działa, nie da się połączyć) w trybie tylko do odczytu i proponuje naprawę jako zmianę w kodzie lub jasną instrukcję. Używaj zawsze, gdy użytkownik zgłasza awarię, błąd, "coś nie działa", pyta "co się dzieje z ..." albo prosi o sprawdzenie stanu maszyny lub usługi.
---

# Diagnoza hosta

Działasz jak dyżurny admin, który najpierw patrzy, potem mówi, a naprawia dopiero
za zgodą. Każde polecenie na serwerze to odczyt; użytkownik zatwierdza je pojedynczo,
więc pisz krótko, po co jest każde.

## Kontekst przed dotknięciem serwera

1. Przeczytaj `hosts/<host>/README.md`, `TODO.md` i `facts.yaml` (rola, usługi, porty, znane ryzyka,
   świadome decyzje - np. port wystawiony celowo).
2. Sprawdź historię zmian: `git log --oneline -15 -- hosts/<host>`
   Wiele awarii zaczyna się od ostatniego wdrożenia.
3. Jeśli problem dotyczy konkretnego stacka, przeczytaj `hosts/<host>/services/<stack>/README.md`,
   zwłaszcza "Troubleshooting" i "Dane i backup".

## Zbieranie objawów (przez `ssh <host> '<polecenie>'`)

Zaczynaj od ogółu, zawężaj według wyników. Typowe polecenia odczytu:

- stan ogólny: `uptime`, `df -h`, `free -m`, `systemctl --failed --no-pager`
- usługa systemd: `systemctl status <unit> --no-pager`, `journalctl -u <unit> -n 100 --no-pager`
- kontenery: `docker ps -a --format '{{.Names}} {{.Status}}'`, `docker logs --tail 100 <kontener>`,
  `docker inspect -f '{{.State.Status}} {{.State.ExitCode}} {{.RestartCount}}' <kontener>`
- sieć: `ss -tulnp` (albo `netstat -tulnp` tam, gdzie nie ma `ss`),
  `curl -sS -o /dev/null -w '%{http_code}' http://localhost:<port>`
- dziennik systemu: `journalctl -p err -n 50 --no-pager`, `dmesg -T | tail -50`

Platformy: na Synology DSM Docker jest pod `/var/packages/ContainerManager/target/usr/bin/docker`
i wymaga sudo z hasłem - polecenia dockerowe podaj użytkownikowi do uruchomienia zamiast
wykonywać je samemu; `host.yaml` mówi, czy host tak działa (`docker_sudo`).

Nie używaj `docker inspect` bez `-f` ani `docker exec ... env`: pełny inspect zawiera
zmienne środowiskowe z hasłami. W logach, które pokazujesz, maskuj wszystko, co wygląda
na sekret.

Jeśli przydatne jest odświeżenie całości: `python tools/collect_facts.py <host>`
i `git diff hosts/<host>/facts.yaml`.

## Raport

Odpowiedz w tej kolejności:
1. **Co się dzieje** - jedno, dwa zdania.
2. **Dowody** - najważniejsze linie z logów/poleceń (krótko).
3. **Przyczyna** - pewna albo najbardziej prawdopodobna, z poziomem pewności.
4. **Naprawa** - preferuj zmianę w repo (`hosts/<host>/services/<stack>/`, `deploys/`), którą
   użytkownik wdroży przez pyinfra; jeśli potrzebna jest jednorazowa akcja na serwerze (restart,
   czyszczenie miejsca), podaj dokładne polecenie do wykonania przez użytkownika i oceń ryzyko.
5. **Zapobieganie** - co dodać do monitoringu, backupu lub kodu, żeby się nie powtórzyło.
   Jeśli diagnoza ujawniła nową wiedzę o usłudze, dopisz ją do "Troubleshooting" w README stacka.

## Czego nie robisz

- Nie restartujesz, nie usuwasz, nie edytujesz plików na serwerze, nie uruchamiasz
  pyinfra bez `--dry`. Nawet przy oczywistej naprawie: proponujesz, nie wykonujesz.
- Nie zgadujesz przy braku danych. Gdy czegoś nie da się sprawdzić odczytem, powiedz to.
- Hosty z `owner: brother` traktujesz z dodatkową ostrożnością: proponuj rozwiązanie,
  ale przypomnij, że to nie jest wyłącznie maszyna użytkownika.
