#!/usr/bin/env python3
"""A Közgáz B hiányzó játékossorainak pótlása a jegyzőkönyvekből (Andris forkja).

Dani mkosz-scoresheet kiolvasója a játékossorokat fix y-ablakokban keresi. A
2026/27-es PDF-ekben a sorköz és az első sor helye ettől eltér, ezért a csapat
első vagy 12. sora kimaradhat a box score-ból, miközben a kosarai megvannak
(docs/scoresheet-extraction-fix.md). Ez a modul:

1. letölti a Közgáz B meccseinek PDF-jegyzőkönyveit (bajnoki és kupa, minden
   szezon, ami az adatbázisban van);
2. Dani kiolvasójával (vendor/mkosz_scoresheet, változatlan másolat) újra kiolvassa
   őket, de a játékos- és faultsorokat a csapatrészben ténylegesen megtalált
   licencszám-sorokhoz igazítja; a futó eredmény, a kosarak, a mezszám-egyeztetés
   és a játékosstat Dani függvényeivel készül;
3. a letöltött adatbázis másolatában pótolja a Közgáz hiányzó player_game_stats
   sorait — csak ha a sor tényleg hiányzik, és a pótlás után a játékosok összege
   egyezik a hivatalos eredménnyel és a kosarak (scoring_events) összegével;
4. ugyanígy alkalmazza a data/box_score_overrides.json kézi felülírásait;
5. a Közgáz kétszer számolt faultjait a PDF-ből javítja, ha a javított érték
   játékosonként csak csökken, negyedenként kiadja a jegyzőkönyv csapatfault-jelöléseit,
   és illeszkedik Dani personal_fouls időrendjéhez; az ismert, nem javítható
   eltérések (data/known_foul_mismatches.json, --known-fouls) egyetlen összesítő
   figyelmeztetésben jelennek meg.

A pótolt sorokat a repaired_rows, a javított faultokat a repaired_fouls tábla jelöli
a másolatban: az export_stats.py ezekből jelöli őket a JSON-ban, és a repaired_rows-ból
számolja a pótlás előtti box_score_check-et. A licencszám a másolatban marad, a
kimenetbe (napló, összesítő) nem kerül.

Használat:
  python3 box_score_repair.py --db mkosz_stats.sqlite --out javitott.sqlite \\
      --pdf-dir /tmp/kozgaz-pdfs [--overrides data/box_score_overrides.json] [--no-download]
  python3 box_score_repair.py key <licencszám>    # a felülíró fájl license_key-e
"""

import argparse
import collections
import hashlib
import json
import os
import shutil
import sqlite3
import statistics
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "mkosz_scoresheet"))
import extract_scoresheet as ex  # noqa: E402  (Dani kiolvasója, változatlanul)

import generate_dashboards as gd  # noqa: E402

TEAM_KEY = "kozgaz-b"
PDF_URL = "https://hunbasketimg.webpont.com/pdf/{season}/{gamecode}.pdf"
USER_AGENT = "Mozilla/5.0 (mkosz-dashboard fork; Gametime statisztika-JSON)"

# A sorhatárok a licencsorhoz (a licencszám karaktereinek y-ja) mérve; a 2025/26-os
# és 2026/27-es PDF-eken mért tartalom a licencsorhoz képest: név −5…+9 px (kétsoros
# név: −4 és +8), X 0…+2, fault fő számjegye −4…+2, alsó/felső indexe −3,5…
# A sor egy sorköznyi (pitch) magas, és a következő sor ugyanilyen pontjáig tart.
# - Név-sáv: 13,5 px-lel a licencsor fölött kezdődik, így Dani „a sor tetejétől 8 px-en
#   belüli sort eldobjuk” szabálya (a fölötte lévő sor tördelt nevére) a saját −5 px-es
#   első sort még megtartja, a +8/+9 px-es második sor pedig a sávon belül marad.
# - Fault-sáv: 8 px-lel fölötte; Dani extract_personal_fouls()-a a sor aljához még
#   12 px-t ad, ezért a sor magassága pitch − 12, így a fault-sáv épp a következő sor
#   fault-sávjáig tart, és nem számolja kétszer a következő sor faultjait.
NAME_TOP = 13.5
FOUL_TOP = 8.0
FOUL_EXTENSION = 12.0         # Dani extract_personal_fouls(): y_max + 12
LICENSE_X = (20, 85)          # Dani extract_players(): a licencszám oszlopa
LICENSE_MIN_DIGITS = 5        # a licencszámok 6 jegyűek; az edzőé "(2026_…)" alakú
FOUL_SLOTS = {"A": ex.FOUL_SLOTS_A, "B": ex.FOUL_SLOTS_B}
NO_COACH = {"coach_y": (-2.0, -1.0), "asst_y": (-2.0, -1.0)}

REPAIRED_SCHEMA = """
    CREATE TABLE IF NOT EXISTS repaired_rows (
        gamecode       TEXT NOT NULL,
        team           TEXT NOT NULL CHECK (team IN ('A','B')),
        license_number TEXT,
        jersey_number  INTEGER,
        player_name    TEXT NOT NULL,
        points         INTEGER NOT NULL,
        origin         TEXT NOT NULL CHECK (origin IN ('pdf','override')),
        PRIMARY KEY (gamecode, team, player_name)
    )
"""
REPAIRED_FOULS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS repaired_fouls (
        gamecode       TEXT NOT NULL,
        team           TEXT NOT NULL CHECK (team IN ('A','B')),
        license_number TEXT NOT NULL,
        jersey_number  INTEGER,
        player_name    TEXT NOT NULL,
        pf_source      INTEGER,
        pf_repaired    INTEGER NOT NULL,
        PRIMARY KEY (gamecode, team, license_number)
    )
"""
FOUL_FIELDS = ("jersey_number", "foul_number", "minute", "quarter", "foul_type", "foul_category",
               "free_throws", "offsetting")


def license_key(license_number):
    """A felülíró fájl kulcsa: a licencszámból képzett, nem visszafordítható kivonat.

    Figyelem: a licencszám 6 jegyű, ezért kipróbálással visszakereshető; a kulcs
    csak azt biztosítja, hogy a fájlban ne álljon a licencszám olvashatóan."""
    digest = hashlib.sha256(f"{TEAM_KEY}:license:{license_number}".encode()).hexdigest()
    return f"lk_{digest[:16]}"


# ─────────────────────────── javított sorkeresés ───────────────────────────

def _label_lines(all_chars, label, x_max):
    """A `label`-t tartalmazó nyomtatott sorok y-ja, felülről lefelé."""
    lines = {}
    for ch in all_chars:
        if ch["x"] <= x_max:
            key = next((k for k in lines if abs(k - ch["y"]) <= 3.0), ch["y"])
            lines.setdefault(key, []).append(ch)
    out = []
    for y in sorted(lines):
        cs = sorted(lines[y], key=lambda c: c["x"])
        if label in "".join(c["c"] for c in cs):
            out.append((y, cs[0]["x"]))
    return out


def team_region(all_chars, team):
    """A csapat játékossorainak y-tartománya: a „Játék engedély száma / Játékos neve”
    fejléc alatt, az „EDZŐ” felirat fölött. None, ha a feliratok nem találhatók."""
    idx = 0 if team == "A" else 1
    headers = [y for y, _ in _label_lines(all_chars, "engedély", 300)]
    assistants = [y for y, _ in _label_lines(all_chars, "SEGÉD", 300)]
    coaches = [y for y, x in _label_lines(all_chars, "EDZŐ", 300)
               if x < 20 and not any(abs(y - s) <= 3 for s in assistants)]
    if len(headers) < 2 or len(coaches) < 2:
        return None
    return headers[idx] + 3.0, coaches[idx] - 3.0


def license_lines(all_chars, team):
    """A csapatrészben ténylegesen megtalált licencszám-sorok y-ja (Dani oszlopában,
    a hivatalos kék színnel, csak számjegyek)."""
    region = team_region(all_chars, team)
    if region is None:
        return []
    lines = {}
    for ch in all_chars:
        if (LICENSE_X[0] <= ch["x"] <= LICENSE_X[1] and region[0] <= ch["y"] <= region[1]
                and ch["color"] == ex.OFFICIAL_BLUE):
            key = next((k for k in lines if abs(k - ch["y"]) <= 3.0), ch["y"])
            lines.setdefault(key, []).append(ch)
    ys = []
    for cs in lines.values():
        # A sor elején álló számjegyek: egyes PDF-ekben a név is belelóg az oszlopba
        # (x≈79-től), az edzői sor pedig "(" jellel kezdődik.
        lead = []
        for c in sorted(cs, key=lambda c: c["x"]):
            if not c["c"].isdigit():
                break
            lead.append(c)
        if len(lead) >= LICENSE_MIN_DIGITS:
            ys.append(min(c["y"] for c in lead))
    return sorted(ys)


def row_lines(all_chars, team):
    """[(licencsor y, sorköz)] — a sorköz a következő licencsorig, az utolsónál a mediánja."""
    ys = license_lines(all_chars, team)
    gaps = [b - a for a, b in zip(ys, ys[1:])]
    pitch = statistics.median(gaps) if gaps else 24.5
    return [(y, gaps[i] if i < len(gaps) else pitch) for i, y in enumerate(ys)]


TEAM_FOUL_BOXES = 4           # a „Csapat hibák” mező negyedenként 4 X-et jelölhet


def team_fouls(all_chars, team):
    """A „Csapat hibák” mező negyedenkénti X-jelölései ({1: db, …, 4: db}), a feliratokhoz
    igazítva: a csapat „"A"/"B" Csapat:” felirata és a játékostábla fejléce között a két
    „Negyed 1 … 2 …” / „Negyed 3 … 4 …” sor; az X-ek a két negyedszám után. Dani
    extract_team_fouls()-a fix ablakkal olvas, ami az új elrendezésben elcsúszik.
    None, ha a feliratok nem találhatók."""
    idx = 0 if team == "A" else 1
    labels = [y for y, x in _label_lines(all_chars, "Csapat:", 300) if x < 30]
    headers = [y for y, _ in _label_lines(all_chars, "engedély", 300)]
    if len(labels) < 2 or len(headers) < 2:
        return None
    out = {}
    for y, _ in _label_lines(all_chars, "egyed", 480):
        if not labels[idx] < y < headers[idx]:
            continue
        line = sorted((c for c in all_chars if abs(c["y"] - y) <= 3.0 and 150 <= c["x"] <= 480),
                      key=lambda c: c["x"])
        digits = [c for c in line if c["c"] in "1234"]
        if len(digits) != 2:
            return None
        first, second = digits
        out[int(first["c"])] = sum(1 for c in line if c["c"].upper() == "X" and first["x"] < c["x"] < second["x"])
        out[int(second["c"])] = sum(1 for c in line if c["c"].upper() == "X" and c["x"] > second["x"])
    return out if set(out) == {1, 2, 3, 4} else None


def _row_cfg(top, height):
    return {"y_start": top, "y_end": top + height, "row_height": height, "max_rows": 1}


def extract_rows(all_chars, all_circles, team):
    """[(licencsor, játékos)] — Dani extract_players()-e soronként, a javított sorhatárokkal."""
    out = []
    for y, pitch in row_lines(all_chars, team):
        found = ex.extract_players(all_chars, all_circles, team, _row_cfg(y - NAME_TOP, pitch), NO_COACH)
        out.extend(((y, pitch), p) for p in found if p["role"] in ("player", "captain"))
    return out


def extract_fouls(all_chars, all_circles, team, rows):
    """Dani extract_personal_fouls()-a soronként, a játékos saját sorában."""
    fouls = []
    for (y, pitch), player in rows:
        cfg = _row_cfg(y - FOUL_TOP, pitch - FOUL_EXTENSION)
        fouls += ex.extract_personal_fouls(all_chars, all_circles, team, cfg, FOUL_SLOTS[team], [player], None)
    return fouls


def extract_box_score(pdf_path):
    """Egy PDF box score-ja Dani láncán (futó eredmény → kosarak → mezszám-egyeztetés →
    player_game_stats), a javított játékos- és faultsorokkal. None, ha képes a PDF."""
    all_chars, all_circles = ex.extract_all_from_pdf(pdf_path)
    if not all_chars:
        return None
    template = ex.detect_template(all_chars)
    info = ex.extract_match_info(all_chars, template)
    rs_records = ex.extract_running_score(all_chars, all_circles, template)
    players, fouls = [], []
    for team in ("A", "B"):
        rows = extract_rows(all_chars, all_circles, team)
        players += [p for _, p in rows]
        fouls += extract_fouls(all_chars, all_circles, team, rows)

    mid = info["match_id"]
    conn = sqlite3.connect(":memory:")
    ex.create_schema(conn)
    ex.insert_match(conn, info, source_pdf=os.path.basename(pdf_path))
    ex.insert_players(conn, mid, players)
    ex.insert_personal_fouls(conn, mid, fouls)
    ex.insert_running_score(conn, mid, rs_records)
    ex.insert_scoring_events(conn, ex.compute_scoring_events(rs_records, players, mid))
    ex.reconcile_jersey_numbers(conn, mid)
    ex.compute_player_game_stats(conn, mid)
    rows = conn.execute("""
        SELECT team, jersey_number, license_number, name, points, fg2_made, fg3_made,
               ft_made, ft_attempted, personal_fouls, starter, entry_quarter
        FROM player_game_stats WHERE match_id = ? ORDER BY team, jersey_number
    """, (mid,)).fetchall()
    events = dict(conn.execute(
        "SELECT team, SUM(points) FROM scoring_events WHERE match_id = ? AND made = 1 GROUP BY team",
        (mid,)).fetchall())
    foul_rows = conn.execute(f"""
        SELECT team, {", ".join(FOUL_FIELDS)} FROM personal_fouls
        WHERE match_id = ? AND jersey_number IS NOT NULL ORDER BY team, quarter, id
    """, (mid,)).fetchall()
    conn.close()
    cols = ("team", "jersey", "license", "name", "points", "fg2_made", "fg3_made",
            "ft_made", "ft_att", "pf", "starter", "entry_quarter")
    return {
        "match_id": mid, "template": template["name"],
        "score_a": info["score_a"], "score_b": info["score_b"],
        "players": [dict(zip(cols, r)) for r in rows],
        "event_points": {"A": events.get("A", 0), "B": events.get("B", 0)},
        "fouls": [dict(zip(("team",) + FOUL_FIELDS, f)) for f in foul_rows],
        "team_fouls": {team: team_fouls(all_chars, team) for team in ("A", "B")},
    }


# ─────────────────────────── pótlás az adatbázisban ───────────────────────────

def kozgaz_matches(conn):
    """A Közgáz B lejátszott meccsei, a Közgáz oldalával."""
    pat = gd.TEAMS[TEAM_KEY]["team_pattern"]
    rows = conn.execute("""
        SELECT gamecode, season, comp_code, match_date, scoresheet_match_id, has_scoresheet,
               team_a_name, team_b_name, score_a, score_b,
               CASE WHEN team_a_name LIKE ? THEN 'A' ELSE 'B' END
        FROM matches
        WHERE (team_a_name LIKE ? OR team_b_name LIKE ?) AND score_a + score_b > 0
        ORDER BY match_date, gamecode
    """, (pat, pat, pat)).fetchall()
    out = []
    for gc, season, comp, date, sid, has_ss, ta, tb, sa, sb, side in rows:
        out.append({
            "gamecode": gc, "season": season, "comp": comp, "date": date,
            "scoresheet_match_id": sid, "has_scoresheet": bool(has_ss),
            "side": side, "opponent": tb if side == "A" else ta,
            "score_a": sa, "score_b": sb, "official": sa if side == "A" else sb,
        })
    return out


def box_rows(conn, gamecode, team):
    rows = conn.execute("""
        SELECT player_name, license_number, jersey_number, points
        FROM player_game_stats WHERE gamecode = ? AND team = ?
    """, (gamecode, team)).fetchall()
    return [{"name": n, "license": lic or None, "jersey": j, "points": p or 0} for n, lic, j, p in rows]


def event_points(conn, gamecode, team):
    r = conn.execute("SELECT SUM(points) FROM scoring_events WHERE gamecode = ? AND team = ? AND made = 1",
                     (gamecode, team)).fetchone()
    return r[0] or 0


def jersey_event_stats(conn, gamecode, team, jersey, license_number):
    """Egy mezszám kosarai a forrás-adatbázisban, Dani compute_player_game_stats()-ának
    képleteivel; csak a licenc nélküli vagy ugyanehhez a licenchez tartozó események."""
    r = conn.execute("""
        SELECT COALESCE(SUM(points), 0),
               COALESCE(SUM(CASE WHEN made=1 AND points=2 THEN 1 ELSE 0 END), 0),
               COALESCE(SUM(CASE WHEN made=1 AND points=3 THEN 1 ELSE 0 END), 0),
               COALESCE(SUM(CASE WHEN made=1 AND points=1 THEN 1 ELSE 0 END), 0),
               COALESCE(SUM(CASE WHEN points IN (0,1) THEN 1 ELSE 0 END), 0)
        FROM scoring_events
        WHERE gamecode = ? AND team = ? AND jersey_number = ?
          AND (license_number IS NULL OR license_number = '' OR license_number = ?)
    """, (gamecode, team, jersey, license_number)).fetchone()
    return dict(zip(("points", "fg2_made", "fg3_made", "ft_made", "ft_att"), r))


def known_name(conn, license_number):
    """A licencszámhoz az adatbázisban leggyakrabban rögzített név, vagy None."""
    r = conn.execute("""
        SELECT player_name FROM player_game_stats
        WHERE license_number = ? GROUP BY player_name ORDER BY COUNT(*) DESC, player_name LIMIT 1
    """, (license_number,)).fetchone()
    return r[0] if r else None


def _same_name(a, b):
    return gd.slugify(a or "") == gd.slugify(b or "")


def find_existing(existing, license_number, jersey, name):
    """'license' / 'name' / 'jersey', ha a sor (vagy egy ütköző sor) már megvan, különben None."""
    for r in existing:
        if license_number and r["license"] == license_number:
            return "license"
    for r in existing:
        if _same_name(r["name"], name):
            return "name"
    for r in existing:
        if jersey is not None and r["jersey"] == jersey:
            return "jersey"
    return None


def check_totals(conn, m, new_rows):
    """A védőkorlát: a pótlás utáni összeg = hivatalos eredmény = kosarak összege.
    (before, after, events) — after az új sorokkal együtt."""
    before = sum(r["points"] for r in box_rows(conn, m["gamecode"], m["side"]))
    after = before + sum(r["points"] for r in new_rows)
    return before, after, event_points(conn, m["gamecode"], m["side"])


def insert_rows(conn, m, rows, origin):
    gc, team = m["gamecode"], m["side"]
    for r in rows:
        conn.execute("""
            INSERT INTO player_game_stats
                (gamecode, team, player_name, license_number, jersey_number,
                 is_starter, entry_quarter, points, fg2_made, fg3_made, ft_made, ft_attempted,
                 personal_fouls, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'scoresheet')
        """, (gc, team, r["name"], r["license"], r["jersey"], int(bool(r["starter"])),
              r["entry_quarter"], r["points"], r["fg2_made"], r["fg3_made"], r["ft_made"],
              r["ft_att"], r["pf"]))
        # A mezszám licenc nélküli kosarai a pótolt játékoshoz (ahogy Dani
        # reconcile_jersey_numbers()-e tenné): így a negyedes bontás és az eredmény
        # alakulásának nevei is látják.
        conn.execute("""
            UPDATE scoring_events SET license_number = ?
            WHERE gamecode = ? AND team = ? AND jersey_number = ?
              AND (license_number IS NULL OR license_number = '')
        """, (r["license"], gc, team, r["jersey"]))
        conn.execute("""
            INSERT INTO repaired_rows (gamecode, team, license_number, jersey_number, player_name, points, origin)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (gc, team, r["license"], r["jersey"], r["name"], r["points"], origin))


def plan_from_pdf(conn, m, box):
    """A PDF-ből pótolandó sorok, vagy (None, ok), ha nem pótolhatók."""
    team = m["side"]
    sid = m["scoresheet_match_id"]
    if sid and box["match_id"] != sid:
        return None, f"a PDF azonosítója {box['match_id']}, az adatbázisé {sid}"
    if (box["score_a"], box["score_b"]) != (m["score_a"], m["score_b"]):
        return None, (f"a PDF végeredménye {box['score_a']}–{box['score_b']}, "
                      f"az adatbázisé {m['score_a']}–{m['score_b']}")
    fresh = [p for p in box["players"] if p["team"] == team]
    fresh_points = sum(p["points"] for p in fresh)
    if not fresh or fresh_points != m["official"]:
        return None, (f"a PDF újraolvasása sem teljes: {len(fresh)} Közgáz-sor, {fresh_points} pont "
                      f"(hivatalos {m['official']})")
    existing = box_rows(conn, m["gamecode"], team)
    rows, problems = [], []
    for p in fresh:
        # A név a játékos többi meccséről, ha van (a PDF-ből olvasott név ritka
        # elrendezésekben csonka lehet); különben a PDF-é. A meglévő sort mindkét
        # névvel keressük.
        name = known_name(conn, p["license"]) or p["name"]
        hits = {find_existing(existing, p["license"], p["jersey"], n) for n in (p["name"], name)}
        if hits & {"license", "name"}:
            continue
        if "jersey" in hits:
            problems.append(f"#{p['jersey']}: a mezszám egy másik játékosé az adatbázisban")
            continue
        db = jersey_event_stats(conn, m["gamecode"], team, p["jersey"], p["license"])
        pdf = {k: p[k] for k in db}
        if db != pdf:
            problems.append(f"#{p['jersey']}: a kosarak eltérnek (PDF {pdf['points']}, adatbázis {db['points']} pont)")
            continue
        rows.append({**p, "name": name})
    if problems:
        return None, "; ".join(problems)
    return rows, None


def resolve_license(conn, key):
    """A felülírás license_key-éhez tartozó licencszám és név a Közgáz B soraiból."""
    pat = gd.TEAMS[TEAM_KEY]["team_pattern"]
    rows = conn.execute("""
        SELECT pgs.license_number, pgs.player_name, COUNT(*)
        FROM player_game_stats pgs JOIN matches m ON m.gamecode = pgs.gamecode
        WHERE pgs.license_number IS NOT NULL AND pgs.license_number != ''
          AND ((pgs.team = 'A' AND m.team_a_name LIKE ?) OR (pgs.team = 'B' AND m.team_b_name LIKE ?))
        GROUP BY pgs.license_number, pgs.player_name
        ORDER BY COUNT(*) DESC
    """, (pat, pat)).fetchall()
    hits = {}
    for lic, name, _ in rows:
        if license_key(lic) == key:
            hits.setdefault(lic, name)
    if len(hits) != 1:
        return None, None
    return next(iter(hits.items()))


def plan_from_override(conn, m, ov):
    """(sorok, ok, hatástalan) egy felülírásra."""
    team = m["side"]
    want = "A" if ov.get("side") == "home" else "B" if ov.get("side") == "away" else None
    if want != team:
        return None, f"a side ({ov.get('side')!r}) nem a Közgáz oldala", False
    jersey, pf = ov.get("jersey"), ov.get("pf", 0)
    if not isinstance(jersey, int) or not isinstance(pf, int) or isinstance(pf, bool) or pf < 0:
        return None, "a jersey és a pf egész szám legyen", False
    lic, name = resolve_license(conn, ov.get("license_key"))
    if not lic:
        return None, ("a license_key egyetlen Közgáz B-játékoshoz sem tartozik (a játékosnak "
                      "licenccel kell szerepelnie legalább egy Közgáz B-meccsen)"), False
    existing = box_rows(conn, m["gamecode"], team)
    if find_existing(existing, lic, jersey, name):
        return [], "a sor már megvan (a forrásban vagy a PDF-ből pótolva), a felülírás hatástalan", True
    if sum(r["points"] for r in existing) == m["official"]:
        return [], "a meccs box score-ja teljes, a felülírás hatástalan", True
    stats = jersey_event_stats(conn, m["gamecode"], team, jersey, lic)
    row = {"name": name, "license": lic, "jersey": jersey, "starter": bool(ov.get("starter")),
           "entry_quarter": 1 if ov.get("starter") else None, "pf": pf, **stats}
    return [row], None, False


def _apply(conn, m, rows, origin, log, title):
    """A védőkorlát, és a sorok beírása egy SAVEPOINT-ban; True, ha beírta."""
    b, a, ev = check_totals(conn, m, rows)
    if not (a == m["official"] == ev):
        log("warning", title, f"a pótlás után {a} pont lenne, a hivatalos eredmény {m['official']}, "
                              f"a kosarak összege {ev}; nem pótolva")
        return False
    conn.execute("SAVEPOINT repair_rows")
    try:
        insert_rows(conn, m, rows, origin)
    except sqlite3.Error as e:
        conn.execute("ROLLBACK TO repair_rows")
        conn.execute("RELEASE repair_rows")
        log("warning", title, f"a sor nem írható be ({e}); nem pótolva")
        return False
    conn.execute("RELEASE repair_rows")
    return True


def _foul_quarter(q):
    return min(int(q), 4)  # a hosszabbítás faultjai a 4. negyed csapatfaultjaihoz számítanak


def foul_timeline_matches(db_events, pdf_events):
    """A javított faultok illeszkednek-e Dani personal_fouls időrendjéhez: a javított
    (negyed, perc) események mind megvannak benne, és Dani többlet-eseményei mind egy
    valódi fault ismétlései (ugyanaz a negyed és perc) — a fix ablak kétszer számolása."""
    db = collections.Counter(db_events)
    pdf = collections.Counter(pdf_events)
    return not (pdf - db) and set(db - pdf) <= set(pdf)


# Miért nem javít a fork egy meccs faultjain (a kód a data/known_foul_mismatches.json-ban
# is ez).
FOUL_REASONS = {
    "unknown_row": "a forrás egy Közgáz-sorát a PDF újraolvasása nem ismeri",
    "sum": "a javított faultok összege nem egyezik a jegyzőkönyv játékos-faultjaival",
    "team_marks": "a javított faultok nem adják ki a jegyzőkönyv csapatfault-jelöléseit",
    "timeline": "Dani personal_fouls időrendjéhez nem illeszkednek (az időrend sérült vagy hiányzik)",
    "increase": "a javított fault egy játékosnál több lenne Dani értékénél (a kétszer számolás csak csökkenthet)",
    "error": "hiba az összevetéskor",
}


def plan_fouls(conn, m, box):
    """A Közgáz-sorok javított faultjai: (változások, ok). A változás
    (sor, Dani értéke, javított érték); ([], None), ha nincs eltérés; (None, (kód,
    részletek)), ha eltérés van, de a védőkorlát nem engedi a javítást."""
    team = m["side"]
    fresh = {p["license"]: p for p in box["players"] if p["team"] == team}
    rows = conn.execute("""
        SELECT player_name, license_number, jersey_number, personal_fouls
        FROM player_game_stats WHERE gamecode = ? AND team = ?
    """, (m["gamecode"], team)).fetchall()
    changes, unknown = [], []
    for name, lic, jersey, pf in rows:
        p = fresh.get(lic) if lic else None
        if p is None:
            unknown.append(f"#{jersey}")
        elif (pf or 0) != p["pf"]:
            changes.append(({"name": name, "license": lic, "jersey": jersey}, pf or 0, p["pf"]))
    if not changes:
        return [], None
    if unknown:
        return None, ("unknown_row", f"a forrás {', '.join(unknown)} sorát a PDF újraolvasása nem ismeri")
    events = [f for f in box["fouls"] if f["team"] == team]
    # Minden forrás-sor ismert, így a javított összeg a PDF szerinti értékek összege; ha a
    # PDF-ben olyan játékosnak is van faultja, akinek nincs sora, ez nem egyezik.
    if sum(fresh[lic]["pf"] for _, lic, _, _ in rows) != len(events):
        return None, ("sum", FOUL_REASONS["sum"])
    marks = (box.get("team_fouls") or {}).get(team)
    per_q = collections.Counter(_foul_quarter(f["quarter"]) for f in events)
    capped = {q: min(per_q.get(q, 0), TEAM_FOUL_BOXES) for q in (1, 2, 3, 4)}
    if marks is None or capped != marks:
        return None, ("team_marks", f"a javított faultok negyedenként {[per_q.get(q, 0) for q in (1, 2, 3, 4)]}, "
                      f"a jegyzőkönyv csapatfault-jelölései "
                      f"{[marks[q] for q in (1, 2, 3, 4)] if marks else 'nem olvashatók'}")
    db_events = [(q, str(mi)) for q, mi in conn.execute("""
        SELECT quarter, minute FROM personal_fouls
        WHERE gamecode = ? AND team = ? AND jersey_number IS NOT NULL
    """, (m["gamecode"], team))]
    if not foul_timeline_matches(db_events, [(f["quarter"], str(f["minute"])) for f in events]):
        return None, ("timeline", "a javított faultok nem illeszkednek a forrás personal_fouls időrendjéhez")
    # A kétszer számolás csak többletet okoz: ha a javított érték valakinél nagyobb,
    # az nem ez a hiba (pl. két játékos faultja felcserélődött), nem javítunk. Utolsóként
    # nézzük, hogy a sérült forrás (időrend, jelölések) maradjon a jelzett ok.
    more = [f"#{row['jersey']} ({source} → {pf})" for row, source, pf in changes if pf > source]
    if more:
        return None, ("increase", f"{FOUL_REASONS['increase']}: {', '.join(more)}")
    return changes, None


def apply_fouls(conn, m, box, changes):
    """A javított faultok beírása: a player_game_stats faultjai, és a Közgáz oldal
    mezszámos personal_fouls sorai (időrend, T/U) a PDF-ből; a mezszám nélküli (edzői)
    sorok maradnak."""
    gc, team = m["gamecode"], m["side"]
    for row, pf_source, pf in changes:
        conn.execute("UPDATE player_game_stats SET personal_fouls = ? WHERE gamecode = ? AND team = ? "
                     "AND license_number = ?", (pf, gc, team, row["license"]))
        conn.execute("""
            INSERT INTO repaired_fouls (gamecode, team, license_number, jersey_number, player_name, pf_source, pf_repaired)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (gc, team, row["license"], row["jersey"], row["name"], pf_source, pf))
    conn.execute("DELETE FROM personal_fouls WHERE gamecode = ? AND team = ? AND jersey_number IS NOT NULL",
                 (gc, team))
    for f in box["fouls"]:
        if f["team"] == team:
            conn.execute(f"""
                INSERT INTO personal_fouls (gamecode, team, {", ".join(FOUL_FIELDS)})
                VALUES (?, ?, {", ".join("?" * len(FOUL_FIELDS))})
            """, (gc, team, *(f[k] for k in FOUL_FIELDS)))


def _apply_fouls(conn, m, box, changes, log, title):
    conn.execute("SAVEPOINT repair_fouls")
    try:
        apply_fouls(conn, m, box, changes)
    except Exception as e:  # bármilyen hiba: a meccs faultjai maradnak, a többi pótlás nem vész el
        conn.execute("ROLLBACK TO repair_fouls")
        conn.execute("RELEASE repair_fouls")
        log("warning", title, f"a faultok nem írhatók be ({e}); nem javítva")
        return False
    conn.execute("RELEASE repair_fouls")
    return True


def _season_label(season):
    """'x2526' → '2025/26'."""
    return f"20{season[1:3]}/{season[3:5]}" if len(season or "") == 5 else str(season)


def repair(conn, pdf_paths, overrides, log, extract=extract_box_score, known_fouls=None):
    """A pótlás a megnyitott (másolat-)adatbázisban. pdf_paths: {gamecode: útvonal};
    known_fouls: {gamecode: okkód} — az ismert, nem javítható fault-eltérések, amelyek
    egyenként helyett egy összesítő figyelmeztetésben jelennek meg. Visszaad egy
    összesítő sort meccsenként."""
    known_fouls = known_fouls or {}
    known_hits = []
    conn.execute(REPAIRED_SCHEMA)
    conn.execute(REPAIRED_FOULS_SCHEMA)
    by_game = {}
    for ov in overrides:
        if not isinstance(ov, dict):
            log("warning", "Felülírás", f"hibás bejegyzés: {ov!r}")
            continue
        by_game.setdefault(ov.get("gamecode"), []).append(ov)
    summary = []
    matches = kozgaz_matches(conn)
    known = {m["gamecode"] for m in matches}
    for gc in sorted(set(by_game) - known, key=str):
        log("warning", f"Felülírás: {gc}", "nincs ilyen lejátszott Közgáz B-meccs az adatbázisban")
    for m in matches:
        label = f"{m['date']} {m['gamecode']} ({m['opponent']})"
        before = sum(r["points"] for r in box_rows(conn, m["gamecode"], m["side"]))
        status, added, fouls, foul_note = "ok", [], [], ""

        path = pdf_paths.get(m["gamecode"])
        box = None
        if path:
            try:
                box = extract(path)
            except Exception as e:  # egy rossz PDF ne állítsa le a többit
                log("warning", f"Kiolvasás: {label}", f"hiba a PDF kiolvasásakor: {e}")
            if box is None:
                log("notice", f"Kiolvasás: {label}", "a PDF nem olvasható (képes vagy hibás), nem ellenőrizve")
        if box:
            try:
                rows, why = plan_from_pdf(conn, m, box)
            except Exception as e:
                rows, why = None, f"hiba a PDF összevetésekor: {e}"
            if rows is None:
                log("warning", f"Nem pótolva: {label}", why)
                status = "nem pótolva"
            elif rows:
                if _apply(conn, m, rows, "pdf", log, f"Nem pótolva: {label}"):
                    added += rows
                else:
                    status = "nem pótolva"

        for ov in by_game.get(m["gamecode"], []):
            title = f"Felülírás: {label}"
            try:
                rows, why, noop = plan_from_override(conn, m, ov)
            except Exception as e:
                rows, why, noop = None, f"hiba: {e}", False
            if noop:
                log("notice", title, f"#{ov.get('jersey')}: {why}")
            elif rows is None:
                log("warning", title, f"#{ov.get('jersey')}: {why}")
            elif _apply(conn, m, rows, "override", log, title):
                added += rows

        if box and status == "nem pótolva":
            foul_note = "nem ellenőrizve (a sorpótlás nem sikerült)"
        if box and status != "nem pótolva":
            title = f"Fault nem javítva: {label}"
            try:
                changes, why = plan_fouls(conn, m, box)
            except Exception as e:
                changes, why = None, ("error", f"hiba a faultok összevetésekor: {e}")
            if changes is None:
                code, detail = why
                if known_fouls.get(m["gamecode"]) == code:
                    known_hits.append((m, code))
                    foul_note = "ismert eltérés"
                else:
                    log("warning", title, detail)
                    foul_note = "nem javítva"
            else:
                if m["gamecode"] in known_fouls:
                    log("notice", f"Ismert fault-eltérés megszűnt: {label}",
                        "törölhető a data/known_foul_mismatches.json-ból")
                if changes:
                    if _apply_fouls(conn, m, box, changes, log, title):
                        fouls = changes
                        for row, pf_source, pf in changes:
                            log("notice", f"Fault javítva: {label}",
                                f"#{row['jersey']} {row['name']}: {pf_source} → {pf} fault")
                    else:
                        foul_note = "nem javítva"

        after = before + sum(r["points"] for r in added)
        for r in added:
            log("notice", f"Pótolt sor: {label}",
                f"#{r['jersey']} {r['name']}: {r['points']} pont, {r['pf']} fault"
                f"{', kezdő' if r['starter'] else ''}")
        if added:
            status = "pótolva"
        if after != m["official"]:
            log("warning", f"Eltérés maradt: {label}",
                f"a játékosokhoz {after} pont tartozik, a hivatalos eredmény {m['official']}")
            if status == "ok":
                status = "eltérés"
        if not path and m["has_scoresheet"] and not str(m["scoresheet_match_id"] or "").startswith("WEB-"):
            log("warning", f"Nincs PDF: {label}", "a jegyzőkönyv nem tölthető le, nem ellenőrizve")
        summary.append({**{k: m[k] for k in ("gamecode", "date", "opponent", "official")},
                        "before": before, "after": after, "status": status,
                        "added": [(r["jersey"], r["name"], r["points"]) for r in added],
                        "fouls": [(row["jersey"], row["name"], pf_source, pf) for row, pf_source, pf in fouls],
                        "foul_note": foul_note})
    if known_hits:
        seasons = ", ".join(sorted({_season_label(m["season"]) for m, _ in known_hits}))
        reasons = collections.Counter(code for _, code in known_hits)
        log("warning", "Fault nem javítva (ismert eltérések)",
            f"{len(known_hits)} meccs ({seasons}): "
            + "; ".join(f"{n} meccs: {FOUL_REASONS.get(code, code)}" for code, n in reasons.most_common())
            + ". A lista: data/known_foul_mismatches.json; részletek: docs/scoresheet-extraction-fix.md.")
    return summary


# ─────────────────────────── letöltés, kimenet ───────────────────────────

def download_pdfs(conn, pdf_dir, log, download=True):
    """{gamecode: helyi PDF} a Közgáz B jegyzőkönyves meccseire (a meglévőt nem tölti újra)."""
    os.makedirs(pdf_dir, exist_ok=True)
    out = {}
    for m in kozgaz_matches(conn):
        if not m["has_scoresheet"] or str(m["scoresheet_match_id"] or "").startswith("WEB-"):
            continue
        path = os.path.join(pdf_dir, f"{m['gamecode']}.pdf")
        if not os.path.exists(path) and download:
            url = PDF_URL.format(season=m["season"], gamecode=m["gamecode"])
            for attempt in range(3):
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        data = resp.read()
                    if not data.startswith(b"%PDF"):
                        raise ValueError("a válasz nem PDF")
                    with open(path + ".part", "wb") as f:
                        f.write(data)
                    os.replace(path + ".part", path)
                    break
                except (urllib.error.URLError, ValueError, OSError) as e:
                    if attempt == 2:
                        log("warning", f"Letöltés: {m['gamecode']}", str(e))
                    else:
                        time.sleep(2 * (attempt + 1))
        if os.path.exists(path):
            out[m["gamecode"]] = path
    return out


def load_overrides(path, log):
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        overrides = data.get("overrides", [])
        if not isinstance(overrides, list):
            raise ValueError("az overrides nem lista")
        return overrides
    except (OSError, ValueError, AttributeError) as e:
        log("warning", "Felülírás", f"a {os.path.basename(path)} nem olvasható ({e}); felülírás nélkül fut")
        return []


def load_known_fouls(path, log):
    """{gamecode: okkód} a data/known_foul_mismatches.json-ból (üres, ha nincs vagy hibás)."""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            matches = json.load(f).get("matches", {})
        if not isinstance(matches, dict) or not all(isinstance(v, str) for v in matches.values()):
            raise ValueError("a matches nem {gamecode: okkód}")
        return matches
    except (OSError, ValueError, AttributeError) as e:
        log("warning", "Ismert fault-eltérések", f"a {os.path.basename(path)} nem olvasható ({e}); mind egyenként jelez")
        return {}


def _escape(text, title=False):
    """GitHub Actions annotáció: a sortörés és a % kódolva, a címben a , és : is."""
    text = str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return text.replace(",", "%2C").replace(":", "%3A") if title else text


def make_logger():
    gha = os.environ.get("GITHUB_ACTIONS") == "true"

    def log(level, title, msg):
        if gha:
            print(f"::{level} title={_escape(title, title=True)}::{_escape(msg)}")
        else:
            print(f"  [{level}] {title}: {msg}")
    return log


def write_summary(summary, path):
    ok = sum(1 for s in summary if s["after"] == s["official"])
    lines = [
        "## Box score-pótlás (Közgáz B)", "",
        f"{ok}/{len(summary)} meccsen egyezik a játékosok összege a hivatalos eredménnyel.", "",
        "| Dátum | Meccs | Ellenfél | Hivatalos | Előtte | Utána | Állapot | Pótolt sorok | Javított faultok |",
        "|---|---|---|---:|---:|---:|---|---|---|",
    ]
    for s in summary:
        added = ", ".join(f"#{j} {n} ({p})" for j, n, p in s["added"]) or "–"
        fouls = ", ".join(f"#{j} {n} ({a}→{b})" for j, n, a, b in s["fouls"]) or s.get("foul_note") or "–"
        lines.append(f"| {s['date']} | {s['gamecode']} | {s['opponent']} | {s['official']} | "
                     f"{s['before']} | {s['after']} | {s['status']} | {added} | {fouls} |")
    text = "\n".join(lines) + "\n"
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
    return text


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["key"]:
        if len(argv) != 2:
            sys.exit("Használat: box_score_repair.py key <licencszám>")
        print(license_key(argv[1]))
        return
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="a letöltött mkosz_stats.sqlite (nem módosul)")
    ap.add_argument("--out", required=True, help="a javított másolat útvonala")
    ap.add_argument("--pdf-dir", required=True, help="a jegyzőkönyvek mappája (letöltés ide)")
    ap.add_argument("--overrides", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                        "data", "box_score_overrides.json"))
    ap.add_argument("--known-fouls", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                          "data", "known_foul_mismatches.json"))
    ap.add_argument("--no-download", action="store_true", help="csak a mappában lévő PDF-ek")
    args = ap.parse_args(argv)

    if os.path.abspath(args.db) == os.path.abspath(args.out):
        sys.exit("A --out nem lehet ugyanaz, mint a --db: a forrás nem módosulhat.")
    shutil.copyfile(args.db, args.out)
    log = make_logger()
    conn = sqlite3.connect(args.out)
    pdfs = download_pdfs(conn, args.pdf_dir, log, download=not args.no_download)
    summary = repair(conn, pdfs, load_overrides(args.overrides, log), log,
                     known_fouls=load_known_fouls(args.known_fouls, log))
    conn.commit()
    conn.close()
    print(write_summary(summary, os.environ.get("GITHUB_STEP_SUMMARY")))


if __name__ == "__main__":
    main()
