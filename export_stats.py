#!/usr/bin/env python3
"""A Közgáz B statisztikái JSON-ban a Gametime appnak (Andris forkja).

Kimenet (az --out mappába, a GitHub Pages ezt teszi közzé):
  data/kozgaz-b/seasons.json              — az elérhető szezonok
  data/kozgaz-b/{szezon}/stats.json       — meccsek, játékosok, csapat
  data/kozgaz-b/{szezon}/standings.json   — tabella (MKOSZ)
  data/kozgaz-b/stats.json, standings.json — a mostani szezon ugyanígy

Minden szám a generate_dashboards.py lekérdezéseiből és compute_*/_compute_*
függvényeiből jön, ugyanazokból, amikből a kozgazkosar.hu oldalai készülnek; itt
csak JSON-ba rendezzük őket. Forrás: a mkosz-stats nyilvános adatbázisa (Dani napi
importja után), a tabella a mkosz.hu-ról. A PDF-feldolgozás itt nem fut.

A mezők leírása: docs/STATS_JSON.md (a schemas/*.schema.json-ból generálva).

Használat:
  python3 export_stats.py --db mkosz_stats.sqlite --out public \
      [--previous-base https://…/data/kozgaz-b] [--db-updated-at 2026-11-15T14:28:58Z]
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

import generate_dashboards as gd

TEAM_KEY = "kozgaz-b"
VERSION = 1

# Kupák: a meccslistában és a meccsoldalakon benne vannak, a szezonösszesítőkben
# (játékos, csapat) nem — ahogy a kozgazkosar.hu-n sem.
CUP_COMPS = {"huna_cup"}
COMP_LABELS = {
    "hun3k": "NB2 Kelet",
    "hun3kob": "NB2 Közép B",
    "hun3_plya": "NB2 alsóházi rájátszás",
    "huna_cup": "Hepp Kupa",
}
VIEW_MODES = {"all": None, "home": "H", "away": "V"}
SCENARIO_LABELS = {
    "HT_LEAD": "Félidőben vezet",
    "HT_TRAIL": "Félidőben hátrányban",
    "3Q_LEAD": "3 negyed után vezet",
    "3Q_TRAIL": "3 negyed után hátrányban",
}
STANDINGS_SOURCE = "MKOSZ"


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def season_label(season):
    """'x2627' → '2026/27'."""
    m = re.fullmatch(r"x(\d\d)(\d\d)", season)
    return f"20{m.group(1)}/{m.group(2)}" if m else season


def comp_phase(comp):
    if comp in CUP_COMPS:
        return "cup"
    return "playoff" if "_ply" in comp else "regular"


def comp_label(comp):
    return COMP_LABELS.get(comp, gd.TEAMS[TEAM_KEY]["group_name"] if comp == gd.TEAMS[TEAM_KEY]["comp_code"] else comp)


def pattern_regex(sql_like):
    """'%KÖZGÁZ%DSK/B%' → kis-nagybetűtől független regex."""
    return re.compile(".*".join(re.escape(part) for part in sql_like.split("%")), re.IGNORECASE)


def player_key(license_number, name):
    """A játékoskulcs: a licencszám, ha van, különben a névből képzett slug."""
    if license_number:
        return str(license_number), "license"
    return gd.slugify(name or ""), "name_slug"


def discover_seasons(conn):
    """Melyik szezonban mely bajnokságokban van a Közgáz B-nek lejátszott meccse."""
    pat = gd.TEAMS[TEAM_KEY]["team_pattern"]
    rows = conn.execute("""
        SELECT season, comp_code, COUNT(*), MIN(match_date), MAX(match_date)
        FROM matches
        WHERE (team_a_name LIKE ? OR team_b_name LIKE ?) AND score_a + score_b > 0
        GROUP BY season, comp_code
    """, (pat, pat)).fetchall()
    seasons = {}
    for season, comp, n, first, last in rows:
        s = seasons.setdefault(season, {"comps": {}, "first": first, "last": last})
        s["comps"][comp] = n
        s["first"] = min(s["first"], first)
        s["last"] = max(s["last"], last)
    return seasons


def season_configs(season, comps):
    """A szezon bajnoki és kupa cfg-je (a TEAMS dict mintájára)."""
    base = gd.TEAMS[TEAM_KEY]
    league = [c for c in comps if c not in CUP_COMPS]
    # Alapszakasz elöl, rájátszás utána; a bajnoki összesítők ezekből készülnek.
    league.sort(key=lambda c: (comp_phase(c) != "regular", -comps[c], c))
    cfg = dict(base)
    cfg["comp_code"] = league[0] if league else base["comp_code"]
    cfg["mkosz_extra_comps"] = league[1:]
    cfg["mkosz_season"] = season
    cfg["mkosz_comp"] = cfg["comp_code"]
    cup_cfgs = {}
    for c in comps:
        if c in CUP_COMPS:
            cc = dict(base)
            cc["comp_code"] = c
            cc["mkosz_extra_comps"] = []
            cup_cfgs[c] = cc
    return cfg, league, cup_cfgs


# ─────────────────────────────── meccsek ───────────────────────────────

def match_json(conn, season, comp, gamecode, cfg, tp, scoresheet_id):
    details = gd.get_match_details(conn, cfg, tp, gamecode)
    if not details:
        return None
    v = gd.compute_match_view(details, cfg)
    kg_side = details["kg_side"]
    home = details["kg_is_home"]

    def side(team_ab):
        return "home" if team_ab == "A" else "away"

    kg_players = []
    jersey_key = {}
    for p in v["kg_players"]:
        key, key_type = player_key(p.get("license_number"), p["name"])
        if p["jersey"] != "":
            jersey_key[p["jersey"]] = key
        kg_players.append({
            "key": key, "key_type": key_type,
            "jersey": p["jersey"] if p["jersey"] != "" else None,
            "name": p["name"],
            "starter": bool(p["starter"]),
            "points": p["points"], "fg2_made": p["fg2_made"], "fg3_made": p["fg3_made"],
            "ft_made": p["ft_made"], "ft_att": p["ft_att"], "pf": p["pf"],
            "tech": p.get("tech", 0), "unsport": p.get("unsport", 0),
            "reconstructed": bool(p.get("_reconstructed")),
        })

    opp = v["opp_total"]
    events = []
    for ev, (minute, estimated) in zip(v["progression"], v["minutes"]):
        events.append({
            "seq": ev["seq"], "quarter": ev["quarter"],
            "minute": minute, "minute_estimated": estimated,
            "team": side(ev["team"]), "is_kozgaz": ev["team"] == kg_side,
            "player": ev["player"], "points": ev["points"], "shot": ev["shot"],
            "home_score": ev["score_a"], "away_score": ev["score_b"],
        })

    def dist(d):
        if not d:
            return None
        return {"points_2": d["p2"], "points_3": d["p3"], "points_ft": d["pft"], "total": d["total"],
                "pct_2": d["pct2"], "pct_3": d["pct3"], "pct_ft": d["pctft"]}

    sb = v["starter_bench"]
    return {
        "gamecode": gamecode,
        "mkosz_match_id": gamecode,
        "scoresheet_match_id": scoresheet_id,
        "competition": comp,
        "competition_label": comp_label(comp),
        "phase": comp_phase(comp),
        "is_cup": comp in CUP_COMPS,
        "date": details["match_date"],
        "time": details["match_time"] or None,
        "venue": details["venue"] or None,
        "home_team": details["team_a_name"],
        "away_team": details["team_b_name"],
        "home_team_short": v["home_label"],
        "away_team_short": v["away_label"],
        "is_home": home,
        "opponent": details["opp_team_name"],
        "opponent_short": gd.shorten_opponent(details["opp_team_name"]),
        "home_score": details["score_a"],
        "away_score": details["score_b"],
        "kozgaz_score": details["kg_score"],
        "opponent_score": details["opp_score"],
        "won": bool(details["kg_won"]),
        "mkosz_url": f"https://mkosz.hu/merkozes/{season}/{comp}/{gamecode}",
        "quarters": [{"quarter": q, "home": sa, "away": sb_} for q, sa, sb_ in v["q_rows"]],
        "quarters_source": "events" if v["progression"] else "quarter_scores",
        "kozgaz_totals": dict(v["totals"]),
        "box_score_check": {
            "official_points": v["kg_official"],
            "box_points": v["totals"]["points"],
            "difference": v["box_diff"],
            "unassigned_fouls": v["orphan_fouls"],
        },
        "opponent_totals": {
            "points": opp["points"], "fg2_made": opp["fg2_made"], "fg3_made": opp["fg3_made"],
            "ft_made": opp["ft_made"], "ft_att": opp["ft_att"], "ft_pct": v["opp_ft_pct"],
            "top_scorer": ({"name": opp["top_scorer"]["name"], "points": opp["top_scorer"]["points"]}
                           if opp["top_scorer"] else None),
        },
        "players": kg_players,
        "progression": {
            "events": events,
            "quarter_ends": [{"quarter": m["q"], "seq": m["x"], "home": m["home"], "away": m["away"]}
                             for m in v["q_markers"]],
        },
        "facts": {
            "comparisons": [{"label": label, "home": hv, "away": av, "format": fmt, "note": note}
                            for label, hv, av, fmt, note in v["vs_items"]],
            "starter_bench": ({
                "home_starter": sb["home_starter"], "home_bench": sb["home_bench"],
                "away_starter": sb["away_starter"], "away_bench": sb["away_bench"],
                "home_unaccounted": sb["home_unaccounted"], "away_unaccounted": sb["away_unaccounted"],
            } if sb else None),
            "lead_changes": v["lead_changes"] if v["has_progression"] else None,
        },
        "quarter_mvps": [{
            "quarter": m["q"],
            "home": {"player": m["home"][0], "points": m["home"][1]},
            "away": {"player": m["away"][0], "points": m["away"][1]},
        } for m in v["quarter_mvps"]],
        "scoring_distribution": {"kozgaz": dist(v["kg_dist"]), "opponent": dist(v["opp_dist"])},
        "foul_timeline": [{
            "jersey": row["jersey"],
            "name": row["name"],
            "player_key": jersey_key.get(row["jersey"]),
            "fouled_out": row["fouled_out"],
            "fouls": [{"quarter": f["quarter"], "minute": f["minute"], "game_minute": f["t"]} for f in row["fouls"]],
        } for row in v["foul_timeline"]],
    }


def season_matches(conn, season, comps, cfg, cup_cfgs):
    tp_league = gd._team_like(conn, cfg)
    tps = {c: tp_league for c in comps if c not in CUP_COMPS}
    for c, cc in cup_cfgs.items():
        tps[c] = gd._team_like(conn, cc)
    out = []
    for comp, tp in tps.items():
        rows = conn.execute("""
            SELECT gamecode, scoresheet_match_id FROM matches
            WHERE season = ? AND comp_code = ?
              AND (team_a_name LIKE ? OR team_b_name LIKE ?)
              AND score_a + score_b > 0
        """, (season, comp, tp, tp)).fetchall()
        for gamecode, scoresheet_id in rows:
            m = match_json(conn, season, comp, gamecode, cup_cfgs.get(comp, cfg), tp, scoresheet_id)
            if m:
                out.append(m)
    out.sort(key=lambda m: (m["date"], m["time"] or "", m["gamecode"]))
    return out


# ─────────────────────────────── játékosok ───────────────────────────────

def player_view_json(player, bundle, competition_of):
    view = gd._compute_player_view(player, bundle, with_ids=True)
    strengths, weaknesses = gd.generate_insights(
        player[1], view["games"], view["ppg"], view["fg3"], view["ft_m"], view["ft_a"],
        view["pf_pg"], view["max_pts"], bundle["quarter_stats"], bundle["opp_stats"],
        bundle["game_log"], view["total_pts"], view["starts"],
    )
    games = []
    for g in view["js_games"]:
        played = g["pts"] is not None
        games.append({
            "gamecode": g["gamecode"],
            "competition": competition_of.get(g["gamecode"]),
            "date": g["iso_date"],
            "is_home": g["hv"] == "H",
            "opponent": g["opp_full"],
            "opponent_short": g["opp"],
            "result": g["res"],
            "kozgaz_score": g["kg_score"],
            "opponent_score": g["opp_score"],
            "played": played,
            "points": g["pts"] if played else None,
            "fg2_made": g["fg2"] if played else None,
            "fg3_made": g["fg3"] if played else None,
            "ft_made": g["ft_m"] if played else None,
            "ft_att": g["ft_a"] if played else None,
            "pf": g["pf"] if played else None,
            "share_pct": g["share"] if played else None,
            "starter": g["start"] if played else None,
        })
    return {
        "summary": {
            "games": view["games"], "points": view["total_pts"], "ppg": view["ppg"],
            "fg2_made": view["fg2"], "fg3_made": view["fg3"],
            "ft_made": view["ft_m"], "ft_att": view["ft_a"], "ft_pct": view["ft_pct"],
            "pf": view["pf"], "pf_per_game": view["pf_pg"], "max_points": view["max_pts"],
            "starts": view["starts"], "share_pct": view["share_pct"],
            "tech": view["tech"], "unsport": view["unsport"],
        },
        "scoring_split": {"points_2": view["pts_2fg"], "points_3": view["pts_3fg"], "points_ft": view["pts_ft"]},
        "quarters": [{"quarter": i + 1, "points": view["q_data"][i], "threes": view["q_3fg_data"][i]}
                     for i in range(4)],
        "games": games,
        "insights": {"strengths": strengths, "weaknesses": weaknesses},
    }


def season_players(conn, cfg, tp, competition_of):
    out = []
    for player in gd.get_roster(conn, cfg, tp):
        lic, name, jersey = player[0], player[1], player[2]
        has_license = lic is not None and lic != name
        key, key_type = player_key(lic if has_license else None, name)
        views = {}
        for mode, hv in VIEW_MODES.items():
            bundle = gd.get_player_bundle(conn, cfg, tp, lic, hv_filter=hv)
            views[mode] = player_view_json(player, bundle, competition_of)
        out.append({
            "key": key, "key_type": key_type, "name": name,
            "jersey": jersey, "slug": gd.slugify(name),
            "views": views,
        })
    return out


# ─────────────────────────────── csapat ───────────────────────────────

def fact_segments(text):
    """'Legerősebb negyed: <b>Q2</b> (…)' → [{text, bold}] (a honlap fact-szövegei)."""
    segs = []
    for part in re.split(r"(<b>.*?</b>)", text):
        if not part:
            continue
        bold = part.startswith("<b>")
        segs.append({"text": re.sub(r"</?b>", "", part), "bold": bold})
    return segs


def team_view_json(d, competition_of):
    js = gd._stats_to_js(d)
    sc = js["sc"]
    return {
        "record": {
            "games": js["games"], "wins": js["wins"], "losses": js["losses"],
            "scored": js["scored"], "allowed": js["allowed"],
            "ppg": js["ppg"], "opp_ppg": js["opp_ppg"], "diff_per_game": js["diff"],
            "best_score": js["best_score"], "most_allowed": js["most_allowed"],
            "players_used": js["players_used"],
            "home_wins": js["home_w"], "home_games": js["home_g"],
            "away_wins": js["away_w"], "away_games": js["away_g"],
        },
        "games": [{
            "gamecode": g[0], "competition": competition_of.get(g[0]), "date": g[1],
            "is_home": g[2] == "H", "opponent": g[3], "opponent_short": gd.shorten_opponent(g[3]),
            "kozgaz_score": g[4], "opponent_score": g[5], "result": "W" if g[4] > g[5] else "L",
        } for g in d["game_log"] if g[4] is not None and g[5] is not None],
        "quarters": [{"quarter": i + 1, "kozgaz_avg": js["q_kg"][i], "opponent_avg": js["q_op"][i],
                      "won": js["q_won"][i], "lost": js["q_lost"][i]} for i in range(len(js["q_kg"]))],
        "scenarios": [{"key": k, "label": label, "games": sc.get(k, [0, 0])[0], "wins": sc.get(k, [0, 0])[1]}
                      for k, label in SCENARIO_LABELS.items()],
        "scoring_split": {"points_2": js["pts2"], "points_3": js["pts3"], "points_ft": js["pts_ft"],
                          "pct_2": js["pct2"], "pct_3": js["pct3"], "pct_ft": js["pct_ft"],
                          "ft_made": js["ftm"], "ft_att": js["fta"]},
        "runs_for": [run_json(r) for r in d["runs_for"]],
        "runs_against": [run_json(r) for r in d["runs_against"]],
        "facts": [fact_segments(f) for f in js["facts"]],
    }


def run_json(r):
    date, opp, sq, eq, pts, baskets = r[:6]
    return {"date": date, "opponent": opp, "opponent_short": gd.shorten_opponent(opp),
            "start_quarter": sq, "end_quarter": eq, "points": pts, "baskets": baskets}


def season_team(conn, cfg, tp, competition_of):
    fn = gd.get_team_stats_pbp if gd._is_pbp(cfg) else gd.get_team_stats
    return {"views": {mode: team_view_json(fn(conn, cfg, tp, hv_filter=hv), competition_of)
                      for mode, hv in VIEW_MODES.items()}}


# ─────────────────────────────── tabella ───────────────────────────────

def fetch_previous(base, path):
    """A legutóbb közzétett fájl (a Pages-ről), vagy None."""
    if not base:
        return None
    try:
        with urllib.request.urlopen(f"{base.rstrip('/')}/{path}", timeout=15) as res:
            return json.loads(res.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return None


def standings_json(season, league_comps, is_current, previous):
    """A szezon tabellái bajnokságonként; a Közgáz B csoportja (rájátszásnál több
    csoport közül). Lezárt szezonnál a korábban közzétett változat marad, ha van;
    sikertelen lekérésnél is a korábbi marad (a régi lekérési idővel)."""
    if previous and not is_current:
        return previous
    kg = pattern_regex(gd.TEAMS[TEAM_KEY]["team_pattern"])
    prev_tables = {t["competition"]: t for t in (previous or {}).get("tables", [])}
    tables = []
    for comp in league_comps:
        found = gd.scrape_standings_tables(season, comp)
        if found is None:
            if comp in prev_tables:
                tables.append(prev_tables[comp])
            continue
        mine = [t for t in found if any(kg.match(r["name"]) for r in t)]
        rows = mine[0] if mine else (found[0] if len(found) == 1 else None)
        if not rows:
            continue
        tables.append({
            "competition": comp,
            "competition_label": comp_label(comp),
            "phase": comp_phase(comp),
            "source": STANDINGS_SOURCE,
            "source_url": f"https://mkosz.hu/bajnoksag/{season}/{comp}",
            "fetched_at": now_iso(),
            "rows": [{
                "rank": r["rank"], "team": r["name"], "team_short": gd.calendar_short_name(r["name"]),
                "is_kozgaz": bool(kg.match(r["name"])),
                "games": r["games"], "wins": r["wins"], "losses": r["losses"],
                "scored": r["scored"], "allowed": r["allowed"], "diff": r["scored"] - r["allowed"],
                "points": r["pts"], "streak": r["form"] or None,
            } for r in rows],
        })
    return {
        "version": VERSION, "team": TEAM_KEY, "season": season, "season_label": season_label(season),
        "generated_at": now_iso(), "tables": tables,
    }


# ─────────────────────────────── fő ───────────────────────────────

def write_json(out_dir, rel, data):
    path = os.path.join(out_dir, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="mkosz_stats.sqlite")
    ap.add_argument("--out", required=True, help="kimeneti mappa (a Pages gyökere)")
    ap.add_argument("--previous-base", help="a legutóbb közzétett data/kozgaz-b URL-je (tabella-tartalék)")
    ap.add_argument("--db-updated-at", help="az adatbázis utolsó frissítése (ISO 8601), ha ismert")
    args = ap.parse_args()

    gd.STATS_DB_PATH = args.db
    conn = gd.get_connection()
    base_rel = f"data/{TEAM_KEY}"
    found = discover_seasons(conn)
    if not found:
        sys.exit("Nincs Közgáz B meccs az adatbázisban.")
    current = max(found)
    season_list = []
    for season in sorted(found, reverse=True):
        info = found[season]
        gd.SEASON = season  # a generate_dashboards lekérdezései ezt a globálist olvassák
        cfg, league, cup_cfgs = season_configs(season, info["comps"])
        tp = gd._team_like(conn, cfg)
        matches = season_matches(conn, season, info["comps"], cfg, cup_cfgs)
        competition_of = {m["gamecode"]: m["competition"] for m in matches}
        stats = {
            "version": VERSION,
            "team": TEAM_KEY,
            "team_name": cfg["team_name"],
            "season": season,
            "season_label": season_label(season),
            "generated_at": now_iso(),
            "source": {
                "database": "https://github.com/pozsikdani/mkosz-stats (mkosz_stats.sqlite)",
                "database_updated_at": args.db_updated_at or None,
                "aggregate_competitions": league,
            },
            "competitions": [{"code": c, "label": comp_label(c), "phase": comp_phase(c),
                              "is_cup": c in CUP_COMPS, "matches": info["comps"][c]}
                             for c in sorted(info["comps"], key=lambda c: (comp_phase(c) == "cup", comp_phase(c), c))],
            "matches": matches,
            "players": season_players(conn, cfg, tp, competition_of) if league else [],
            "team": season_team(conn, cfg, tp, competition_of) if league else None,
        }
        previous = fetch_previous(args.previous_base, f"{season}/standings.json")
        standings = standings_json(season, league, season == current, previous)
        for rel_dir in ([f"{base_rel}/{season}"] + ([base_rel] if season == current else [])):
            write_json(args.out, f"{rel_dir}/stats.json", stats)
            write_json(args.out, f"{rel_dir}/standings.json", standings)
        season_list.append({
            "season": season, "label": season_label(season),
            "competitions": stats["competitions"],
            "match_count": len(matches),
            "first_match_date": info["first"], "last_match_date": info["last"],
            "stats": f"{season}/stats.json", "standings": f"{season}/standings.json",
        })
        print(f"  ✓ {season}: {len(matches)} meccs, {len(stats['players'])} játékos, "
              f"{len(standings['tables'])} tabella")
    write_json(args.out, f"{base_rel}/seasons.json", {
        "version": VERSION, "team": TEAM_KEY, "current_season": current,
        "generated_at": now_iso(), "seasons": season_list,
    })
    conn.close()
    print(f"  ✓ {base_rel}/seasons.json ({len(season_list)} szezon)")


if __name__ == "__main__":
    main()
