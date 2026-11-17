# A statisztika-JSON-ok (stats.json, standings.json, seasons.json, history.json)

> Generált fájl: a `stats_schema.py write` írja a sémából; kézzel ne szerkeszd.

Andris forkja a mkosz-dashboardból JSON-ban teszi közzé a Közgáz B statisztikáit a
Gametime appnak. A számok a `generate_dashboards.py` lekérdezéseiből és számító
függvényeiből jönnek, ugyanazokból, amikből a kozgazkosar.hu oldalai készülnek
(`export_stats.py`).

- **Hol:** a fork GitHub Pages oldalán, `data/kozgaz-b/` alatt:
  `seasons.json`, `{szezon}/stats.json`, `{szezon}/standings.json`, `history.json`, és a
  mostani szezon a `data/kozgaz-b/stats.json` és `standings.json` néven is.
- **Mikor:** naponta, Dani mkosz-stats importja után (`.github/workflows/stats-export.yml`).
- **Forrás:** a mkosz-stats nyilvános `mkosz_stats.sqlite`-ja; a tabella a mkosz.hu-ról.
- **Szerződés:** mezőt nem nevezünk át és nem törlünk, új mező jöhet; törő változásnál
  a `version` nő. A séma: `schemas/*.schema.json` (JSON Schema 2020-12); a workflow
  minden közzététel előtt ellenőrzi.
- **NB2 = jegyzőkönyv-szint:** pont, 2FG/3FG/FT bedobott, FT-kísérlet, fault, T/U,
  kezdő. Mezőny- és hármaskísérlet, lepattanó, gólpassz, labdaszerzés, blokk,
  eladott labda, perc és +/- a forrásban nincs, ezért itt sincs.
- **Nézetek:** a játékos- és csapatadatok `all` / `home` / `away` bontásban, a
  bajnoki meccsekből (alapszakasz + rájátszás); a csapaté rájátszásos szezonban
  `regular` / `playoff` bontásban is, és ezek hazai / idegen fele is (`regular_home`,
  `regular_away`, `playoff_home`, `playoff_away`; különben mind `null`). A kupameccsek (Hepp Kupa) a
  `matches[]`-ben teljes részletességgel benne vannak, a szezonösszesítőkbe nem
  számítanak (mint a honlapon).
- **Csoport-összehasonlítás:** a `league_comparison[]` a bajnokság minden csapatát
  rangsorolja a honlap csoport.html-jének mutatói szerint (ugyanazzal a kóddal).
- **Szezonról szezonra:** a `history.json` minden szezon tömör, meccsenkénti mutatóit adja
  (csapat és játékosok), a szezonok összehasonlításához; ugyanazokból a számokból, mint a
  szezonok `stats.json`-ja. A csapat büntető%-a és győzelem-aránya egy tizedesre kerekített
  (a fun factek és a játékosok `ft_pct`-je egészre). A játékos szezonjait a játékoskulcs köti
  össze: akinek egy szezonban még nem volt licencszáma (név-slug), az ott külön szerepel.
- **Játékoskulcs:** a licencszám, ha van (`key_type: "license"`), különben a névből
  képzett slug (`key_type: "name_slug"`).

Jelölés: `[]` = tömb eleme; a típus után `?` = lehet `null`.


## stats.json

Egy szezon minden statisztikája. A szezonösszesítők (players, team) a bajnoki meccsekből (alapszakasz + rájátszás) készülnek, ahogy a kozgazkosar.hu-n; a kupameccsek a matches[]-ben vannak.

| Mező | Típus | Jelentés |
|---|---|---|
| `version` | const 1 | Formátum-verzió. |
| `team` | const "kozgaz-b" | Csapatkulcs. |
| `team_name` | string | A csapat neve az MKOSZ-nál. |
| `season` | string | Szezonkulcs (pl. x2627). |
| `season_label` | string | Szezon felirata (pl. 2026/27). |
| `generated_at` | string | A fájl készítése (UTC). |
| `source` | object | Forrás. |
| `source.database` | string | A forrásadatbázis. |
| `source.database_updated_at` | string? | Az adatbázis utolsó frissítése (UTC), ha ismert. |
| `source.aggregate_competitions` | array | A szezonösszesítőkbe számító bajnokságok kódjai. |
| `competitions` | array | A szezon bajnokságai és kupái, ahol a Közgáz B játszott. |
| `competitions[].code` | string | MKOSZ bajnokság-kód (pl. hun3k, hun3_plya, huna_cup). |
| `competitions[].label` | string | Megjelenítendő név (pl. NB2 Kelet, Hepp Kupa). |
| `competitions[].phase` | string (regular | playoff | cup) | regular = alapszakasz, playoff = rájátszás, cup = kupa. |
| `competitions[].is_cup` | boolean | Kupa-e (a szezonösszesítőkbe nem számít). |
| `competitions[].matches` | integer | A Közgáz B lejátszott meccsei ebben (a forrásadatbázisban). |
| `matches` | array | Lejátszott meccsek időrendben (bajnoki és kupa). |
| `matches[].gamecode` | string | A meccs kulcsa (MKOSZ-azonosító, pl. hun3k_141615). |
| `matches[].mkosz_match_id` | string | Az MKOSZ meccs-azonosítója; azonos a gamecode-dal és a schedule.json match_id-jával. |
| `matches[].scoresheet_match_id` | string? | A jegyzőkönyv azonosítója (pl. F2KE-0035, kupánál FHKF-…). |
| `matches[].competition` | string | Bajnokság-kód (lásd competitions[]). |
| `matches[].competition_label` | string | Bajnokság neve. |
| `matches[].phase` | string (regular | playoff | cup) | regular / playoff / cup. |
| `matches[].is_cup` | boolean | Kupameccs-e (pl. Hepp Kupa). |
| `matches[].date` | string | Dátum (budapesti), ÉÉÉÉ-HH-NN. |
| `matches[].time` | string? | Kezdés (budapesti), ÓÓ:PP. |
| `matches[].venue` | string? | Helyszín. |
| `matches[].home_team` | string | Hazai csapat teljes neve. |
| `matches[].away_team` | string | Vendég csapat teljes neve. |
| `matches[].home_team_short` | string | Hazai csapat rövid neve (a honlap rövidítése). |
| `matches[].away_team_short` | string | Vendég csapat rövid neve. |
| `matches[].is_home` | boolean | A Közgáz B hazai-e. |
| `matches[].opponent` | string | Az ellenfél teljes neve. |
| `matches[].opponent_short` | string | Az ellenfél rövid neve. |
| `matches[].opponent_table_short` | string | Ellenfél rövid neve, ahogy a szezon tabelláján (team_short); ha nincs a tabellán (pl. kupaellenfél), a honlap naptárának rövidítése (az app eltéréseivel, export_stats.APP_SHORT_NAMES). |
| `matches[].home_score` | integer? | Hazai pont. |
| `matches[].away_score` | integer? | Vendég pont. |
| `matches[].kozgaz_score` | integer? | A Közgáz B pontja. |
| `matches[].opponent_score` | integer? | Az ellenfél pontja. |
| `matches[].won` | boolean | A Közgáz B nyert-e. |
| `matches[].mkosz_url` | string | A meccs oldala az mkosz.hu-n. |
| `matches[].quarters` | array | Negyedenkénti pontok, hazai–vendég (nem kumulált). |
| `matches[].quarters[].quarter` | integer | Negyed sorszáma (1–4, 5+ = hosszabbítás). |
| `matches[].quarters[].home` | integer | Hazai pont a negyedben. |
| `matches[].quarters[].away` | integer | Vendég pont a negyedben. |
| `matches[].quarters_source` | string (events | quarter_scores) | events = a kosarak sorából számolva (a honlap is ezt használja), quarter_scores = a jegyzőkönyv negyed-táblájából. |
| `matches[].kozgaz_totals` | object | A Közgáz box score összesítő sora. |
| `matches[].kozgaz_totals.points` | integer | Pont (a játékossorok összege). |
| `matches[].kozgaz_totals.fg2_made` | integer | Bedobott kétpontos. |
| `matches[].kozgaz_totals.fg3_made` | integer | Bedobott hárompontos. |
| `matches[].kozgaz_totals.ft_made` | integer | Bedobott büntető. |
| `matches[].kozgaz_totals.ft_att` | integer | Büntető-kísérlet. |
| `matches[].kozgaz_totals.pf` | integer | Személyi hiba. |
| `matches[].kozgaz_totals.tech` | integer | Technikai hiba (T). |
| `matches[].kozgaz_totals.unsport` | integer | Sportszerűtlen hiba (U). |
| `matches[].box_score_check` | object | Forrás-ellenőrzés a pótlás előtti állapotból (docs/scoresheet-extraction-fix.md). A honlap figyelmeztetése a kosarakból kiegészített sorokat is beszámítja, ez nem. |
| `matches[].box_score_check.official_points` | integer | A hivatalos végeredmény Közgáz-pontja. |
| `matches[].box_score_check.box_points` | integer | A forrás (Dani adatbázisa) játékossoraihoz rendelt pontok összege, a pótolt (repaired) és a kosarakból kiegészített (reconstructed) sorok nélkül. |
| `matches[].box_score_check.difference` | integer | official_points − box_points; ha nem 0, a forrás jegyzőkönyv-adata hiányos. |
| `matches[].box_score_check.repaired_points` | integer | A fork által a PDF-jegyzőkönyvből vagy kézi felülírásból pótolt sorok pontjai. |
| `matches[].box_score_check.remaining_difference` | integer | official_points − box_points − repaired_points: ami a pótlás után is hiányzik; 0, ha a forrás és a pótolt sorok együtt kiadják a hivatalos eredményt. A kosarakból kiegészített (reconstructed) sorok pontjai ebbe beleszámítanak (ellenőrizetlenek). |
| `matches[].box_score_check.unassigned_fouls` | integer | Játékoshoz nem rendelhető (mezszám nélküli) Közgáz-faultok. |
| `matches[].opponent_totals` | object | Az ellenfél összesítője. |
| `matches[].opponent_totals.points` | integer | Pont (a hivatalos eredmény). |
| `matches[].opponent_totals.fg2_made` | integer | Bedobott kétpontos. |
| `matches[].opponent_totals.fg3_made` | integer | Bedobott hárompontos. |
| `matches[].opponent_totals.ft_made` | integer | Bedobott büntető. |
| `matches[].opponent_totals.ft_att` | integer | Büntető-kísérlet. |
| `matches[].opponent_totals.ft_pct` | integer | Büntető-százalék (egészre kerekítve; 0, ha nem volt kísérlet). |
| `matches[].opponent_totals.top_scorer` | object? | Az ellenfél legjobb dobója. |
| `matches[].opponent_totals.top_scorer.name` | string | Név (a jegyzőkönyv szerint). |
| `matches[].opponent_totals.top_scorer.points` | integer | Pont. |
| `matches[].fouls_repaired` | boolean | A fork a meccs Közgáz-faultjait a PDF-jegyzőkönyvből javította: ilyenkor a teljes Közgáz fault-időrend (foul_timeline, T/U) a PDF-ből jön, akkor is, ha egy játékos faultszáma nem változott (pf_repaired csak a változott számokat jelöli). |
| `matches[].players` | array | A Közgáz játékossorai (box score), pont szerint csökkenő sorrendben. |
| `matches[].players[].key` | string | Játékoskulcs: licencszám, vagy ha nincs, a névből képzett slug. |
| `matches[].players[].key_type` | string (license | name_slug) | license = licencszám, name_slug = névből képzett slug. |
| `matches[].players[].jersey` | integer? | Mezszám. |
| `matches[].players[].name` | string | Név (a jegyzőkönyv szerint). |
| `matches[].players[].starter` | boolean | Kezdőötös tagja volt-e. |
| `matches[].players[].points` | integer | Pont. |
| `matches[].players[].fg2_made` | integer | Bedobott kétpontos. |
| `matches[].players[].fg3_made` | integer | Bedobott hárompontos. |
| `matches[].players[].ft_made` | integer | Bedobott büntető. |
| `matches[].players[].ft_att` | integer | Büntető-kísérlet. |
| `matches[].players[].pf` | integer | Személyi hiba. |
| `matches[].players[].tech` | integer | Technikai hiba (T). |
| `matches[].players[].unsport` | integer | Sportszerűtlen hiba (U). |
| `matches[].players[].reconstructed` | boolean | A sor a kosarak listájából pótolt (a jegyzőkönyv box score-jából hiányzott). |
| `matches[].players[].repaired` | boolean | A sort a fork pótolta a PDF-jegyzőkönyvből vagy kézi felülírásból (a forrás adatbázisából hiányzott; docs/scoresheet-extraction-fix.md). |
| `matches[].players[].pf_repaired` | boolean | A játékos faultszámát a fork javította a PDF-jegyzőkönyvből (a forrás adatbázisa többet számolt; docs/scoresheet-extraction-fix.md). |
| `matches[].players[].pf_source` | integer? | A forrás adatbázisának faultszáma, ha a fork javította (pf_repaired), különben null. |
| `matches[].progression` | object | Az eredmény alakulása (csak a beesett kosarak; NB2-ben nincs kihagyott dobás). |
| `matches[].progression.events` | array | Kosarak időrendben. |
| `matches[].progression.events[].seq` | integer | Sorszám a meccsen belül (a grafikon x-tengelye a honlapon). |
| `matches[].progression.events[].quarter` | integer | Negyed. |
| `matches[].progression.events[].minute` | integer | Perc a negyeden belül (0–10). |
| `matches[].progression.events[].minute_estimated` | boolean | A perc becsült: a jegyzőkönyv csak az új percnél ír időt, ilyenkor az előző ismert percet kapja (a negyed elején 0). |
| `matches[].progression.events[].team` | string (home | away) | Melyik csapat dobta: home / away. |
| `matches[].progression.events[].is_kozgaz` | boolean | A Közgáz dobta-e. |
| `matches[].progression.events[].player` | string? | A dobó neve, ha ismert. |
| `matches[].progression.events[].points` | integer | Pont (1, 2, 3). |
| `matches[].progression.events[].shot` | string | Dobástípus (2FG, 3FG, FT, MULTI). |
| `matches[].progression.events[].home_score` | integer | Hazai állás a kosár után. |
| `matches[].progression.events[].away_score` | integer | Vendég állás a kosár után. |
| `matches[].progression.quarter_ends` | array | Negyedvégi állások. |
| `matches[].progression.quarter_ends[].quarter` | integer | Negyed. |
| `matches[].progression.quarter_ends[].seq` | integer | A negyed utolsó kosarának sorszáma. |
| `matches[].progression.quarter_ends[].home` | integer | Hazai állás (kumulált). |
| `matches[].progression.quarter_ends[].away` | integer | Vendég állás (kumulált). |
| `matches[].facts` | object | Érdekességek (a honlap csempéi, ugyanabban a sorrendben és feltételekkel). |
| `matches[].facts.comparisons` | array | Kétcsapatos összevetések, hazai–vendég. |
| `matches[].facts.comparisons[].label` | string | Felirat (pl. Legnagyobb vezetés). |
| `matches[].facts.comparisons[].home` | integer | Hazai érték. |
| `matches[].facts.comparisons[].away` | integer | Vendég érték. |
| `matches[].facts.comparisons[].format` | string (int | plus | points | run) | Kiírás: int = szám, plus = +szám, points = számp, run = szám-0. |
| `matches[].facts.comparisons[].note` | string? | Megjegyzés a csempe alján. |
| `matches[].facts.starter_bench` | object? | Kezdő és cserepontok (csak ha van kezdő-adat). |
| `matches[].facts.starter_bench.home_starter` | integer | Hazai kezdők pontja. |
| `matches[].facts.starter_bench.home_bench` | integer | Hazai cserék pontja. |
| `matches[].facts.starter_bench.away_starter` | integer | Vendég kezdők pontja. |
| `matches[].facts.starter_bench.away_bench` | integer | Vendég cserék pontja. |
| `matches[].facts.starter_bench.home_unaccounted` | integer | Hazai pont, ami nincs játékoshoz rendelve. |
| `matches[].facts.starter_bench.away_unaccounted` | integer | Vendég pont, ami nincs játékoshoz rendelve. |
| `matches[].facts.lead_changes` | integer? | Vezetésváltások száma (null, ha nincs kosár-lista). |
| `matches[].quarter_mvps` | array | Negyedenként a legtöbb pontot dobó játékos csapatonként. |
| `matches[].quarter_mvps[].quarter` | integer | Negyed (1–4). |
| `matches[].quarter_mvps[].home` | object | Hazai legjobb. |
| `matches[].quarter_mvps[].home.player` | string | Név (— ha nem dobott). |
| `matches[].quarter_mvps[].home.points` | integer | Pont. |
| `matches[].quarter_mvps[].away` | object | Vendég legjobb. |
| `matches[].quarter_mvps[].away.player` | string | Név (— ha nem dobott). |
| `matches[].quarter_mvps[].away.points` | integer | Pont. |
| `matches[].scoring_distribution` | object | Pontszerzés megoszlása. |
| `matches[].scoring_distribution.kozgaz` | object? | Közgáz (null, ha nincs adat). |
| `matches[].scoring_distribution.kozgaz.points_2` | integer | Kétpontosokból szerzett pont. |
| `matches[].scoring_distribution.kozgaz.points_3` | integer | Hárompontosokból szerzett pont. |
| `matches[].scoring_distribution.kozgaz.points_ft` | integer | Büntetőből szerzett pont. |
| `matches[].scoring_distribution.kozgaz.total` | integer | Összesen (a három összege). |
| `matches[].scoring_distribution.kozgaz.pct_2` | integer | Kétpontosok aránya, % (egészre kerekítve). |
| `matches[].scoring_distribution.kozgaz.pct_3` | integer | Hárompontosok aránya, %. |
| `matches[].scoring_distribution.kozgaz.pct_ft` | integer | Büntetők aránya, %. |
| `matches[].scoring_distribution.opponent` | object? | Ellenfél (null, ha nincs adat). |
| `matches[].scoring_distribution.opponent.points_2` | integer | Kétpontosokból szerzett pont. |
| `matches[].scoring_distribution.opponent.points_3` | integer | Hárompontosokból szerzett pont. |
| `matches[].scoring_distribution.opponent.points_ft` | integer | Büntetőből szerzett pont. |
| `matches[].scoring_distribution.opponent.total` | integer | Összesen (a három összege). |
| `matches[].scoring_distribution.opponent.pct_2` | integer | Kétpontosok aránya, % (egészre kerekítve). |
| `matches[].scoring_distribution.opponent.pct_3` | integer | Hárompontosok aránya, %. |
| `matches[].scoring_distribution.opponent.pct_ft` | integer | Büntetők aránya, %. |
| `matches[].foul_timeline` | array | A Közgáz játékosok faultjai időrendben, a legtöbb faultot elkövető elöl. |
| `matches[].foul_timeline[].jersey` | integer | Mezszám. |
| `matches[].foul_timeline[].name` | string | Név (vagy #mezszám, ha a box score-ban nincs). |
| `matches[].foul_timeline[].player_key` | string? | A játékos kulcsa a players[]-ben, ha megtalálható. |
| `matches[].foul_timeline[].fouled_out` | boolean | Kipontozódott-e (5+ fault). |
| `matches[].foul_timeline[].fouls` | array | Faultok. |
| `matches[].foul_timeline[].fouls[].quarter` | integer | Negyed. |
| `matches[].foul_timeline[].fouls[].minute` | integer | Perc a negyeden belül (0–10, a honlap javításával). |
| `matches[].foul_timeline[].fouls[].game_minute` | integer | Perc a meccsen (0–40): (negyed−1)·10 + perc. |
| `players` | array | Játékosok, összpont szerint csökkenő sorrendben. |
| `players[].key` | string | Játékoskulcs: licencszám, vagy ha nincs, a névből képzett slug. |
| `players[].key_type` | string (license | name_slug) | license / name_slug. |
| `players[].name` | string | Név (a jegyzőkönyv szerint). |
| `players[].jersey` | integer? | Mezszám (a szezonban a legnagyobb előforduló). |
| `players[].slug` | string | A névből képzett slug (a honlap játékosoldalának neve). |
| `players[].views` | object | Nézetek: összes, hazai, idegen; alapszakasz, rájátszás, és ezek hazai / idegen fele. |
| `players[].views.all` | object | Egy nézet a bajnoki meccsekből (views.all: mindegyik). |
| `players[].views.all.summary` | object | Szezonösszesítő. |
| `players[].views.all.summary.games` | integer | Lejátszott meccs. |
| `players[].views.all.summary.points` | integer | Összes pont. |
| `players[].views.all.summary.ppg` | number | Pontátlag (1 tizedes). |
| `players[].views.all.summary.fg2_made` | integer | Bedobott kétpontos. |
| `players[].views.all.summary.fg3_made` | integer | Bedobott hárompontos. |
| `players[].views.all.summary.ft_made` | integer | Bedobott büntető. |
| `players[].views.all.summary.ft_att` | integer | Büntető-kísérlet. |
| `players[].views.all.summary.ft_pct` | integer | Büntető-százalék (egészre kerekítve; 0, ha nem volt kísérlet). |
| `players[].views.all.summary.pf` | integer | Személyi hiba. |
| `players[].views.all.summary.pf_per_game` | number | Fault/meccs (1 tizedes). |
| `players[].views.all.summary.max_points` | integer | Csúcs (legtöbb pont egy meccsen). |
| `players[].views.all.summary.starts` | integer | Kezdések száma. |
| `players[].views.all.summary.share_pct` | number | A csapat pontjaiból való részesedés, % (1 tizedes). |
| `players[].views.all.summary.tech` | integer | Technikai hiba (T). |
| `players[].views.all.summary.unsport` | integer | Sportszerűtlen hiba (U). |
| `players[].views.all.scoring_split` | object | Dobásmegoszlás (pontban). |
| `players[].views.all.scoring_split.points_2` | integer | Kétpontosokból. |
| `players[].views.all.scoring_split.points_3` | integer | Hárompontosokból. |
| `players[].views.all.scoring_split.points_ft` | integer | Büntetőből. |
| `players[].views.all.quarters` | array | Negyedenkénti teljesítmény (a szezon összesen, nem átlag). |
| `players[].views.all.quarters[].quarter` | integer | Negyed (1–4). |
| `players[].views.all.quarters[].points` | integer | Pont ebben a negyedben a szezonban. |
| `players[].views.all.quarters[].threes` | integer | Bedobott hárompontos ebben a negyedben. |
| `players[].views.all.games` | array | Meccsenkénti sorok, időrendben; a csapat minden bajnoki meccse. |
| `players[].views.all.games[].gamecode` | string | A meccs kulcsa (matches[].gamecode). |
| `players[].views.all.games[].competition` | string? | Bajnokság-kód. |
| `players[].views.all.games[].date` | string | Dátum. |
| `players[].views.all.games[].is_home` | boolean | Hazai meccs-e. |
| `players[].views.all.games[].opponent` | string | Ellenfél teljes neve. |
| `players[].views.all.games[].opponent_short` | string | Ellenfél rövid neve. |
| `players[].views.all.games[].opponent_table_short` | string | Ellenfél rövid neve, ahogy a szezon tabelláján (team_short); ha nincs a tabellán (pl. kupaellenfél), a honlap naptárának rövidítése (az app eltéréseivel, export_stats.APP_SHORT_NAMES). |
| `players[].views.all.games[].result` | string (W | L) | A csapat eredménye: W / L. |
| `players[].views.all.games[].kozgaz_score` | integer | Közgáz pont. |
| `players[].views.all.games[].opponent_score` | integer | Ellenfél pont. |
| `players[].views.all.games[].played` | boolean | Játszott-e a játékos (false = nem lépett pályára; ilyenkor a statok null). |
| `players[].views.all.games[].points` | integer? | Pont. |
| `players[].views.all.games[].fg2_made` | integer? | Bedobott kétpontos. |
| `players[].views.all.games[].fg3_made` | integer? | Bedobott hárompontos. |
| `players[].views.all.games[].ft_made` | integer? | Bedobott büntető. |
| `players[].views.all.games[].ft_att` | integer? | Büntető-kísérlet. |
| `players[].views.all.games[].pf` | integer? | Személyi hiba. |
| `players[].views.all.games[].share_pct` | number? | A csapat pontjaiból való részesedés, %. |
| `players[].views.all.games[].starter` | boolean? | Kezdő volt-e. |
| `players[].views.all.games[].repaired` | boolean | A meccs sorát a fork pótolta a PDF-jegyzőkönyvből vagy kézi felülírásból (false, ha nem játszott). |
| `players[].views.all.games[].pf_repaired` | boolean | A meccs faultját a fork javította a PDF-jegyzőkönyvből (false, ha nem játszott). |
| `players[].views.all.insights` | object | Elemzői meglátások (a honlap szabályaival, erre a nézetre számolva). |
| `players[].views.all.insights.strengths` | array | Erősségek (legfeljebb 5). |
| `players[].views.all.insights.weaknesses` | array | Fejlesztendő területek (legfeljebb 5). |
| `players[].views.home` | object | Mint a `views.all`. |
| `players[].views.away` | object | Mint a `views.all`. |
| `players[].views.regular` | object? | Mint a `views.all`, csak az alapszakasz meccseiből; null, ha a szezonban nincs rájátszás. |
| `players[].views.playoff` | object? | Mint a `views.all`, csak a rájátszás meccseiből; null, ha a szezonban nincs rájátszás. |
| `players[].views.regular_home` | object? | Mint a `views.all`, csak az alapszakasz hazai meccseiből; null, ha a szezonban nincs rájátszás. |
| `players[].views.regular_away` | object? | Mint a `views.all`, csak az alapszakasz idegenbeli meccseiből; null, ha a szezonban nincs rájátszás. |
| `players[].views.playoff_home` | object? | Mint a `views.all`, csak a rájátszás hazai meccseiből; null, ha a szezonban nincs rájátszás. |
| `players[].views.playoff_away` | object? | Mint a `views.all`, csak a rájátszás idegenbeli meccseiből; null, ha a szezonban nincs rájátszás. |
| `team_stats` | object? | Csapatszint (null, ha a szezonban még nincs bajnoki meccs). |
| `team_stats.views` | object | Nézetek: összes, hazai, idegen; alapszakasz, rájátszás, és ezek hazai / idegen fele. |
| `team_stats.views.all` | object | Egy nézet a bajnoki meccsekből (views.all: mindegyik). |
| `team_stats.views.all.record` | object | Mérleg. |
| `team_stats.views.all.record.games` | integer | Meccs. |
| `team_stats.views.all.record.wins` | integer | Győzelem. |
| `team_stats.views.all.record.losses` | integer | Vereség. |
| `team_stats.views.all.record.scored` | integer | Dobott pont. |
| `team_stats.views.all.record.allowed` | integer | Kapott pont. |
| `team_stats.views.all.record.ppg` | number | Dobott/meccs. |
| `team_stats.views.all.record.opp_ppg` | number | Kapott/meccs. |
| `team_stats.views.all.record.diff_per_game` | number | Különbség/meccs. |
| `team_stats.views.all.record.best_score` | integer | Legtöbb dobott pont egy meccsen. |
| `team_stats.views.all.record.most_allowed` | integer | Legtöbb kapott pont egy meccsen. |
| `team_stats.views.all.record.players_used` | integer | Pályára lépett játékosok száma. |
| `team_stats.views.all.record.home_wins` | integer | Hazai győzelem. |
| `team_stats.views.all.record.home_games` | integer | Hazai meccs. |
| `team_stats.views.all.record.away_wins` | integer | Idegenbeli győzelem. |
| `team_stats.views.all.record.away_games` | integer | Idegenbeli meccs. |
| `team_stats.views.all.games` | array | A meccsek, időrendben. |
| `team_stats.views.all.games[].gamecode` | string | A meccs kulcsa. |
| `team_stats.views.all.games[].competition` | string? | Bajnokság-kód. |
| `team_stats.views.all.games[].date` | string | Dátum. |
| `team_stats.views.all.games[].is_home` | boolean | Hazai-e. |
| `team_stats.views.all.games[].opponent` | string | Ellenfél teljes neve. |
| `team_stats.views.all.games[].opponent_short` | string | Ellenfél rövid neve. |
| `team_stats.views.all.games[].opponent_table_short` | string | Ellenfél rövid neve, ahogy a szezon tabelláján (team_short); ha nincs a tabellán (pl. kupaellenfél), a honlap naptárának rövidítése (az app eltéréseivel, export_stats.APP_SHORT_NAMES). |
| `team_stats.views.all.games[].kozgaz_score` | integer | Közgáz pont. |
| `team_stats.views.all.games[].opponent_score` | integer | Ellenfél pont. |
| `team_stats.views.all.games[].result` | string (W | L) | W / L. |
| `team_stats.views.all.quarters` | array | Negyedátlagok. |
| `team_stats.views.all.quarters[].quarter` | integer | Negyed (1–4). |
| `team_stats.views.all.quarters[].kozgaz_avg` | number | Közgáz pont/meccs a negyedben. |
| `team_stats.views.all.quarters[].opponent_avg` | number | Ellenfél pont/meccs a negyedben. |
| `team_stats.views.all.quarters[].won` | integer | Megnyert negyedek száma. |
| `team_stats.views.all.quarters[].lost` | integer | Elvesztett negyedek száma. |
| `team_stats.views.all.scenarios` | array | Félidős és 3 negyed utáni forgatókönyvek. |
| `team_stats.views.all.scenarios[].key` | string (HT_LEAD | HT_TRAIL | 3Q_LEAD | 3Q_TRAIL) | HT = félidő, 3Q = 3 negyed után; LEAD = vezet, TRAIL = hátrányban. |
| `team_stats.views.all.scenarios[].label` | string | Felirat. |
| `team_stats.views.all.scenarios[].games` | integer | Ennyi meccsen állt így. |
| `team_stats.views.all.scenarios[].wins` | integer | Ebből ennyit nyert meg (vezetésnél: győzelem, hátránynál: fordítás). |
| `team_stats.views.all.scoring_split` | object | Pontmegoszlás dobástípus szerint. |
| `team_stats.views.all.scoring_split.points_2` | integer | Kétpontosokból. |
| `team_stats.views.all.scoring_split.points_3` | integer | Hárompontosokból. |
| `team_stats.views.all.scoring_split.points_ft` | integer | Büntetőből. |
| `team_stats.views.all.scoring_split.pct_2` | integer | Kétpontosok aránya, %. |
| `team_stats.views.all.scoring_split.pct_3` | integer | Hárompontosok aránya, %. |
| `team_stats.views.all.scoring_split.pct_ft` | integer | Büntetők aránya, %. |
| `team_stats.views.all.scoring_split.ft_made` | integer | Bedobott büntető. |
| `team_stats.views.all.scoring_split.ft_att` | integer | Büntető-kísérlet. |
| `team_stats.views.all.runs_for` | array | Top 5 saját run. |
| `team_stats.views.all.runs_for[].date` | string | Dátum. |
| `team_stats.views.all.runs_for[].opponent` | string | Ellenfél teljes neve. |
| `team_stats.views.all.runs_for[].opponent_short` | string | Ellenfél rövid neve. |
| `team_stats.views.all.runs_for[].opponent_table_short` | string | Ellenfél rövid neve, ahogy a szezon tabelláján (team_short); ha nincs a tabellán (pl. kupaellenfél), a honlap naptárának rövidítése (az app eltéréseivel, export_stats.APP_SHORT_NAMES). |
| `team_stats.views.all.runs_for[].start_quarter` | integer | Kezdő negyed. |
| `team_stats.views.all.runs_for[].end_quarter` | integer | Záró negyed. |
| `team_stats.views.all.runs_for[].points` | integer | Pont a runban. |
| `team_stats.views.all.runs_for[].baskets` | integer | Kosarak száma a runban. |
| `team_stats.views.all.runs_against` | array | Top 5 kapott run. |
| `team_stats.views.all.runs_against[].date` | string | Dátum. |
| `team_stats.views.all.runs_against[].opponent` | string | Ellenfél teljes neve. |
| `team_stats.views.all.runs_against[].opponent_short` | string | Ellenfél rövid neve. |
| `team_stats.views.all.runs_against[].opponent_table_short` | string | Ellenfél rövid neve, ahogy a szezon tabelláján (team_short); ha nincs a tabellán (pl. kupaellenfél), a honlap naptárának rövidítése (az app eltéréseivel, export_stats.APP_SHORT_NAMES). |
| `team_stats.views.all.runs_against[].start_quarter` | integer | Kezdő negyed. |
| `team_stats.views.all.runs_against[].end_quarter` | integer | Záró negyed. |
| `team_stats.views.all.runs_against[].points` | integer | Pont a runban. |
| `team_stats.views.all.runs_against[].baskets` | integer | Kosarak száma a runban. |
| `team_stats.views.all.facts` | array | Fun factek; mindegyik szövegrészek listája (a kiemelt részek bold: true). |
| `team_stats.views.all.facts[]` | array | Egy fact. |
| `team_stats.views.all.facts[][].text` | string | Szöveg. |
| `team_stats.views.all.facts[][].bold` | boolean | Kiemelt-e. |
| `team_stats.views.home` | object | Mint a `views.all`. |
| `team_stats.views.away` | object | Mint a `views.all`. |
| `team_stats.views.regular` | object? | Mint a `views.all`, csak az alapszakasz meccseiből; null, ha a szezonban nincs rájátszás. |
| `team_stats.views.playoff` | object? | Mint a `views.all`, csak a rájátszás meccseiből; null, ha a szezonban nincs rájátszás. |
| `team_stats.views.regular_home` | object? | Mint a `views.all`, csak az alapszakasz hazai meccseiből; null, ha a szezonban nincs rájátszás. |
| `team_stats.views.regular_away` | object? | Mint a `views.all`, csak az alapszakasz idegenbeli meccseiből; null, ha a szezonban nincs rájátszás. |
| `team_stats.views.playoff_home` | object? | Mint a `views.all`, csak a rájátszás hazai meccseiből; null, ha a szezonban nincs rájátszás. |
| `team_stats.views.playoff_away` | object? | Mint a `views.all`, csak a rájátszás idegenbeli meccseiből; null, ha a szezonban nincs rájátszás. |
| `league_comparison` | array | Csoport-összehasonlítás bajnokságonként (a honlap csoport.html-je): a csoport minden csapata a jegyzőkönyvek alapján, mutatónként rangsorolva. |
| `league_comparison[].competition` | string | Bajnokság-kód. |
| `league_comparison[].competition_label` | string | Bajnokság neve. |
| `league_comparison[].phase` | string (regular | playoff | cup) | Szakasz. |
| `league_comparison[].team_count` | integer | A csoport csapatainak száma. |
| `league_comparison[].metrics` | array | A mutatók, a honlap sorrendjében. |
| `league_comparison[].metrics[].key` | string (wl | ppg | oppg | ft_pct | fg2_pg | fg3_pg | fta_total | ftm_pg) | A mutató kulcsa. |
| `league_comparison[].metrics[].label` | string | A mutató címe (a honlap szerint). |
| `league_comparison[].metrics[].rows` | array | A csapatok a mutató szerinti sorrendben. |
| `league_comparison[].metrics[].rows[].rank` | integer | Helyezés ebben a mutatóban (1-től). |
| `league_comparison[].metrics[].rows[].team` | string | Csapat teljes neve. |
| `league_comparison[].metrics[].rows[].team_short` | string | Csapat rövid neve (a honlap rövidítése, az app eltéréseivel). |
| `league_comparison[].metrics[].rows[].is_kozgaz` | boolean | A Közgáz B-e. |
| `league_comparison[].metrics[].rows[].games` | integer | Lejátszott meccsek a bajnokságban. |
| `league_comparison[].metrics[].rows[].value` | string | Az érték, ahogy a honlap írja (pl. 9-13, 76.9, 67.6%). |

## standings.json

A szezon tabellái bajnokságonként (rájátszásnál a Közgáz B csoportja).

| Mező | Típus | Jelentés |
|---|---|---|
| `version` | const 1 | Formátum-verzió. |
| `team` | const "kozgaz-b" | Csapatkulcs. |
| `season` | string | Szezonkulcs. |
| `season_label` | string | Szezon felirata. |
| `generated_at` | string | A fájl készítése (UTC). |
| `tables` | array | Tabellák. |
| `tables[].competition` | string | Bajnokság-kód. |
| `tables[].competition_label` | string | Bajnokság neve. |
| `tables[].phase` | string (regular | playoff | cup) | regular / playoff. |
| `tables[].source` | string | Forrás (MKOSZ). |
| `tables[].source_url` | string | A forrásoldal. |
| `tables[].fetched_at` | string | A lekérés ideje (UTC). |
| `tables[].rows` | array | Sorok helyezés szerint. |
| `tables[].rows[].rank` | integer | Helyezés. |
| `tables[].rows[].team` | string | Csapat teljes neve. |
| `tables[].rows[].team_short` | string | Csapat rövid neve (a honlap rövidítése, az app eltéréseivel). |
| `tables[].rows[].is_kozgaz` | boolean | A Közgáz B sora-e. |
| `tables[].rows[].games` | integer | M: lejátszott meccs. |
| `tables[].rows[].wins` | integer | Gy: győzelem. |
| `tables[].rows[].losses` | integer | V: vereség. |
| `tables[].rows[].scored` | integer | Dob: dobott pont. |
| `tables[].rows[].allowed` | integer | Kap: kapott pont. |
| `tables[].rows[].diff` | integer | +/-: dobott − kapott. |
| `tables[].rows[].points` | integer | Pt: bajnoki pont. |
| `tables[].rows[].streak` | string? | Sorozat (MKOSZ „Sor”, pl. GY5 = 5 győzelem, V1 = 1 vereség). |

## seasons.json

Az elérhető szezonok, a legújabb elöl.

| Mező | Típus | Jelentés |
|---|---|---|
| `version` | const 1 | Formátum-verzió. |
| `team` | const "kozgaz-b" | Csapatkulcs. |
| `current_season` | string | A mostani (legutóbbi) szezon kulcsa. |
| `generated_at` | string | A fájl készítése (UTC). |
| `seasons` | array | Szezonok. |
| `seasons[].season` | string | Szezonkulcs. |
| `seasons[].label` | string | Felirat (pl. 2025/26). |
| `seasons[].competitions` | array | Bajnokságok és kupák. |
| `seasons[].competitions[].code` | string | MKOSZ bajnokság-kód (pl. hun3k, hun3_plya, huna_cup). |
| `seasons[].competitions[].label` | string | Megjelenítendő név (pl. NB2 Kelet, Hepp Kupa). |
| `seasons[].competitions[].phase` | string (regular | playoff | cup) | regular = alapszakasz, playoff = rájátszás, cup = kupa. |
| `seasons[].competitions[].is_cup` | boolean | Kupa-e (a szezonösszesítőkbe nem számít). |
| `seasons[].competitions[].matches` | integer | A Közgáz B lejátszott meccsei ebben (a forrásadatbázisban). |
| `seasons[].match_count` | integer | Lejátszott meccsek száma a stats.json-ban. |
| `seasons[].first_match_date` | string | Első meccs. |
| `seasons[].last_match_date` | string | Utolsó meccs. |
| `seasons[].stats` | string | A stats.json útvonala a seasons.json-hoz képest. |
| `seasons[].standings` | string | A standings.json útvonala a seasons.json-hoz képest. |

## history.json

Minden szezon tömör, meccsenkénti mutatói a csapatra és a játékosokra, a szezonok összehasonlításához. Ugyanazok a számok, mint a szezonok stats.json-jában (a bajnoki meccsekből, nézetenként: views.all, views.home …), csak meccsenkéntire osztva; a helyezés a standings.json-ból.

| Mező | Típus | Jelentés |
|---|---|---|
| `version` | const 1 | Formátum-verzió. |
| `team` | const "kozgaz-b" | Csapatkulcs. |
| `generated_at` | string | A fájl készítése (UTC). |
| `seasons` | array | A szezonok, a legrégebbi elöl. |
| `seasons[].season` | string | Szezonkulcs. |
| `seasons[].label` | string | Felirat (pl. 2025/26). |
| `seasons[].team` | object? | A csapat a bajnoki meccsekből (null, ha még nincs bajnoki meccs); ugyanaz, mint a team_views.all. |
| `seasons[].team.games` | integer | Bajnoki meccs. |
| `seasons[].team.wins` | integer | Győzelem. |
| `seasons[].team.losses` | integer | Vereség. |
| `seasons[].team.win_pct` | number | Győzelem-arány, % (egy tizedes). |
| `seasons[].team.ppg` | number | Dobott/meccs. |
| `seasons[].team.opp_ppg` | number | Kapott/meccs. |
| `seasons[].team.diff_per_game` | number | Különbség/meccs. |
| `seasons[].team.ft_pct` | number? | Büntető%, egy tizedes; null, ha nem volt kísérlet. |
| `seasons[].team.fg2_per_game` | number | Bedobott kettes/meccs, egy tizedes. |
| `seasons[].team.fg3_per_game` | number | Bedobott hármas/meccs, egy tizedes. |
| `seasons[].team.home_wins` | integer | Hazai győzelem. |
| `seasons[].team.home_games` | integer | Hazai meccs. |
| `seasons[].team.away_wins` | integer | Idegenbeli győzelem. |
| `seasons[].team.away_games` | integer | Idegenbeli meccs. |
| `seasons[].team.quarters` | array | Negyedátlagok. |
| `seasons[].team.quarters[].quarter` | integer | Negyed (1–4). |
| `seasons[].team.quarters[].kozgaz_avg` | number | Közgáz pont/meccs a negyedben. |
| `seasons[].team.quarters[].opponent_avg` | number | Ellenfél pont/meccs a negyedben. |
| `seasons[].team_views` | object? | A csapat a stats.json team_stats minden nézetében (null, ha a szezonnak nincs csapatszintje; ha van, de még nincs bajnoki meccs, minden nézet null); az app szűrői a szezonok táblázatát is így bontják. |
| `seasons[].team_views.all` | object? | Mint a team; null, ha nincs bajnoki meccs. |
| `seasons[].team_views.all.games` | integer | Bajnoki meccs. |
| `seasons[].team_views.all.wins` | integer | Győzelem. |
| `seasons[].team_views.all.losses` | integer | Vereség. |
| `seasons[].team_views.all.win_pct` | number | Győzelem-arány, % (egy tizedes). |
| `seasons[].team_views.all.ppg` | number | Dobott/meccs. |
| `seasons[].team_views.all.opp_ppg` | number | Kapott/meccs. |
| `seasons[].team_views.all.diff_per_game` | number | Különbség/meccs. |
| `seasons[].team_views.all.ft_pct` | number? | Büntető%, egy tizedes; null, ha nem volt kísérlet. |
| `seasons[].team_views.all.fg2_per_game` | number | Bedobott kettes/meccs, egy tizedes. |
| `seasons[].team_views.all.fg3_per_game` | number | Bedobott hármas/meccs, egy tizedes. |
| `seasons[].team_views.all.home_wins` | integer | Hazai győzelem. |
| `seasons[].team_views.all.home_games` | integer | Hazai meccs. |
| `seasons[].team_views.all.away_wins` | integer | Idegenbeli győzelem. |
| `seasons[].team_views.all.away_games` | integer | Idegenbeli meccs. |
| `seasons[].team_views.all.quarters` | array | Negyedátlagok. |
| `seasons[].team_views.all.quarters[].quarter` | integer | Negyed (1–4). |
| `seasons[].team_views.all.quarters[].kozgaz_avg` | number | Közgáz pont/meccs a negyedben. |
| `seasons[].team_views.all.quarters[].opponent_avg` | number | Ellenfél pont/meccs a negyedben. |
| `seasons[].team_views.home` | object? | Mint a team, csak a hazai meccseiből; null, ha nincs ilyen meccs. |
| `seasons[].team_views.away` | object? | Mint a team, csak az idegenbeli meccseiből; null, ha nincs ilyen meccs. |
| `seasons[].team_views.regular` | object? | Mint a team, csak az alapszakasz meccseiből; null, ha nincs ilyen meccs (rájátszás nélküli szezonban mindig). |
| `seasons[].team_views.playoff` | object? | Mint a team, csak a rájátszás meccseiből; null, ha nincs ilyen meccs (rájátszás nélküli szezonban mindig). |
| `seasons[].team_views.regular_home` | object? | Mint a team, csak az alapszakasz hazai meccseiből; null, ha nincs ilyen meccs (rájátszás nélküli szezonban mindig). |
| `seasons[].team_views.regular_away` | object? | Mint a team, csak az alapszakasz idegenbeli meccseiből; null, ha nincs ilyen meccs (rájátszás nélküli szezonban mindig). |
| `seasons[].team_views.playoff_home` | object? | Mint a team, csak a rájátszás hazai meccseiből; null, ha nincs ilyen meccs (rájátszás nélküli szezonban mindig). |
| `seasons[].team_views.playoff_away` | object? | Mint a team, csak a rájátszás idegenbeli meccseiből; null, ha nincs ilyen meccs (rájátszás nélküli szezonban mindig). |
| `seasons[].standings` | array | A Közgáz helyezése a szezon tabelláin (alapszakasz elöl). |
| `seasons[].standings[].competition` | string | Bajnokság-kód. |
| `seasons[].standings[].competition_label` | string | Bajnokság neve. |
| `seasons[].standings[].phase` | string (regular | playoff | cup) | Szakasz. |
| `seasons[].standings[].rank` | integer | Helyezés (1-től). |
| `seasons[].standings[].teams` | integer | A tabella csapatainak száma. |
| `players` | array | A játékosok, mindegyik a saját szezonjaival (a legrégebbi elöl). A szezonokat a játékoskulcs köti össze. |
| `players[].key` | string | Játékoskulcs: licencszám, vagy ha nincs, a névből képzett slug. |
| `players[].key_type` | string (license | name_slug) | license / name_slug. |
| `players[].name` | string | Név a legutóbbi szezonja jegyzőkönyvei szerint. |
| `players[].seasons` | array | A szezonjai, amelyekben bajnoki meccsen pályára lépett. |
| `players[].seasons[].season` | string | Szezonkulcs. |
| `players[].seasons[].games` | integer | Meccs. |
| `players[].seasons[].points` | integer | Pont. |
| `players[].seasons[].ppg` | number | Pont/meccs. |
| `players[].seasons[].max_points` | integer | Legtöbb pont egy meccsen. |
| `players[].seasons[].fg2_per_game` | number | Bedobott kettes/meccs, egy tizedes. |
| `players[].seasons[].fg3_per_game` | number | Bedobott hármas/meccs, egy tizedes. |
| `players[].seasons[].ft_made` | integer | Bedobott büntető. |
| `players[].seasons[].ft_att` | integer | Büntető-kísérlet. |
| `players[].seasons[].ft_pct` | number? | Büntető%, ahogy a stats.json-ban; null, ha nem volt kísérlet. |
| `players[].seasons[].pf_per_game` | number | Fault/meccs. |
| `players[].seasons[].views` | object | A szezon a stats.json players[].views minden nézetében; az app szűrői a játékos szezonjainak táblázatát is így bontják. |
| `players[].seasons[].views.all` | object? | Mint a szezon számai; null, ha nincs bajnoki meccs. |
| `players[].seasons[].views.all.games` | integer | Meccs. |
| `players[].seasons[].views.all.points` | integer | Pont. |
| `players[].seasons[].views.all.ppg` | number | Pont/meccs. |
| `players[].seasons[].views.all.max_points` | integer | Legtöbb pont egy meccsen. |
| `players[].seasons[].views.all.fg2_per_game` | number | Bedobott kettes/meccs, egy tizedes. |
| `players[].seasons[].views.all.fg3_per_game` | number | Bedobott hármas/meccs, egy tizedes. |
| `players[].seasons[].views.all.ft_made` | integer | Bedobott büntető. |
| `players[].seasons[].views.all.ft_att` | integer | Büntető-kísérlet. |
| `players[].seasons[].views.all.ft_pct` | number? | Büntető%, ahogy a stats.json-ban; null, ha nem volt kísérlet. |
| `players[].seasons[].views.all.pf_per_game` | number | Fault/meccs. |
| `players[].seasons[].views.home` | object? | Mint a szezon számai, csak a hazai meccseiből; null, ha nincs ilyen meccs. |
| `players[].seasons[].views.away` | object? | Mint a szezon számai, csak az idegenbeli meccseiből; null, ha nincs ilyen meccs. |
| `players[].seasons[].views.regular` | object? | Mint a szezon számai, csak az alapszakasz meccseiből; null, ha nincs ilyen meccs (rájátszás nélküli szezonban mindig). |
| `players[].seasons[].views.playoff` | object? | Mint a szezon számai, csak a rájátszás meccseiből; null, ha nincs ilyen meccs (rájátszás nélküli szezonban mindig). |
| `players[].seasons[].views.regular_home` | object? | Mint a szezon számai, csak az alapszakasz hazai meccseiből; null, ha nincs ilyen meccs (rájátszás nélküli szezonban mindig). |
| `players[].seasons[].views.regular_away` | object? | Mint a szezon számai, csak az alapszakasz idegenbeli meccseiből; null, ha nincs ilyen meccs (rájátszás nélküli szezonban mindig). |
| `players[].seasons[].views.playoff_home` | object? | Mint a szezon számai, csak a rájátszás hazai meccseiből; null, ha nincs ilyen meccs (rájátszás nélküli szezonban mindig). |
| `players[].seasons[].views.playoff_away` | object? | Mint a szezon számai, csak a rájátszás idegenbeli meccseiből; null, ha nincs ilyen meccs (rájátszás nélküli szezonban mindig). |
