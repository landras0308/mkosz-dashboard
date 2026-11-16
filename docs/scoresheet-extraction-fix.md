# Jegyzőkönyv-kiolvasás: a kimaradó játékossorok, a kétszer számolt faultok és a javításuk

Andris forkja, 2026-11-16. Dani `mkosz-scoresheet` repójának kiolvasójáról
(`extract_scoresheet.py`), és arról, hogyan kerüli meg a fork a hibát úgy, hogy
Dani repóihoz nem nyúl. A végén a javasolt javítás Dani kiolvasójához, átadásra.

## Tünet

Az FKE–Közgáz B meccsen (2026-10-31, `hun3k_141597`, jegyzőkönyv `F2KE-0021`) a
Közgáz #5-ös játékosa a PDF-ben benne van (első sor, kezdő), de a box score-ból
hiányzik: a mkosz_stats-ban a Közgáz játékossorainak összege 62, a hivatalos
eredmény 75. A 13 pont a kosarak listájában (`scoring_events`) megvan, licencszám
nélkül.

- A honlap meccsoldala és a fork meccsnézete ezt eddig is pótolta a kosarakból
  (`get_match_details()`, `reconstructed`), de kezdőként nem jelölte.
- A játékosnézetben (meccslista, összesítő) és a szezon-összesítőben a meccs
  „nem játszott” volt, mert ezek a `player_game_stats`-ból számolnak.

## Az ok

Az `extract_players()` a játékossorokat **fix y-ablakokban** keresi: sablononként
egy kezdő y (`TEAM_A_PLAYERS` / `TEAM_B_PLAYERS` + a `detect_template()` eltolása) és
24,5 px sormagasság, 12 sor. Ehhez a 2025/26-os PDF-ek igazodnak: a licencszám ott
16–18 px-lel az ablak teteje alatt ül, a sorköz 24,5 px.

2026 október közepétől az MKOSZ PDF-jeinek egy része más elrendezésű. A
`detect_template()` ezeket is TYPE2-nek ismeri fel, de:

- a sorköz 25,6–27,6 px (nem 24,5);
- az első sor licencszáma az ablak tetejétől 0,3–2 px-re van, vagy fölötte (az
  FKE-meccsen 0,5 px-lel fölötte: 1012,51 az 1013,0 helyett).

Ennek a következményei, a 2026/27-es 104 PDF-en mérve (2026-11-16):

1. **Kimarad az első sor**, ha a licencszám az ablak fölé kerül: a sort üresnek
   veszi (`continue`). 12 csapatrész, köztük a Közgáz B az FKE-meccsen.
2. **Kimarad a 12. sor**: a nagyobb sorköz miatt a 12. sor a 12. ablak alá esik.
   Az NB1 B (`hun2a`) meccsein rendszeres, és előfordul `hun3k` / `huna_cup`
   meccseken is.
3. **Kétszer számolt faultok.** Az `extract_personal_fouls()` a játékos ablakát
   12 px-lel lefelé kiterjeszti (az alsó indexek miatt); az új sorköznél ez a
   következő sor faultjait is magába veszi. A Közgáz B-nél: 2026-10-13
   (`hun3k_141615`) #11 és #19 egy-egy, 2026-10-31 (`hun3k_141597`) #18 kettő és
   #22 egy fault többlettel. A fork ezeket a Közgáz B meccsein javítja (lásd lent).
   Ugyanígy fix ablakkal olvassa az `extract_team_fouls()` a „Csapat hibák” mezőt: az
   új elrendezésben 10-31-én a 3–4. negyed X-eit az 1–2. negyedhez olvassa, 10-13-án
   egyet sem talál. (A mkosz_stats a csapatfaultokat nem tárolja, ezért ez ott nem
   látszik.)
4. Az elcsúszott ablakok miatt az új elrendezésben egyes sorokban üres a név, vagy
   rossz a kezdő-jelölés; az edző licencsora („(2026_…)”) segédedzőként kerül be.
5. A tördelt (kétsoros) nevek második sora a régi elrendezésben is elveszhet (a sor
   alja +7,8 px-nél van, a második sor +8–9 px-en), és vele a második sorban álló
   „(KAP)” is.

Három további észrevétel, ami nem ehhez a hibához tartozik:

- A `huna_cup_1032`-t a `detect_template()` TYPE3-nak ismeri fel, és 7 sor kimarad.
- A `scoresheet.sqlite` kulcsa a jegyzőkönyvszám (`F2KE-0021`), ami szezononként
  újrakezdődik: a 2025/26-os `hun3k_125493.pdf` is `F2KE-0021`, és a két PDF naponta
  felülírja egymást. A mkosz_stats-ban ma mindkét meccs külön, helyesen szerepel.
- A `reconcile_jersey_numbers()` a hiányzó játékos kosarait egy olyan csapattárshoz
  is átírhatja, akinek a mezszáma ugyanarra a számjegyre végződik (pl. #4 → #14), ha
  egyetlen ilyen van. Az FKE-meccsen ilyen nem volt.

## A fork javítása (box_score_repair.py)

A fork workflow-ja (`.github/workflows/stats-export.yml`) az export előtt:

1. **Letölti** a Közgáz B meccseinek PDF-jegyzőkönyveit (bajnoki és kupa, minden
   szezon, ami a mkosz_stats-ban van; `https://hunbasketimg.webpont.com/pdf/{szezon}/{gamecode}.pdf`).
2. **Újra kiolvassa** őket Dani kiolvasójával (`vendor/mkosz_scoresheet/`,
   változatlan másolat), de a sorhatárokat a csapatrészben ténylegesen megtalált
   licencszám-sorokhoz igazítja:
   - a csapatrész a „Játék engedély száma / Játékos neve” fejléc és az „EDZŐ”
     felirat között van;
   - licencsor: a licencszám oszlopában (x 20–85, hivatalos kék) legalább 5 számjegy
     a sor elején;
   - a sorköz a következő licencsorig tart (az utolsónál a mediánja);
   - név-sáv: 13,5 px-lel a licencsor fölött kezdődik, egy sorköz magas; fault-sáv:
     8 px-lel fölötte, és a +12 px-es kiterjesztéssel együtt is csak a következő sor
     fault-sávjáig ér.

   Dani soron belüli logikája (név, tördelés, „(KAP)”, X, kezdő, fault-klaszterek)
   ugyanaz: a fork az `extract_players()`-t és az `extract_personal_fouls()`-t egy-egy
   sorra hívja. A futó eredmény, a kosarak, a mezszám-egyeztetés és a játékosstat is
   Dani függvényeivel készül, egy memóriabeli adatbázisban.
3. **Pótolja** a letöltött adatbázis ideiglenes másolatában a Közgáz hiányzó
   `player_game_stats` sorait (pont, 2FG, 3FG, büntető, fault, kezdő), és a mezszám
   licenc nélküli kosarait a pótolt játékoshoz köti (negyedes bontás, eredmény
   alakulása). Csak akkor, ha mind teljesül:
   - a sor tényleg hiányzik (se licencszám, se név szerint nincs meg — a PDF-beli és a
     játékos más meccseiről ismert névvel is keresve), és a mezszáma nem egy másik
     játékosé;
   - a PDF ugyanaz a meccs: a végeredmény egyezik, és ha az adatbázisban van
     jegyzőkönyvszám, az is;
   - a PDF újraolvasása teljes: a Közgáz-sorok összege a hivatalos eredmény;
   - a PDF-ből számolt és az adatbázis kosaraiból számolt statja egyezik;
   - a pótlás után a játékosok összege = a hivatalos eredmény = a kosarak összege.

   Különben nem nyúl a meccshez, és a workflow figyelmeztet. Minden meccs (és minden
   felülírás) külön SAVEPOINT-ban íródik: ha a beírás hibára fut, csak az a meccs marad
   ki, figyelmeztetéssel.
4. **Kézi felülírás** tartaléknak: `data/box_score_overrides.json` (gamecode, side,
   jersey, `license_key`, starter, nem kötelezően pf). A `license_key` a licencszámból
   képzett kivonat (`python3 box_score_repair.py key <licencszám>`), hogy a fájlban
   ne álljon olvashatóan; a 6 jegyű licencszám kipróbálással visszakereshető, ezért
   ez nem titkosítás. A kulcs csak olyan játékoshoz oldható fel, aki legalább egy
   Közgáz B-meccsen licenccel szerepel. Ugyanaz a védőkorlát; a felülírás magától
   hatástalan, ha a sor már megvan (a forrásban vagy a PDF-ből pótolva), vagy ha a meccs
   box score-ja már teljes (így teljes meccshez nem ad pont nélküli „játékost”).

A pótolt sorokat a másolat `repaired_rows` táblája jelöli. Az export:

- `matches[].players[].repaired` és `players[].views.*.games[].repaired`: a sort a
  fork pótolta;
- `matches[].box_score_check` a pótlás előtti állapotból számol (`box_points`,
  `difference`), és új mezőkben a pótlást is mutatja: `repaired_points`,
  `remaining_difference` (ami a forrás és a pótolt sorok után is hiányzik; a generátor
  által a kosarakból kiegészített, ellenőrizetlen `reconstructed` sorok ebbe
  beleszámítanak). A honlap figyelmeztetése a `reconstructed` sorokat is beszámítja, ez
  az ellenőrzés nem.

A workflow kimenetében minden pótolt sor `notice`, minden kimaradt pótlás és
megmaradt eltérés `warning`, a futás összesítőjében pedig a Közgáz B összes meccse
egy táblázatban (hivatalos, előtte, utána, állapot). Ha a tesztek elbuknak (vagy a
tesztek PDF-jei nem tölthetők le), a pótlás kimarad, és az export figyelmeztetéssel a
forrás-adatbázisból fut; ha maga a pótlás áll le hibával, ugyanígy.

**Eredmény (2026-11-16):** a Közgáz B 27 meccséből egyen pótolt sort a fork (FKE,
#5, 13 pont, kezdő, 0 fault); utána mind a 27 meccsen egyezik az összeg.

## A faultok javítása

A sorpótlás után, ugyanabban a futásban, a fork a Közgáz B minden meccsén
összeveti a játékosonkénti faultot Dani adatbázisával: a javított kiolvasás
(licencsorokhoz igazított fault-sáv, Dani `extract_personal_fouls()`-ával) adja a
faultot. Ha egy játékosnál eltér, a fork a javított értéket használja — csak akkor,
ha mind teljesül:

- a javított érték játékosonként legfeljebb Dani értéke: a kétszer számolás csak
  többletet okoz, így ha valakinél nőne (pl. két játékos faultja felcserélődött),
  az más hiba, és a fork nem javít;
- a forrás minden Közgáz-sorát ismeri a PDF újraolvasása (licencszám szerint), és a
  javított faultok összege egyenlő a PDF játékos-faultjainak számával (nincs olyan
  fault, aminek a játékosa nincs a forrásban);
- **csapatfaultok:** negyedenként a javított faultok száma — legfeljebb 4-ig, mert a
  „Csapat hibák” mező negyedenként 4 X-et jelöl; a hosszabbítás a 4. negyedhez
  számít — egyenlő a jegyzőkönyv X-jelöléseivel. A jelöléseket a fork a feliratokhoz
  igazítva olvassa (`team_fouls()`: a csapat „Csapat:” felirata és a játékostábla
  fejléce közötti „Negyed 1 … 2 …” / „Negyed 3 … 4 …” sorok), nem Dani fix ablakával;
- **időrend:** a javított faultok (negyed, perc) eseményei mind megvannak Dani
  `personal_fouls` időrendjében, és Dani többlet-eseményei mind egy valódi fault
  ismétlései (ugyanaz a negyed és perc). Ez a mezszámot nem nézi; a játékosok közti
  felcserélést az előző, játékosonkénti feltétel szűri ki.

Különben nem nyúl a meccs faultjaihoz, és a workflow figyelmeztet („Fault nem
javítva”). Javításkor a `player_game_stats` faultja és a Közgáz oldal mezszámos
`personal_fouls` sorai (időrend, T/U) a PDF-ből íródnak, egy SAVEPOINT-ban; a
mezszám nélküli (edzői) sorok maradnak. A javított sorokat a másolat
`repaired_fouls` táblája jelöli (Dani értéke és a javított érték); az export ebből
jelöli őket: `matches[].players[].pf_repaired` és `pf_source` (Dani értéke), és
`players[].views.*.games[].pf_repaired`. A javított meccsen a Közgáz **teljes**
fault-időrendje a PDF-ből jön, mert Dani hibája a sorok közti eltolás is: a
`foul_timeline` olyan játékosnál is változhat, akinek a faultszáma nem változott
(2026-10-31: #14, #20, #38; 2026-10-13: #14 — mind a PDF szerint helyes). Ezt a
meccs-szintű `matches[].fouls_repaired` jelöli. A futás összesítőjében a „Javított
faultok” oszlop mutatja őket (vagy hogy ismert eltérés), a naplóban `notice`.

A 252 csapatrészből (a 2026/27-es 104 PDF és a Közgáz 22 darab 2025/26-os PDF-je) 244-ben a
javított faultok negyedenként pontosan kiadják a csapatfault-jelöléseket; a többi
7-ben (egy Közgáz-meccs: 2025-11-25) nem, és egynél a feliratok sem találhatók.

**Eredmény (2026-11-16):**

| Meccs | Játékos | Dani | Javított |
|---|---|---:|---:|
| 2026-10-13, `hun3k_141615` (Pénzügyőr) | #11 | 1 | 0 |
| 2026-10-13, `hun3k_141615` (Pénzügyőr) | #19 | 2 | 1 |
| 2026-10-31, `hun3k_141597` (FKE) | #18 | 2 | 0 |
| 2026-10-31, `hun3k_141597` (FKE) | #22 | 3 | 2 |

A 2025/26-os szezonban 11 meccsen tér el a javított fault Dani adatbázisától, de
egyiken sem javít a fork: tízen Dani `personal_fouls` időrendje sérült (értelmetlen
percek, pl. „610”, „99”, vagy hiányzik) — ezt a szezont Dani kiolvasójának egy korábbi
változata olvasta be —, egyen (2025-11-25) a csapatfault-jelölések nem egyeznek. Ezek
a napi futásban egyetlen összesítő figyelmeztetésként látszanak („Fault nem javítva
(ismert eltérések)”: hány meccs, melyik okkal).

Az ismert eltéréseket a `data/known_foul_mismatches.json` sorolja fel (gamecode és
okkód: `timeline`, `team_marks`, `sum`, `unknown_row`, `error`). Ha egy ott szereplő
meccs ugyanazzal az okkal bukik, az összesítőbe kerül; ha más okkal, vagy a meccs
nincs a listán (új, eddig nem látott eltérés), egyenként jelez. Ha egy ismert
eltérés megszűnik (a forrás javult, vagy a fork már javítani tudja), a workflow
értesít („Ismert fault-eltérés megszűnt”), és a sor törölhető a listából.

### Ellenőrzés helyben

```bash
pip install PyMuPDF==2.1 jsonschema
REQUIRE_PDFS=1 python3 -m unittest discover -s tests -v
python3 box_score_repair.py --db /tmp/mkosz_stats.sqlite --out /tmp/javitott.sqlite --pdf-dir /tmp/kozgaz-pdfs
python3 export_stats.py --db /tmp/javitott.sqlite --out public
```

## A helyes javítás Dani kiolvasójához (mkosz-scoresheet)

1. **A sorok a licencsorokhoz igazodjanak, ne fix ablakokhoz.** Az
   `extract_players()` előbb keresse meg a csapatrészben (fejléc és „EDZŐ” között) a
   licencszám-sorokat, és a sorhatárokat ezekből számolja: a sor egy sorköz magas,
   a sorköz a következő licencsorig tart. Így sem az első, sem a 12. sor nem esik ki,
   és a `max_rows` korlát sem kell.
2. **A faultok ugyanezekhez a sorokhoz kerüljenek.** Az `extract_personal_fouls()`
   most a játékos sorszámából (`pi`) számolja az ablakot, nem a sor helyéből: ha egy
   sor kimarad, a faultok elcsúsznak, és a +12 px-es kiterjesztés az új sorköznél
   átlóg a következő sorba. A fault-ablak a játékos saját sorához tartozzon, és ne
   érjen túl a következő sor fault-ablakának tetején (a fork: 8 px-lel a licencsor
   fölött kezdődik, és a következő sor ugyanilyen pontjáig tart).
   Az `extract_team_fouls()` a „Negyed” feliratokhoz igazodjon, és a kiolvasó
   ellenőrizze, hogy negyedenként `min(faultok, 4)` = X-jelölések.
3. **Önellenőrzés kiolvasáskor.** Ha egy kosár mezszámához nincs játékossor, vagy a
   játékosok összege nem egyezik a végeredménnyel, az `extraction_log` ne `success`
   legyen, hanem figyelmeztetés a mezszámmal.
4. **Újrafuttatás** `--force`-szal az x2627 szezonra; a mkosz-stats importja beszúrja
   az új sorokat. Az import `ON CONFLICT ... DO UPDATE`-je a meglévő sorok faultjait is
   frissíti.
5. Külön: a `scoresheet.sqlite` meccskulcsa legyen szezonnal egyedi (pl. a PDF neve
   vagy `szezon + jegyzőkönyvszám`), és a TYPE3-felismerés nézze meg a `huna_cup_1032`-t.

A fork javítása ezt a logikát követi (`box_score_repair.py`: `team_region()`,
`license_lines()`, `row_lines()`, `extract_rows()`, `extract_fouls()`,
`team_fouls()`), átvehető. A meglévő sorokból a fork csak a faultot írja át, és csak
a fenti védőkorláttal; ha Dani kiolvasója javul, a pótlás és a fault-javítás magától
üres lesz (a forrás már helyes). Utána a `vendor/` másolat frissíthető vagy törölhető.
