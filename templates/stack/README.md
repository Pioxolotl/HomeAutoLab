# <nazwa stacka>

> Jedno zdanie: co to jest i po co nam. Tak, żeby zrozumiał ktoś, kto nie wie, co to Docker.

| | |
|---|---|
| **Host** | `<inventory_name>` (`hosts/<host>/README.md`) |
| **Stack** | `<remote_dir na serwerze>` · obrazy: `<obraz:tag>`, `<obraz:tag>` |
| **Adres** | `http://<ip>:<port>` (LAN) · docelowo `https://<nazwa>.<domena>` |
| **Stan** | planowana / działa od <data> / wyłączona <data> |
| **Dla domowników** | tak - <kto i do czego> / nie, tylko admin |
| **Dane krytyczne** | nie / tak: <co dokładnie, np. baza zdjęć> |
| **Backup** | brak / <gdzie, jak często> (szczegóły niżej) |
| **Sekrety** | brak / `hosts/<host>/secrets/<stack>.sops.yaml` (klucze: `NAZWA_1`, `NAZWA_2`) |

## Po co i dlaczego tak

- **Problem:** co było niewygodne lub niemożliwe bez tej usługi.
- **Dlaczego to narzędzie:** jedno-dwa zdania; jakie alternatywy odrzucono i czemu.
- **Decyzje architektoniczne:** każda nieoczywista rzecz w compose z uzasadnieniem
  (np. "Docker API przez socket-proxy, a nie goły socket, bo kontener z socketem = root na hoście").

## Jak działa

- **Kontenery:** `<nazwa>` - rola; `<nazwa>` - rola. Kto z kim rozmawia (tekstowy schemat wystarczy).
- **Sieć:** porty wystawione na host (`<ip>:<port> → kontener:<port>`) i dlaczego na tym adresie;
  sieci compose; co NIE jest wystawione i celowo.
- **Od czego zależy:** inne usługi, DNS, reverse proxy, zewnętrzne API, zmienne z sekretów.
- **Na co wpływa:** co przestanie działać, gdy ta usługa padnie. Jeśli nic - napisz to.

## Dla domowników

Prostym językiem, bez żargonu. Trzy akapity maksimum:

1. **Jak wejść:** adres, czym się logować (hasło jest w <menedżer haseł / kartka>).
2. **Co tu można zrobić:** dwa-trzy zdania.
3. **Gdy nie działa:** (a) odśwież stronę za minutę, (b) sprawdź, czy serwer świeci, (c) napisz do <kto>.
   Nie restartuj serwera, jeśli nie prosimy.

Jeśli usługa jest tylko dla admina, napisz: "Tylko dla admina. Dla domowników niewidoczna,
jej awaria niczego domowego nie psuje."

## Instrukcja techniczna

### Pierwsze uruchomienie
Kroki od zera do działającej usługi, w kolejności, z poleceniami. Co trzeba przygotować ręcznie
(sekrety w sops, reguła reverse proxy w GUI, konto), a co robi pyinfra.

### Wdrożenie i aktualizacja
```bash
pyinfra inventory.py deploys/compose_stacks.py --limit <host> --dry --data only=<stack>   # podgląd
pyinfra inventory.py deploys/compose_stacks.py --limit <host> --data only=<stack>         # wdrożenie (człowiek)
```
Aktualizacja obrazu = zmiana tagu w `compose.yaml` + commit + wdrożenie. Co sprawdzić po aktualizacji.

### Konfiguracja i sekrety
Gdzie jest konfiguracja (plik, zmienne), **nazwy** sekretów i jak je zmienić
(`sops hosts/<host>/secrets/<stack>.sops.yaml`, potem wdrożenie). Wartości nigdy tutaj.

### Logi i stan
Jak zajrzeć w logi (Dozzle / `docker logs`), jak sprawdzić, że działa (adres healthchecka, co ma zwrócić).

## Dane i backup

- **Gdzie leżą dane:** katalogi/wolumeny z podziałem na *stan* (trzeba backupować) i *cache*
  (można skasować, odbuduje się).
- **Co i jak backupujemy:** mechanizm, częstotliwość, gdzie ląduje kopia. Jeśli brak - napisz
  wprost "BRAK BACKUPU" i dlaczego to akceptowalne (albo odeślij do `hosts/<host>/TODO.md`).
- **Jak odtworzyć:** procedura krok po kroku. **Ostatni test odtworzenia:** <data> / nigdy.

## Troubleshooting

| Objaw | Prawdopodobna przyczyna | Co zrobić |
|---|---|---|
| strona nie odpowiada | kontener nie działa | `docker ps -a`, logi, `compose up` przez pyinfra |
| ... | ... | ... |

## Historia i decyzje

- <data>: utworzono; dlaczego teraz, w jakim wariancie.
- <data>: zmiana X, bo Y.
