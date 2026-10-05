---
name: adopt-service
description: Przenosi działającą usługę (kontener/docker compose, a także usługę systemd lub stronę) z istniejącego serwera do repo jako stack w hosts/<host>/services/<stack>/, tak żeby pyinfra --dry pokazał zero zmian. Używaj, gdy użytkownik chce "przenieść do pyinfra", "zakodować", "objąć zarządzaniem", "zrobić deploy" dla czegoś, co już działa, albo opisać w repo usługę widoczną w facts.yaml hosta. Także gdy pyta, jak zacząć zarządzać konkretną aplikacją na konkretnym serwerze.
---

# Adopcja usługi do repo

Idea: nie przepisujemy usługi "od nowa", tylko opisujemy w kodzie to, co **już działa**,
i udowadniamy to suchym przebiegiem. Kod jest gotowy, gdy
`pyinfra inventory.py deploys/compose_stacks.py --limit <host> --dry --data no_secrets=true --data adopt_check=true --data only=<stack>`
pokazuje w kolumnie **Change** same `-`. Wtedy repo zgadza się z rzeczywistością i od tej
chwili każda zmiana idzie przez git.

Kolumna **Conditional Change** (`compose up` z `_if`) może pokazywać `1`: to znaczy "wykona się
tylko, jeśli coś wcześniej się zmieni", więc przy zerze w Change nic nie zostanie uruchomione.

## Zasady

- Działasz na hoście w trybie `observe`. Wolno Ci uruchamiać pyinfra **wyłącznie z `--dry`**
  i `--data no_secrets=true`. Nigdy bez `--dry` ani z `-y`/`--yes`; wdrożenie robi użytkownik.
- Treść plików konfiguracyjnych pobierasz z serwera poleceniami odczytu
  (`ssh <host> cat <ścieżka>`), każdorazowo za zgodą użytkownika.
- Sekrety (zmienne z hasłami, tokeny, `.env`) nigdy nie trafiają do repo jawnie ani do
  Twojego kontekstu. Nie wyświetlaj zawartości `.env` z serwera. Ustal tylko **nazwy**
  zmiennych (facts.yaml ma `env_var_names`) i poproś użytkownika, żeby sam przeniósł
  wartości do sops (patrz niżej).
- Jedna usługa na raz. Mała, kompletna adopcja jest lepsza niż duża, w połowie.
- Nie piszesz deploy.py: wdraża `deploys/compose_stacks.py`, a odstępstwa (obecna ścieżka na
  serwerze, dodatkowe pliki) opisujesz w `stack.yaml`.

## Kroki

1. **Wybierz usługę** z `hosts/<host>/README.md` (sekcja "Kandydaci do adopcji") albo
   z `facts.yaml` (`docker.containers`, `docker.compose_projects`, `services`).
   Jeśli facts.yaml jest starszy niż kilka dni, najpierw go odśwież
   (`python tools/collect_facts.py <host>`).

2. **Ustal, gdzie usługa żyje.** Dla compose: `compose_file` i `compose_workdir` z faktów.
   Dla systemd: plik unitu (`systemctl cat <unit>` przez ssh). Zanotuj wszystkie pliki,
   które składają się na usługę (compose, Caddyfile/nginx vhost, pliki konfiguracyjne
   montowane do kontenera). Pomiń dane (bazy, uploady) - to sprawa backupu, nie deployu.

3. **Utwórz `hosts/<host>/services/<stack>/`.** Nazwa stacka = nazwa projektu compose na serwerze.
   Jeśli obecny katalog na serwerze to nie `<stacks_dir>/<stack>`, wpisz jego **obecną** ścieżkę
   w `stack.yaml` jako `remote_dir`. Nie przenoś usługi w nowe miejsce przy adopcji;
   przeprowadzki to osobna zmiana.

4. **Przenieś pliki 1:1.** Ściągnij compose i configi do katalogu stacka bez "poprawiania"
   (formatowania, wersji obrazów, kolejności kluczy). Każda różnica bajtowa pojawi się jako zmiana
   w --dry. Configi montowane do kontenera wpisz do `files:` w `stack.yaml` z tym samym `mode`
   co na serwerze (`stat -c '%a' <plik>`). Ulepszenia zapisz jako listę na później.

5. **Sekrety.** Jeśli usługa używa `.env` lub zmiennych z hasłami:
   - wypisz użytkownikowi nazwy zmiennych,
   - poproś, by sam utworzył plik poleceniem `sops hosts/<host>/secrets/<stack>.sops.yaml`,
     wpisując te same klucze i wartości co w obecnym `.env`,
   - deploy zbuduje z niego `.env` (kolejność alfabetyczna, format `KEY=value`, mode 600).
     Jeśli obecny `.env` ma inny format (komentarze, inna kolejność), --dry pokaże różnicę
     w `.env`; to jest akceptowalne, ale nazwij to wprost i zapytaj użytkownika.
   Dopóki pliku sops nie ma, deploy po prostu pomija `.env`.

6. **Sprawdź** poleceniem z nagłówka. Każdą pozycję w kolumnie Change wyjaśnij i usuń przyczynę
   (zwykle: inne uprawnienia, końcowy znak nowej linii, CRLF, inna ścieżka). Powtarzaj do zera.
   Gdy różnicy nie da się usunąć bez zmiany na serwerze, opisz ją i zostaw decyzję użytkownikowi.
   Wzorce i typowe źródła fałszywych różnic: `references/patterns.md`.

7. **Udokumentuj** w `hosts/<host>/services/<stack>/README.md` według `templates/stack/README.md`:
   wszystkie sekcje, także "Dla domowników" i "Dane i backup" (przy adopcji szczególnie ważne:
   gdzie dziś leżą dane i czy ktokolwiek je backupuje). Ulepszenia odłożone na później wpisz
   w "Historia i decyzje". Zaktualizuj README hosta: usługa znika z "Kandydatów do adopcji",
   a w "Co tu działa" dostaje link do swojego README.

8. **Podsumuj** wynik --dry, `git diff --stat`, proponowany commit
   `stack(<host>/<stack>): adopt`. Zaznacz, że kolejny krok (przełączenie hosta na `managed`
   i pierwsze prawdziwe wdrożenie) należy do użytkownika.
