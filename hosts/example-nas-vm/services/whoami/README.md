# whoami

> Testowa strona, która wypisuje nagłówki żądania. Służy do sprawdzenia, czy wdrażanie stacków działa.

| | |
|---|---|
| **Host** | `example-nas-vm` (`hosts/example-nas-vm/README.md`) |
| **Stack** | `/opt/whoami` · obrazy: `traefik/whoami:v1.10` |
| **Adres** | `http://192.168.0.10:8081` (LAN) |
| **Stan** | przykład, nie wdrażany (host ma `disabled: true`) |
| **Dla domowników** | nie, tylko admin |
| **Dane krytyczne** | nie |
| **Backup** | niepotrzebny - usługa bezstanowa |
| **Sekrety** | brak |

## Po co i dlaczego tak
- **Problem:** potrzebny najprostszy możliwy stack do testu ścieżki repo → pyinfra → serwer.
- **Dlaczego to narzędzie:** jeden kontener, bez konfiguracji, bez danych.
- **Decyzje:** port na adresie LAN, nie 0.0.0.0, zgodnie z zasadą dla wszystkich stacków.

## Jak działa
- **Kontenery:** `whoami` - serwer HTTP odpowiadający swoim hostname i nagłówkami.
- **Sieć:** `192.168.0.10:8081 → whoami:80`. Nic więcej.
- **Od czego zależy:** nic. **Na co wpływa:** nic.

## Dla domowników
Tylko dla admina. Dla domowników niewidoczna, jej awaria niczego domowego nie psuje.

## Instrukcja techniczna
### Pierwsze uruchomienie
1. Host w `managed`. 2. `pyinfra inventory.py deploys/compose_stacks.py --limit example-nas-vm --data only=whoami`.
### Wdrożenie i aktualizacja
Zmiana tagu w `compose.yaml`, commit, polecenie jak wyżej. Test: `curl http://192.168.0.10:8081`.
### Konfiguracja i sekrety
Brak.
### Logi i stan
`docker logs whoami-whoami-1`; kod 200 na adresie wyżej.

## Dane i backup
Bezstanowa. Nic do backupu.

## Troubleshooting
| Objaw | Przyczyna | Co zrobić |
|---|---|---|
| connection refused | kontener nie wstał / zły adres IP w `ports` | `docker ps -a`, sprawdź IP hosta w `hosts/<host>/facts.yaml` |

## Historia i decyzje
- 2026-10-05: utworzono jako przykład układu `hosts/<host>/services/<stack>/`.
