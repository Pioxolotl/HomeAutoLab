# TODO: homelab-nas

Zadania dotyczące tej maszyny, wynikające z inwentaryzacji i decyzji. Kolejność = priorytet.
Odhacza użytkownik; Claude dopisuje i uzgadnia z faktami. Sprawy repo i narzędzi: `/TODO.md`.

## Do zrobienia

- [ ] **Zamknąć SSH NAS-a od strony internetu.** Router przekierowuje 22100 → 192.168.50.100, a sshd
  przyjmuje hasła. Docelowo: usunąć regułę "Ssh" z routera i wchodzić przez WireGuard na routerze
  (51820). Decyzja 2026-10-04: **zostaje tymczasowo**, do czasu ogarnięcia dostępu zdalnego.
  W międzyczasie w DSM: auto-blokada + ochrona konta + 2FA (Panel sterowania → Bezpieczeństwo).
- [ ] **Backup poza NAS.** Dziś są tylko snapshoty btrfs (Snapshot Replication) na tym samym
  sprzęcie; Hyper Backup nie jest zainstalowany, nie ma rclone/restic/borg. Snapshoty nie chronią
  przed awarią NAS-a, kradzieżą, pożarem ani ransomware z kontem admina.
  Opcje: Hyper Backup na dysk USB (najtańsze, offline), Hyper Backup / rclone do chmury
  (Backblaze B2, Hetzner Storage Box), drugi NAS u rodziny przez WireGuard/VPN.
  Zacząć od tego, co boli najbardziej przy utracie: zdjęcia (Synology Photos) i udział `backups`.
- [ ] (niski priorytet) Zdalny dostęp supportu Synology: w DSM 7 to aplikacja "Centrum pomocy
  technicznej" / "Support Center" w Menu głównym, nie w Panelu sterowania. Jeśli jej nie ma,
  temat pominąć: dostęp i tak wymaga ręcznego włączenia i klucza ze zgłoszenia.
- [ ] (opcjonalnie) `pkg-SynoAnalytics-analyzer.service` jest failed od restartu 2026-10-04 -
  telemetria Synology; zignorować albo wyłączyć pakiet SynoAnalytics.

## Zrobione

- [x] Pozostałości w `/volume1/docker` (`_old`, `.env` z lipca) usunięte (2026-10-05, wg użytkownika;
  do potwierdzenia przy następnym odświeżeniu faktów).
- [x] Martwe przekierowania na routerze usunięte (2026-10-04): 80→81, 443→444. Zostawione celowo:
  25500-25502 (Minecraft w przyszłości) i WireGuard 51820 → router.
- [x] NFS wyłączony (2026-10-04) - dyski Y:/Z: to SMB, nic nie przestało działać, porty NFS zniknęły.
- [x] iSCSI wyłączony wg użytkownika (2026-10-04). Fakty z sudo o 23:56 jeszcze pokazywały porty
  3261-3265 - do potwierdzenia przy następnym `collect_facts.py homelab-nas --sudo`.
- [x] Konto `admin` w DSM wyłączone - sprawdzone (`Expired: true`, 2026-10-04).
- [x] Tailscale odinstalowany z NAS (2026-10-04) - był nieużywany; `tun1000` zniknął razem z nim.
- [x] Strefa czasowa DSM ustawiona (2026-10-04) - wpis "Sarajevo, Skopje, Warsaw, Zagreb",
  czyli Europe/Sarajevo; identyczne reguły co Warszawa, DSM nie ma osobnego wpisu Warsaw.
