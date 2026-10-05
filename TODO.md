# TODO (repo i narzędzia)

Sprawy wspólne: repo, narzędzia, skille, proces. Zadania dotyczące konkretnej maszyny są w jej
katalogu: `hosts/<host>/TODO.md` (np. [homelab-nas](hosts/homelab-nas/TODO.md)).

## Do zrobienia

- [ ] **Środowisko sekretów:** zainstalować `sops` i `age`, wygenerować klucz age, wpisać klucz
  publiczny do `.sops.yaml` (dziś placeholder). Polecenia: README, sekcja "Start". Bez tego nie
  da się wdrożyć żadnego stacka z sekretami.
- [ ] Pierwszy stack w nowym układzie (`hosts/<host>/services/<stack>/`): Dozzle przez socket-proxy.
- [ ] Gdy pojawi się drugie repo infra (pierwszy klient): wydzielić `.claude/skills/`, `tools/`
  i `templates/` do osobnego repo jako plugin Claude Code, żeby jedna wersja skilli służyła
  wszystkim repo. Do tego czasu pilnować, że te trzy katalogi nie wiedzą nic o konkretnych hostach.
- [ ] Automatyzacja wdrożeń (runner z kluczem SSH i kluczem age "deployer"). Otwarte: sudo na
  Synology wymaga hasła - hasło w sekrecie CI albo konto z NOPASSWD tylko na `docker-compose`.
  Świadoma decyzja na później.
- [ ] `deploys/`: wspólne role (base, backup, monitoring), gdy będzie więcej niż jeden host managed.
