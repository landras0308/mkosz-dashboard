# Andris forkja — statisztika-JSON a Gametime appnak

Ez a fork Dani `mkosz-dashboard` repójából készült, egyetlen célra: a Közgáz B
statisztikáit JSON-ban közzétenni a Gametime app „Eredmények” fülének. A
kozgazkosar.hu-t továbbra is Dani repója építi; ez a fork nem épít honlapot.

## Mi más, mint Dani repójában

- `export_stats.py` — a JSON-export (`stats.json`, `standings.json`, `seasons.json`,
  minden elérhető szezonra). Csak a `generate_dashboards.py` függvényeit hívja.
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
- `stats_schema.py` — a séma egy helyen; ebből készül a `schemas/*.schema.json` és a
  `docs/STATS_JSON.md`, és ez ellenőrzi a kimenetet.
- `.github/workflows/stats-export.yml` — napi futás 18:47 UTC-kor (Dani mkosz-stats
  importja után), közzététel a fork GitHub Pages oldalán. A többi workflow
  (`daily-update.yml`, `update-attendance.yml`) a forkban ki van kapcsolva.

## Helyben

```bash
curl -fsSLo /tmp/mkosz_stats.sqlite https://raw.githubusercontent.com/pozsikdani/mkosz-stats/main/mkosz_stats.sqlite
python3 export_stats.py --db /tmp/mkosz_stats.sqlite --out public
pip install jsonschema && python3 stats_schema.py check public
# séma vagy leírás változott:
python3 stats_schema.py write
```
