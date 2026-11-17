# Andris forkja — statisztika-JSON a Gametime appnak

Ez a fork Dani `mkosz-dashboard` repójából készült, egyetlen célra: a Közgáz B
statisztikáit JSON-ban közzétenni a Gametime app „Eredmények” fülének. A
kozgazkosar.hu-t továbbra is Dani repója építi; ez a fork nem épít honlapot.

## Mi más, mint Dani repójában

- `export_stats.py` — a JSON-export (`stats.json`, `standings.json`, `seasons.json`,
  minden elérhető szezonra, és `history.json` a szezonok összehasonlításához). Csak a
  `generate_dashboards.py` függvényeit hívja; a `history.json` a szezonok `stats.json`-
  jának számait osztja meccsenkéntire.
- `generate_dashboards.py` — a számítások kiemelve, hogy a honlap és a JSON ugyanazt
  a kódot használja (a honlap HTML-je byte-ra ugyanaz maradt, mindkét szezonra
  ellenőrizve):
  - `compute_match_view()` — a meccsoldal minden számított értéke (negyedek,
    összesítő, eredmény alakulása, érdekességek, negyed-MVP-k, pontmegoszlás,
    faultok időrendje, vezetési idő); a `generate_match_page()` ebből épít HTML-t;
  - `_filled_minutes()` — a kosarak percének előre kitöltése (a becsült percek
    jelölésével), a záró 5 perc is ezt használja;
  - `get_player_bundle()` — egy játékos egy nézetének lekérdezései;
  - `_compute_player_view(..., with_ids=True)` — a meccssorok azonosítókkal;
  - `scrape_standings_tables()` — az MKOSZ-oldal összes tabellája (rájátszásnál
    csoportonként), a `scrape_standings()` ebből az elsőt adja, mint eddig;
  - `get_match_details()` a játékosoknál a nyers licencszámot is visszaadja;
  - `LEAGUE_METRICS`, `rank_league()`, `league_is_kg()` — a csoport-összehasonlítás
    mutatói és rangsora; a `generate_league_comparison_page()` és a JSON
    `league_comparison[]`-je is ebből készül.
- `box_score_repair.py` — a Közgáz B hiányzó box score-sorainak pótlása a PDF-
  jegyzőkönyvekből, a letöltött adatbázis ideiglenes másolatában (Dani kiolvasója a
  fix sorablakok miatt az idei PDF-ekben kihagyhatja az első és a 12. sort). Dani
  kiolvasójának változatlan másolatára épül (`vendor/mkosz_scoresheet/`), csak a
  sorhatárokat adja meg a licencsorokból; kézi tartalék: `data/box_score_overrides.json`.
  Ugyanígy javítja a Közgáz B meccsein a kétszer számolt faultokat (védőkorláttal:
  csapatfault-jelölések és Dani időrendje); az ismert, nem javítható eltérések
  listája: `data/known_foul_mismatches.json`.
  Az ok, a védőkorlát és a Dani kiolvasójához javasolt javítás:
  `docs/scoresheet-extraction-fix.md`. Tesztek: `tests/`.
- `export_stats.py` `APP_SHORT_NAMES` — ahol az app rövid neve eltér a honlap
  szótárától (`CALENDAR_SHORT`), pl. „RADOBASKET Törökbálint” → „Rado.Tbálint”
  (a honlapon marad „Rado.bálint”); csak a JSON tabellás rövid neveire hat.
- `stats_schema.py` — a séma egy helyen; ebből készül a `schemas/*.schema.json` és a
  `docs/STATS_JSON.md`, és ez ellenőrzi a kimenetet.
- `.github/workflows/stats-export.yml` — napi futás 18:47 UTC-kor (Dani mkosz-stats
  importja után): tesztek, box score-pótlás, export a javított másolatból,
  közzététel a fork GitHub Pages oldalán. A többi workflow
  (`daily-update.yml`, `update-attendance.yml`) a forkban ki van kapcsolva.

## Függőségek

- `jsonschema` — a kimenet séma-ellenőrzése.
- `PyMuPDF` (2.1-re rögzítve) — a PDF-jegyzőkönyvek kiolvasása a box score-pótláshoz;
  Dani kiolvasója és a honlap workflow-ja is ezt használja.

## Helyben

```bash
curl -fsSLo /tmp/mkosz_stats.sqlite https://raw.githubusercontent.com/pozsikdani/mkosz-stats/main/mkosz_stats.sqlite
pip install jsonschema PyMuPDF==2.1
REQUIRE_PDFS=1 python3 -m unittest discover -s tests -v
python3 box_score_repair.py --db /tmp/mkosz_stats.sqlite --out /tmp/mkosz_stats_repaired.sqlite --pdf-dir /tmp/kozgaz-pdfs
python3 export_stats.py --db /tmp/mkosz_stats_repaired.sqlite --out public
python3 stats_schema.py check public
# séma vagy leírás változott:
python3 stats_schema.py write
```
