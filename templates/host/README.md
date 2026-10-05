# <nazwa hosta>

**Rola:** <jedno zdanie>
**Właściciel:** <me/brother> · **Tryb:** observe · **Dostęp:** `<user>@<alias ssh>` (→ <ip>:<port>, klucz `~/.ssh/<nazwa>`)
**System:** <dystrybucja/wersja, kernel, arch, hostname> · **Zasoby:** <CPU, RAM, dyski z zajętością, GPU> · **Ostatni restart:** <data>

## Co tu działa
<usługi systemd i kontenery pogrupowane wg funkcji; dla stacków z repo: link do
`services/<stack>/README.md`; dla rzeczy spoza repo: obraz, porty, ścieżka compose>

## Sieć
<interfejsy i adresy (tabela); porty nasłuchujące na 0.0.0.0 z procesem; porty tylko na localhost;
tabela przekierowań z routera, jeśli host jest za NAT - z oceną każdej reguły (żywa/martwa/celowa)>

## Dane i backup
<udziały/wolumeny/katalogi z danymi; co jest stanem, a co cache; mechanizm backupu albo wprost "brak">

## Ryzyka i rzeczy do uwagi
<ponumerowane, od najpoważniejszego; na końcu "Sprawdzone i OK: ..." z datami>

## Kandydaci do adopcji
<usługi działające poza repo, które warto przenieść skillem adopt-service, od najłatwiejszej>

## Odświeżanie faktów
<jak odświeżać na tym hoście: zwykłe polecenie, czy potrzebny --sudo, kto je uruchamia>

## Otwarte pytania
<rzeczy, których nie da się ustalić z faktów; "Brak na dziś", gdy pusto>
