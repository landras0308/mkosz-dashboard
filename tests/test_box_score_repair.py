"""A box_score_repair.py és az export pótlás-jelölésének tesztjei.

  python3 -m unittest discover -s tests -v

A PDF-es tesztek a nyilvános MKOSZ-jegyzőkönyveket töltik le a tests/.pdf-cache
mappába (nincs a repóban). Hálózat nélkül kimaradnak; REQUIRE_PDFS=1 mellett
(a workflow így futtatja) a letöltés hibája a teszt hibája.
"""

import collections
import os
import sqlite3
import sys
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import box_score_repair as r  # noqa: E402
import export_stats  # noqa: E402

ex = r.ex
CACHE = os.path.join(ROOT, "tests", ".pdf-cache")
PDFS = {
    "hun3k_141597": "x2627",   # FKE–Közgáz B: a Közgáz első sora (#5) kimarad
    "hun3k_141609": "x2627",   # új elrendezés, 12 sor: a 12. sor kimarad
    "hun3k_125513": "x2526",   # hibátlan, TYPE1, 12 soros csapattal
    "hun3k_141589": "x2627",   # hibátlan, régi TYPE2 elrendezés
    "hun3_plya_133561": "x2526",  # hibátlan, kétsoros nevekkel
}


def pdf(gamecode):
    path = os.path.join(CACHE, f"{gamecode}.pdf")
    if not os.path.exists(path):
        os.makedirs(CACHE, exist_ok=True)
        url = r.PDF_URL.format(season=PDFS[gamecode], gamecode=gamecode)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": r.USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            with open(path, "wb") as f:
                f.write(data)
        except OSError as e:
            if os.environ.get("REQUIRE_PDFS") == "1":
                raise
            raise unittest.SkipTest(f"a jegyzőkönyv nem tölthető le ({e})")
    return path


def load(gamecode):
    return ex.extract_all_from_pdf(pdf(gamecode))


def dani_players(chars, circles, team):
    """Dani eredeti, fix ablakos kiolvasása."""
    off = ex.detect_template(chars)["off_body"]
    reg = ex.TEAM_A_PLAYERS if team == "A" else ex.TEAM_B_PLAYERS
    coach = ex.TEAM_A_COACH if team == "A" else ex.TEAM_B_COACH
    cfg = ex._offset_player_region(reg, off)
    players = [p for p in ex.extract_players(chars, circles, team, cfg, ex._offset_coach_region(coach, off))
               if p["role"] in ("player", "captain")]
    fouls = ex.extract_personal_fouls(chars, circles, team, cfg, r.FOUL_SLOTS[team], players, None)
    return players, fouls


# Az összevetésben a licencszám helyett a kivonata áll, hogy hiba esetén se kerüljön
# a licencszám a (nyilvános) Actions-naplóba.
def row_fields(players):
    return sorted((r.license_key(p["license_number"]), p["jersey_number"], p["role"], p["starter"],
                   p["entry_quarter"]) for p in players)


def names(players):
    return {r.license_key(p["license_number"]): p["name"] for p in players}


def foul_counts(fouls):
    return collections.Counter(f["jersey_number"] for f in fouls)


class AnchoredRowsTest(unittest.TestCase):
    def test_first_row_of_fke_match_is_found(self):
        chars, circles = load("hun3k_141597")
        dani, _ = dani_players(chars, circles, "B")
        self.assertNotIn(5, [p["jersey_number"] for p in dani])  # a hiba, amit javítunk
        rows = [p for _, p in r.extract_rows(chars, circles, "B")]
        self.assertEqual([p["jersey_number"] for p in rows], [5, 7, 11, 14, 18, 19, 20, 22, 38])
        first = rows[0]
        self.assertEqual((first["name"], first["role"], first["starter"], first["entry_quarter"]),
                         ("LÁTOS ANDRÁS", "player", 1, 1))
        self.assertEqual(sum(p["starter"] for p in rows), 5)

    def test_twelfth_row_is_found(self):
        chars, circles = load("hun3k_141609")
        dani, _ = dani_players(chars, circles, "A")
        self.assertEqual(len(dani), 11)  # a hiba: a 12. sor kimarad
        rows = [p for _, p in r.extract_rows(chars, circles, "A")]
        self.assertEqual(len(rows), 12)
        self.assertTrue(set(names(dani)) < set(names(rows)))

    def test_fouls_are_not_counted_twice(self):
        # Dani fix ablaka az új elrendezésben a következő sor faultjait is a
        # játékoshoz számolja (#16-nak 2 fault, a PDF-ben 0; a 2 a #17-é).
        chars, circles = load("hun3k_141597")
        _, dani_fouls = dani_players(chars, circles, "A")
        self.assertEqual(foul_counts(dani_fouls)[16], 2)
        rows = r.extract_rows(chars, circles, "A")
        mine = foul_counts(r.extract_fouls(chars, circles, "A", rows))
        self.assertEqual(mine, {4: 1, 6: 1, 8: 1, 15: 1, 17: 2, 21: 2, 23: 2})

    def test_clean_pdfs_read_the_same_as_dani(self):
        for gamecode in ("hun3k_125513", "hun3k_141589", "hun3_plya_133561"):
            chars, circles = load(gamecode)
            for team in ("A", "B"):
                with self.subTest(gamecode=gamecode, team=team):
                    dani, dani_fouls = dani_players(chars, circles, team)
                    rows = r.extract_rows(chars, circles, team)
                    mine = [p for _, p in rows]
                    self.assertEqual(row_fields(dani), row_fields(mine))
                    self.assertEqual(foul_counts(dani_fouls), foul_counts(r.extract_fouls(chars, circles, team, rows)))
                    # A név ugyanaz, vagy csak a tördelt második sorral bővül (Dani azt elhagyja).
                    for lic, name in names(dani).items():
                        self.assertTrue(names(mine)[lic] == name or names(mine)[lic].startswith(name + " "),
                                        (name, names(mine)[lic]))

    def test_wrapped_names_keep_both_lines(self):
        # Ebben a PDF-ben két név két sorba tördelve áll; Dani az egyiknél a második
        # sort elhagyja, a javított sor mindkettőt megtartja.
        chars, circles = load("hun3_plya_133561")
        longer, wrapped = 0, 0
        for team in ("A", "B"):
            dani = names(dani_players(chars, circles, team)[0])
            mine = names([p for _, p in r.extract_rows(chars, circles, team)])
            longer += sum(len(mine[lic].split()) > len(name.split()) for lic, name in dani.items())
            wrapped += sum(len(name.split()) >= 3 for name in mine.values())
        self.assertEqual(longer, 1)
        self.assertGreaterEqual(wrapped, 2)

    def test_box_score_of_fke_match(self):
        box = r.extract_box_score(pdf("hun3k_141597"))
        self.assertEqual((box["match_id"], box["score_a"], box["score_b"]), ("F2KE-0021", 92, 75))
        for team, total in (("A", 92), ("B", 75)):
            players = [p for p in box["players"] if p["team"] == team]
            self.assertEqual(sum(p["points"] for p in players), total)
            self.assertEqual(box["event_points"][team], total)
        p5 = next(p for p in box["players"] if p["team"] == "B" and p["jersey"] == 5)
        self.assertEqual({k: p5[k] for k in ("points", "fg2_made", "fg3_made", "ft_made", "ft_att", "pf", "starter")},
                         {"points": 13, "fg2_made": 6, "fg3_made": 0, "ft_made": 1, "ft_att": 4, "pf": 0, "starter": 1})


# ─────────────────────────── pótlás, kis adatbázison ───────────────────────────

KG = "KÖZGÁZ SC ÉS DSK/B"
LIC = "900005"


def make_db():
    """A mkosz_stats.sqlite érintett táblái, egy meccsel: a Közgáz (B) #5-ös sora hiányzik."""
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE matches (gamecode TEXT PRIMARY KEY, comp_code TEXT, season TEXT, match_date TEXT,
            team_a_name TEXT, team_b_name TEXT, score_a INTEGER, score_b INTEGER,
            has_scoresheet INTEGER, scoresheet_match_id TEXT);
        CREATE TABLE player_game_stats (gamecode TEXT, playercode TEXT, team TEXT, player_name TEXT,
            license_number TEXT, jersey_number INTEGER, is_starter INTEGER, entry_quarter INTEGER,
            points INTEGER, fg2_made INTEGER, fg3_made INTEGER, ft_made INTEGER, ft_attempted INTEGER,
            personal_fouls INTEGER, source TEXT, PRIMARY KEY (gamecode, team, player_name));
        CREATE TABLE scoring_events (id INTEGER PRIMARY KEY, gamecode TEXT, event_seq INTEGER, team TEXT,
            license_number TEXT, jersey_number INTEGER, points INTEGER, shot_type TEXT, made INTEGER);
    """)
    conn.execute("INSERT INTO matches VALUES ('g1','hun3k','x2627','2026-10-31','FKE',?,20,21,1,'F2KE-0021')", (KG,))
    # A forrásban meglévő sorok (B: 8 pont), és egy korábbi meccs, ahol a #5 szerepel.
    conn.execute("INSERT INTO matches VALUES ('g0','hun3k','x2627','2026-10-01',?,'X',4,5,0,NULL)", (KG,))
    conn.execute("INSERT INTO player_game_stats VALUES ('g0',NULL,'A','LÁTOS ANDRÁS',?,5,0,1,4,0,0,4,4,0,'scoresheet')", (LIC,))
    conn.execute("INSERT INTO player_game_stats VALUES ('g0',NULL,'A','HARMADIK JÁTÉKOS','900099',99,0,1,0,0,0,0,0,0,'scoresheet')")
    conn.execute("INSERT INTO player_game_stats VALUES ('g1',NULL,'B','MÁSIK JÁTÉKOS','900007',7,1,1,8,4,0,0,0,1,'scoresheet')")
    conn.execute("INSERT INTO player_game_stats VALUES ('g1',NULL,'A','ELLENFÉL','900100',4,1,1,20,10,0,0,0,0,'scoresheet')")
    seq = iter(range(1, 100))
    for _ in range(4):
        conn.execute("INSERT INTO scoring_events (gamecode,event_seq,team,license_number,jersey_number,points,shot_type,made)"
                     " VALUES ('g1',?, 'B','900007',7,2,'2FG',1)", (next(seq),))
    # A #5 13 pontja licenc nélkül: 6 kétpontos, 1/4 büntető.
    for _ in range(6):
        conn.execute("INSERT INTO scoring_events (gamecode,event_seq,team,license_number,jersey_number,points,shot_type,made)"
                     " VALUES ('g1',?,'B',NULL,5,2,'2FG',1)", (next(seq),))
    conn.execute("INSERT INTO scoring_events (gamecode,event_seq,team,license_number,jersey_number,points,shot_type,made)"
                 " VALUES ('g1',?,'B',NULL,5,1,'FT',1)", (next(seq),))
    for _ in range(3):
        conn.execute("INSERT INTO scoring_events (gamecode,event_seq,team,license_number,jersey_number,points,shot_type,made)"
                     " VALUES ('g1',?,'B',NULL,5,0,'FT',0)", (next(seq),))
    for _ in range(10):
        conn.execute("INSERT INTO scoring_events (gamecode,event_seq,team,license_number,jersey_number,points,shot_type,made)"
                     " VALUES ('g1',?,'A','900100',4,2,'2FG',1)", (next(seq),))
    for _ in range(4):
        conn.execute("INSERT INTO scoring_events (gamecode,event_seq,team,license_number,jersey_number,points,shot_type,made)"
                     " VALUES ('g0',?,'A',?,5,1,'FT',1)", (next(seq), LIC))
    return conn


def fake_box(**changes):
    """A javított kiolvasó eredménye a 'g1' meccsre (PDF nélkül)."""
    p5 = {"team": "B", "jersey": 5, "license": LIC, "name": "LÁTOS ANDRÁS", "points": 13, "fg2_made": 6,
          "fg3_made": 0, "ft_made": 1, "ft_att": 4, "pf": 0, "starter": 1, "entry_quarter": 1}
    p7 = {"team": "B", "jersey": 7, "license": "900007", "name": "MÁSIK JÁTÉKOS", "points": 8, "fg2_made": 4,
          "fg3_made": 0, "ft_made": 0, "ft_att": 0, "pf": 1, "starter": 1, "entry_quarter": 1}
    p5.update(changes.pop("p5", {}))
    p7.update(changes.pop("p7", {}))
    box = {"match_id": "F2KE-0021", "template": "TYPE2", "score_a": 20, "score_b": 21,
           "players": [p5, p7], "event_points": {"A": 20, "B": 21}}
    box.update(changes)
    return box


class RepairTest(unittest.TestCase):
    def run_repair(self, conn, box=None, overrides=(), with_pdf=True):
        logs = []
        summary = r.repair(conn, {"g1": "g1.pdf"} if with_pdf else {}, list(overrides),
                           lambda level, title, msg: logs.append((level, title, msg)),
                           extract=lambda path: box)
        return {s["gamecode"]: s for s in summary}, logs

    def b_rows(self, conn):
        return conn.execute("SELECT player_name, license_number, jersey_number, points, fg2_made, ft_made, "
                            "ft_attempted, personal_fouls, is_starter, source FROM player_game_stats "
                            "WHERE gamecode='g1' AND team='B' ORDER BY jersey_number").fetchall()

    def test_missing_row_is_added(self):
        conn = make_db()
        summary, logs = self.run_repair(conn, fake_box())
        self.assertEqual(self.b_rows(conn)[0], ("LÁTOS ANDRÁS", LIC, 5, 13, 6, 1, 4, 0, 1, "scoresheet"))
        self.assertEqual((summary["g1"]["before"], summary["g1"]["after"], summary["g1"]["status"]), (8, 21, "pótolva"))
        self.assertEqual(conn.execute("SELECT gamecode, team, license_number, points, origin FROM repaired_rows").fetchall(),
                         [("g1", "B", LIC, 13, "pdf")])
        # A #5 kosarai a pótolt játékoshoz kerülnek (negyedes bontás, eredmény alakulása).
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM scoring_events WHERE gamecode='g1' AND jersey_number=5 "
                                      "AND license_number=?", (LIC,)).fetchone()[0], 10)
        self.assertFalse([entry for entry in logs if entry[0] == "warning"])

    def test_existing_row_is_left_alone(self):
        conn = make_db()
        self.run_repair(conn, fake_box())
        before = self.b_rows(conn)
        summary, _ = self.run_repair(conn, fake_box())
        self.assertEqual(self.b_rows(conn), before)
        self.assertEqual(summary["g1"]["status"], "ok")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM repaired_rows").fetchone()[0], 1)

    def test_no_repair_when_official_score_differs(self):
        conn = make_db()
        conn.execute("UPDATE matches SET score_b = 23 WHERE gamecode = 'g1'")
        summary, logs = self.run_repair(conn, fake_box(score_b=23))
        self.assertEqual(len(self.b_rows(conn)), 1)
        self.assertEqual(summary["g1"]["status"], "nem pótolva")
        self.assertTrue(any(level == "warning" and "Nem pótolva" in title for level, title, _ in logs))
        self.assertTrue(any(level == "warning" and "Eltérés maradt" in title for level, title, _ in logs))

    def test_no_repair_when_events_total_differs(self):
        conn = make_db()
        # Egy másik, licenc nélküli kosár a B oldalon: a kosarak összege 23, a hivatalos 21.
        conn.execute("INSERT INTO scoring_events (gamecode,event_seq,team,license_number,jersey_number,points,shot_type,made)"
                     " VALUES ('g1',99,'B',NULL,9,2,'2FG',1)")
        summary, logs = self.run_repair(conn, fake_box())
        self.assertEqual(len(self.b_rows(conn)), 1)
        self.assertEqual(summary["g1"]["status"], "nem pótolva")

    def test_no_repair_when_existing_rows_already_have_the_points(self):
        # Egy csapattárs sora a forrásban már tartalmazza a #5 pontjainak egy részét (pl.
        # a mezszám-egyeztetés oda írta át): a PDF újraolvasása teljes, de a pótlás után
        # 23 pont lenne a hivatalos 21 helyett.
        conn = make_db()
        conn.execute("UPDATE player_game_stats SET points = 10 WHERE gamecode='g1' AND team='B'")
        summary, logs = self.run_repair(conn, fake_box())
        self.assertEqual(len(self.b_rows(conn)), 1)
        self.assertTrue(any("23 pont lenne" in msg for _, _, msg in logs), logs)

    def test_no_repair_when_pdf_reread_is_incomplete(self):
        conn = make_db()
        box = fake_box()
        box["players"] = box["players"][1:]
        summary, logs = self.run_repair(conn, box)
        self.assertEqual(len(self.b_rows(conn)), 1)
        self.assertTrue(any("sem teljes" in msg for _, _, msg in logs))

    def test_existing_row_with_other_name_spelling(self):
        # A forrásban licenc és mezszám nélkül megvan a sor; a PDF-ből olvasott név
        # csonka. A név a többi meccsről jön, így a meglévő sort megtalálja.
        conn = make_db()
        conn.execute("INSERT INTO player_game_stats VALUES ('g1',NULL,'B','LÁTOS ANDRÁS',NULL,NULL,0,1,13,6,0,1,4,0,'pbp')")
        summary, logs = self.run_repair(conn, fake_box(p5={"name": "LÁTOS A"}))
        self.assertEqual(len(self.b_rows(conn)), 2)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM repaired_rows").fetchone()[0], 0)
        self.assertFalse([entry for entry in logs if entry[0] == "warning"])

    def test_failed_insert_is_rolled_back(self):
        conn = make_db()
        conn.execute(r.REPAIRED_SCHEMA)
        conn.execute("CREATE TRIGGER fail BEFORE INSERT ON repaired_rows BEGIN SELECT RAISE(ABORT, 'teszt'); END")
        summary, logs = self.run_repair(conn, fake_box())
        self.assertEqual(len(self.b_rows(conn)), 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM scoring_events WHERE gamecode='g1' AND license_number=?",
                                      (LIC,)).fetchone()[0], 0)
        self.assertTrue(any("nem írható be" in msg for _, _, msg in logs))
        self.assertEqual(summary["g1"]["status"], "nem pótolva")

    def test_no_repair_when_pdf_and_events_disagree(self):
        conn = make_db()
        summary, logs = self.run_repair(conn, fake_box(p5={"points": 11, "fg2_made": 5}, p7={"points": 10}))
        self.assertEqual(len(self.b_rows(conn)), 1)
        self.assertTrue(any("a kosarak eltérnek" in msg for _, _, msg in logs))

    def test_no_repair_from_another_matchs_pdf(self):
        conn = make_db()
        summary, logs = self.run_repair(conn, fake_box(match_id="F2KE-0099"))
        self.assertEqual(len(self.b_rows(conn)), 1)
        self.assertTrue(any("azonosítója" in msg for _, _, msg in logs))

    def test_no_repair_when_jersey_belongs_to_another_player(self):
        conn = make_db()
        conn.execute("UPDATE player_game_stats SET jersey_number = 5 WHERE gamecode='g1' AND team='B'")
        summary, logs = self.run_repair(conn, fake_box())
        self.assertEqual(len(self.b_rows(conn)), 1)
        self.assertTrue(any("másik játékosé" in msg for _, _, msg in logs))

    def override(self, **changes):
        ov = {"gamecode": "g1", "side": "away", "jersey": 5, "license_key": r.license_key(LIC), "starter": True}
        ov.update(changes)
        return ov

    def test_override_adds_row_without_pdf(self):
        conn = make_db()
        summary, logs = self.run_repair(conn, overrides=[self.override()], with_pdf=False)
        self.assertEqual(self.b_rows(conn)[0], ("LÁTOS ANDRÁS", LIC, 5, 13, 6, 1, 4, 0, 1, "scoresheet"))
        self.assertEqual(conn.execute("SELECT origin FROM repaired_rows").fetchall(), [("override",)])
        self.assertEqual(summary["g1"]["after"], 21)

    def test_override_is_inert_when_source_is_right(self):
        conn = make_db()
        summary, logs = self.run_repair(conn, fake_box(), overrides=[self.override()])
        self.assertEqual(conn.execute("SELECT origin FROM repaired_rows").fetchall(), [("pdf",)])
        self.assertTrue(any(level == "notice" and "hatástalan" in msg for level, _, msg in logs))
        self.assertEqual(len(self.b_rows(conn)), 2)

    def test_override_guard(self):
        conn = make_db()
        conn.execute("UPDATE matches SET score_b = 23 WHERE gamecode = 'g1'")
        _, logs = self.run_repair(conn, overrides=[self.override()], with_pdf=False)
        self.assertEqual(len(self.b_rows(conn)), 1)
        self.assertTrue(any(title.startswith("Felülírás") and "nem pótolva" in msg for _, title, msg in logs))

    def test_override_guard_checks_events_total(self):
        conn = make_db()
        conn.execute("INSERT INTO scoring_events (gamecode,event_seq,team,license_number,jersey_number,points,shot_type,made)"
                     " VALUES ('g1',99,'B',NULL,9,2,'2FG',1)")
        _, logs = self.run_repair(conn, overrides=[self.override()], with_pdf=False)
        self.assertEqual(len(self.b_rows(conn)), 1)
        self.assertTrue(any("a kosarak összege 23" in msg for _, _, msg in logs), logs)

    def test_override_on_complete_match_is_inert(self):
        # Teljes box score-hoz nem ad hozzá pont nélküli „játékost”.
        conn = make_db()
        self.run_repair(conn, fake_box())
        ov = self.override(jersey=99, pf=4, license_key=r.license_key("900099"))
        summary, logs = self.run_repair(conn, fake_box(), overrides=[ov])
        self.assertEqual(len(self.b_rows(conn)), 2)
        self.assertTrue(any(level == "notice" and "teljes" in msg for level, _, msg in logs))

    def test_override_for_existing_row_is_inert_even_with_a_gap(self):
        # A sor már megvan, de a meccsen más ok miatt hiányzik pont: a felülírás akkor is
        # hatástalan (nem próbálja újra beírni).
        conn = make_db()
        conn.execute("INSERT INTO player_game_stats VALUES ('g1',NULL,'B','LÁTOS ANDRÁS',?,5,1,1,13,6,0,1,4,0,'scoresheet')", (LIC,))
        conn.execute("UPDATE player_game_stats SET points = 6 WHERE gamecode='g1' AND jersey_number=7")
        _, logs = self.run_repair(conn, overrides=[self.override()], with_pdf=False)
        self.assertTrue(any(level == "notice" and "már megvan" in msg for level, _, msg in logs), logs)
        self.assertFalse(any("nem írható be" in msg for _, _, msg in logs))

    def test_bad_override_entries_are_skipped(self):
        conn = make_db()
        summary, logs = self.run_repair(conn, overrides=["nem dict", self.override(pf="?"), self.override()],
                                        with_pdf=False)
        self.assertEqual(len(self.b_rows(conn)), 2)  # a hibásak kimaradnak, a jó bekerül
        self.assertTrue(any("hibás bejegyzés" in msg for _, _, msg in logs))
        self.assertTrue(any("egész szám" in msg for _, _, msg in logs))

    def test_override_with_unknown_key_or_wrong_side(self):
        for ov, text in ((self.override(license_key="lk_0000000000000000"), "egyetlen"),
                         (self.override(side="home"), "nem a Közgáz oldala")):
            conn = make_db()
            _, logs = self.run_repair(conn, overrides=[ov], with_pdf=False)
            self.assertEqual(len(self.b_rows(conn)), 1)
            self.assertTrue(any(text in msg for _, _, msg in logs), logs)

    def test_annotation_escaping(self):
        self.assertEqual(r._escape("a, b: 50%\nc", title=True), "a%2C b%3A 50%25%0Ac")
        self.assertEqual(r._escape("a, b: c"), "a, b: c")

    def test_license_key_is_not_the_license(self):
        key = r.license_key(LIC)
        self.assertNotIn(LIC, key)
        self.assertEqual(key, r.license_key(LIC))
        self.assertNotEqual(key, r.license_key("900007"))


class ExportCheckTest(unittest.TestCase):
    def test_box_score_check_counts_from_before_the_repair(self):
        players = [
            {"points": 50, "repaired": False, "reconstructed": False},
            {"points": 13, "repaired": True, "reconstructed": False},
            {"points": 4, "repaired": False, "reconstructed": True},
        ]
        self.assertEqual(export_stats.box_score_check(players, 70, 1), {
            "official_points": 70, "box_points": 50, "difference": 20,
            "repaired_points": 13, "remaining_difference": 7, "unassigned_fouls": 1,
        })

    def test_load_repaired(self):
        conn = make_db()
        self.assertEqual(export_stats.load_repaired(conn), set())
        r.repair(conn, {"g1": "g1.pdf"}, [], lambda *a: None, extract=lambda path: fake_box())
        conn.execute("INSERT INTO repaired_rows VALUES ('g1','B',NULL,9,'NÉV NÉLKÜL',0,'pdf')")
        self.assertEqual(export_stats.load_repaired(conn), {("g1", "B", LIC)})


if __name__ == "__main__":
    unittest.main()
