# homelab-nas

Zadania tej maszyny: [TODO.md](TODO.md). Stacki: `services/<stack>/` (dziś brak).

**Rola:** Synology DS923+ (DSM 7.3.2): zdjęcia (Synology Photos), pliki (Drive, SMB), backupy
i miejsce na kilka usług w Container Manager. Włączony 24/7, mały pobór prądu.
**Właściciel:** me · **Tryb:** observe · **Dostęp:** `pioxolotl@homelab-nas` (alias w `~/.ssh/config`
→ 192.168.50.100:22100, klucz `~/.ssh/homelab_nas`; sudo wymaga hasła, patrz "Odświeżanie faktów")
**System:** DSM 7.3.2-86009 Update 4 (build 2026-06-18), kernel 4.4.302+, x86_64, hostname `nas`,
strefa czasowa: wpis DSM "Sarajevo, Skopje, Warsaw, Zagreb" = Europe/Sarajevo (te same reguły
CET/CEST co Warszawa; DSM nie ma osobnego Europe/Warsaw). Ustawione 2026-10-04.
**Zasoby:** AMD Ryzen Embedded R1600 (4 wątki), 32 GB RAM (ok. 27 GB wolne), swap 21 GB;
volume1 1,8 TB btrfs (73 % zajęte, 485 GB wolne), volume2 3,5 TB btrfs (27 % zajęte, 2,6 TB wolne),
oba wolumeny przez `cachedev_*` (SSD cache). Bez GPU. Ostatni restart: 2026-10-04 22:19
(wcześniej uptime ok. 87 dni).

## Co tu działa

Wszystko poniżej to pakiety DSM, nie własne usługi. Container Manager (Docker przez
`/var/packages/ContainerManager/target/usr/bin/docker`) jest **pusty**: zero kontenerów, zero
projektów compose, zero wolumenów, tylko domyślne sieci bridge/host/none (sprawdzone z sudo 2026-10-04).

**Pliki i zdjęcia**
- Synology Photos (apid, face/concept detection, geocoding, thumbnails) - zdjęcia
- Synology Drive (apid, syncd, redis) - port 6690
- SMB/CIFS (synosamba, WS-Discovery 5357, NetBIOS 137-139) - udziały dla Windows/macOS
- ~~NFS~~ - **wyłączony 2026-10-04** (był nieużywany: dyski Y:/Z: na komputerze użytkownika to SMB
  `\\nas\homes` i `\\nas\data`, Windows nie ma klienta NFS). Porty 2049/111/662/892/4045 i rpcbind zniknęły
- iSCSI target (ScsiTarget, 3261-3265 na IPv6) - udostępnia "wirtualny dysk" po sieci, używane
  głównie pod VM-ki/hypervisory. **Prawdopodobnie nieużywany**, demon DSM działa domyślnie (TODO)
- File Station, Universal Viewer, SynoFinder (indeksowanie)

**Backup i replikacja**
- Snapshot Replication + Replication Service (`synobtrfsreplicad`, TCP 5566 na IPv6) - snapshoty btrfs
- `synobackupd` - systemowy demon backupu DSM
- **Hyper Backup nie jest zainstalowany**; backupu poza NAS nie ma (potwierdzone, patrz TODO)

**Platforma i dostęp**
- Container Manager (dockerd, event-watcher, termd) - Docker, obecnie zero kontenerów
- ~~Tailscale~~ - **odinstalowany 2026-10-04** (był nieużywany). Razem z nim zniknął interfejs
  `tun1000`, który tworzył `tailscaled`, oraz porty UDP 41641 i TCP 32906
- QuickConnect + synorelayd - zdalny dostęp przez relay Synology; używany celowo (telefony)
- SecureSignIn, OAuthService, SynologyApplicationService (pgbouncer, push)
- nginx DSM (80/443, 5000/5001, 5357); `server.ReverseProxy.conf` ma 1 bajt - **brak reguł reverse proxy**
- PostgreSQL (127.0.0.1:5432) i Redis - wewnętrzne bazy pakietów DSM
- `synovpnclient` - wbudowana usługa DSM (klient VPN z Panelu sterowania), działa na każdym DSM
  niezależnie od konfiguracji; użytkownik niczego tu nie konfigurował
- `findhostd` (UDP 9997-9999) - wykrywanie NAS przez Synology Assistant w LAN
- SNMP (161 tylko na localhost), ActiveInsight, SupportService (sam demon jest standardowy;
  realny zdalny dostęp supportu działa tylko po ręcznym włączeniu w Centrum pomocy technicznej)
- Runtime: Git, Node.js 18/20/22, Python 2 i 3.14 (pakiety), `/usr/bin/python3` w systemie

## Sieć

| Interfejs | Adres | Uwagi |
|---|---|---|
| eth0 | 192.168.50.100 (statyczny) | LAN, główny |
| eth1 | 169.254.208.205 | link-local, kernel zgłasza `linkdown` - kabel niepodpięty (potwierdzone) |
| docker0 | 172.17.0.1 | mostek Dockera |

Porty nasłuchujące na `0.0.0.0` (wszystkie interfejsy, stan z sudo 2026-10-04 23:56): 22100 (SSH),
80/443 (nginx DSM), 5000/5001 (DSM), 445/139 (SMB), 6690 (Drive), 5357 (WS-Discovery),
3261-3265 IPv6 (iSCSI), 5566 IPv6 (replikacja btrfs); UDP: 137/138 (NetBIOS), 1900/3702/5353
(SSDP, WS-Discovery, mDNS), 9997-9999 (Synology Assistant), 123 (NTP) oraz kilka losowych wysokich
portów UDP (avahi/dhclient). Tylko localhost: 5432 (PostgreSQL), 161 (SNMP), 512 (termd),
323 (chrony), 33304 (synomibaction).

**Przekierowania portów na routerze** (ASUS, stan ze zrzutu 2026-10-04):

| Nazwa | Port zewn. | Port wewn. | Cel | Proto | Ocena |
|---|---|---|---|---|---|
| ~~ubuntudocker~~ | 80 | 81 | 192.168.50.100 | TCP | **usunięte 2026-10-04** (martwe) |
| ~~ubuntudockers~~ | 443 | 444 | 192.168.50.100 | TCP | **usunięte 2026-10-04** (martwe) |
| mc | 25500-25502 | (te same) | 192.168.50.100 | TCP | dziś nic nie nasłuchuje; **zostawione celowo** pod przyszły Minecraft |
| wireguard | 51820 | 51820 | 192.168.50.1 | UDP | serwer WireGuard na routerze, nie dotyczy NAS |
| Ssh | 22100 | (ten sam) | 192.168.50.100 | TCP | **SSH NAS wystawione do internetu** - patrz ryzyka |

Reguła "mc" to świadoma mina na przyszłość: gdy na NAS wystartuje cokolwiek na 25500-25502,
będzie od razu publiczne. Przy stawianiu serwera Minecraft pamiętać o tym w jego README.

## Dane i backup

Udziały: `/volume1/{backups,docker,homes,shared}` oraz `/volume2/data`. W `/volume1/docker` leżą
dziś tylko pozostałości: katalog `_old` i plik `.env` z lipca (treści nie czytałem - może zawierać
sekrety; do przejrzenia i sprzątnięcia przez użytkownika). Container Manager montuje
wszystkie pięć pod `/volume1/@appdata/ContainerManager/all_shares/`, czyli kontenery mają do nich
dostęp. volume1 (1,8 TB) zapełniony w 73 %, volume2 (3,5 TB) w 27 %.

Backup: tylko Snapshot Replication (snapshoty btrfs na tym samym NAS) i udział `backups` jako cel
backupów z innych maszyn. **Backupu poza NAS nie ma** - potwierdzone przez użytkownika, zadanie w TODO.

## Ryzyka i rzeczy do uwagi

1. **SSH NAS-a (22100) jest wystawione do internetu**, a sshd przyjmuje logowanie hasłem
   (`Permission denied (publickey,password)` przy pierwszej próbie). Boty skanują wysokie porty
   równie chętnie jak 22. Zalecenie: usunąć to przekierowanie i wchodzić przez WireGuard na routerze
   (już jest, 51820). Jeśli ma zostać: w DSM auto-blokada, ochrona konta i 2FA
   na wszystkich kontach administratorów.
2. **Brak backupu poza NAS.** Snapshoty nie chronią przed awarią sprzętu, pożarem, kradzieżą ani
   ransomware z kontem admina. Zadanie w TODO.
3. **Przekierowanie 25500-25502** do NAS zostawione celowo (Minecraft w przyszłości); martwe
   80→81 i 443→444 usunięte 2026-10-04.
4. **QuickConnect** - używany celowo (telefony), więc nie błąd, tylko powierzchnia ataku do
   pilnowania: 2FA, SecureSignIn, blokada po nieudanych logowaniach. Po odinstalowaniu Tailscale
   to jedyna droga zdalna do DSM poza WireGuardem na routerze.
5. **iSCSI** - wg użytkownika wyłączony 2026-10-04; fakty z sudo o 23:56 jeszcze pokazywały porty
   3261-3265, więc do potwierdzenia przy następnym przebiegu z `--sudo`. NFS już wyłączony.
6. **volume1 w 73 %** - jeszcze nie krytycznie; ponad 90 % btrfs zacznie boleć.
7. **Zdalny dostęp supportu Synology** - sam demon jest normalny, a realny dostęp wymaga, żeby
   użytkownik sam włączył go i podał klucz ze zgłoszenia do Synology. Niski priorytet.
8. `pkg-SynoAnalytics-analyzer.service` w stanie **failed** (od restartu 2026-10-04). To telemetria
   Synology, nie wpływa na dane ani usługi; jeśli przeszkadza, pakiet SynoAnalytics można wyłączyć.

Sprawdzone i OK: konto `admin` wyłączone (`Expired: [true]`), brak reguł reverse proxy, strefa
czasowa zgodna z Polską, za każdym otwartym portem stoi znany proces DSM, NAS zrestartowany po
Update 4 (2026-10-04), NFS i Tailscale usunięte z powierzchni ataku.

## Kandydaci do adopcji

Obecnie nic nie działa w Dockerze, więc nie ma czego adoptować. Pakietów DSM (Photos, Drive, SMB)
pyinfra nie powinno dotykać - to domena GUI DSM.

Kolejność na przyszłość:
1. Nowe usługi od razu jako `hosts/homelab-nas/services/<stack>/` (wdraża `deploys/compose_stacks.py`
   do `/volume1/docker/<stack>`), nie przez GUI. Pierwszy kandydat: Dozzle przez socket-proxy.
2. Dopiero potem ewentualne przejęcie tego, co powstanie "ręcznie".

## Odświeżanie faktów

- `python tools/collect_facts.py homelab-nas` (Claude może to uruchomić sam) - wszystko poza
  kontenerami i procesami za portami. Sekcje wymagające sudo są wtedy **przepisywane z poprzedniego
  pliku** i oznaczone w `_meta.sudo_facts_preserved_from`, żeby nie zniknęły.
- `python tools/collect_facts.py homelab-nas --sudo` (uruchamia **użytkownik**, pyinfra pyta o hasło
  w terminalu) - pełny obraz. Claude nie ma hasła i nie powinien go mieć, dlatego sam tego nie
  uruchomi; `sudo: false` w host.yaml zostaje. Na NAS zostaje jedynie skrypt `pyinfra-sudo-askpass-*`
  w katalogu domowym (bez hasła w środku); `/tmp` DSM jest `noexec`, stąd `temp_dir` w host.yaml.

## Otwarte pytania

- Brak na dziś. Nowe pytania dopisywać tutaj.
