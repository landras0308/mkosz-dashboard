#!/usr/bin/env python3
"""A stats.json / standings.json / seasons.json sémája (export_stats.py kimenete).

Egy forrás: az alábbi Python-leírásból készül a schemas/*.schema.json (JSON Schema,
2020-12) és a docs/STATS_JSON.md (mező, típus, jelentés).

  python3 stats_schema.py write              — séma- és docs-fájlok újraírása
  python3 stats_schema.py check <out-mappa>  — a fájlok naprakészek-e, és a
                                               kimenet minden JSON-ja megfelel-e
                                               a sémának (a workflow ezt futtatja)

Szerződés az app felé: mezőt nem nevezünk át és nem törlünk; új mező jöhet.
Törő változásnál a `version` nő (és a fájl mellé a régi is megmarad egy ideig).
"""

import glob
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_DIR = os.path.join(BASE_DIR, "schemas")
DOCS_PATH = os.path.join(BASE_DIR, "docs", "STATS_JSON.md")


# ─────────────────────────── építőkockák ───────────────────────────

def _t(base, null):
    return [base, "null"] if null else base


def INT(d, null=False):
    return {"type": _t("integer", null), "description": d}


def NUM(d, null=False):
    return {"type": _t("number", null), "description": d}


def STR(d, null=False, **kw):
    return {"type": _t("string", null), "description": d, **kw}


def BOOL(d, null=False):
    return {"type": _t("boolean", null), "description": d}


def ENUM(d, values, null=False):
    return {"type": _t("string", null), "enum": list(values) + ([None] if null else []), "description": d}


def ARR(d, items):
    return {"type": "array", "description": d, "items": items}


def OBJ(d, props, null=False):
    return {
        "type": _t("object", null), "description": d,
        "properties": props, "required": list(props), "additionalProperties": False,
    }


DATE = {"pattern": r"^\d{4}-\d{2}-\d{2}$"}
DATETIME = {"pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"}
SEASON = {"pattern": r"^x\d{4}$"}

PHASE = ("regular", "playoff", "cup")
SIDE = ("home", "away")
RESULT = ("W", "L")


def competition():
    return OBJ("Egy bajnokság vagy kupa a szezonban.", {
        "code": STR("MKOSZ bajnokság-kód (pl. hun3k, hun3_plya, huna_cup)."),
        "label": STR("Megjelenítendő név (pl. NB2 Kelet, Hepp Kupa)."),
        "phase": ENUM("regular = alapszakasz, playoff = rájátszás, cup = kupa.", PHASE),
        "is_cup": BOOL("Kupa-e (a szezonösszesítőkbe nem számít)."),
        "matches": INT("A Közgáz B lejátszott meccsei ebben (a forrásadatbázisban)."),
    })


def dist(d):
    return OBJ(d, {
        "points_2": INT("Kétpontosokból szerzett pont."),
        "points_3": INT("Hárompontosokból szerzett pont."),
        "points_ft": INT("Büntetőből szerzett pont."),
        "total": INT("Összesen (a három összege)."),
        "pct_2": INT("Kétpontosok aránya, % (egészre kerekítve)."),
        "pct_3": INT("Hárompontosok aránya, %."),
        "pct_ft": INT("Büntetők aránya, %."),
    }, null=True)


def match():
    return OBJ("Egy lejátszott meccs, a meccsoldal minden adatával.", {
        "gamecode": STR("A meccs kulcsa (MKOSZ-azonosító, pl. hun3k_141615)."),
        "mkosz_match_id": STR("Az MKOSZ meccs-azonosítója; azonos a gamecode-dal és a schedule.json match_id-jával."),
        "scoresheet_match_id": STR("A jegyzőkönyv azonosítója (pl. F2KE-0035, kupánál FHKF-…).", null=True),
        "competition": STR("Bajnokság-kód (lásd competitions[])."),
        "competition_label": STR("Bajnokság neve."),
        "phase": ENUM("regular / playoff / cup.", PHASE),
        "is_cup": BOOL("Kupameccs-e (pl. Hepp Kupa)."),
        "date": STR("Dátum (budapesti), ÉÉÉÉ-HH-NN.", **DATE),
        "time": STR("Kezdés (budapesti), ÓÓ:PP.", null=True),
        "venue": STR("Helyszín.", null=True),
        "home_team": STR("Hazai csapat teljes neve."),
        "away_team": STR("Vendég csapat teljes neve."),
        "home_team_short": STR("Hazai csapat rövid neve (a honlap rövidítése)."),
        "away_team_short": STR("Vendég csapat rövid neve."),
        "is_home": BOOL("A Közgáz B hazai-e."),
        "opponent": STR("Az ellenfél teljes neve."),
        "opponent_short": STR("Az ellenfél rövid neve."),
        "opponent_table_short": STR("Ellenfél rövid neve, ahogy a szezon tabelláján (team_short); ha nincs a tabellán (pl. kupaellenfél), a honlap naptárának rövidítése."),
        "home_score": INT("Hazai pont.", null=True),
        "away_score": INT("Vendég pont.", null=True),
        "kozgaz_score": INT("A Közgáz B pontja.", null=True),
        "opponent_score": INT("Az ellenfél pontja.", null=True),
        "won": BOOL("A Közgáz B nyert-e."),
        "mkosz_url": STR("A meccs oldala az mkosz.hu-n."),
        "quarters": ARR("Negyedenkénti pontok, hazai–vendég (nem kumulált).", OBJ("Egy negyed.", {
            "quarter": INT("Negyed sorszáma (1–4, 5+ = hosszabbítás)."),
            "home": INT("Hazai pont a negyedben."),
            "away": INT("Vendég pont a negyedben."),
        })),
        "quarters_source": ENUM("events = a kosarak sorából számolva (a honlap is ezt használja), "
                                "quarter_scores = a jegyzőkönyv negyed-táblájából.", ("events", "quarter_scores")),
        "kozgaz_totals": OBJ("A Közgáz box score összesítő sora.", {
            "points": INT("Pont (a játékossorok összege)."),
            "fg2_made": INT("Bedobott kétpontos."),
            "fg3_made": INT("Bedobott hárompontos."),
            "ft_made": INT("Bedobott büntető."),
            "ft_att": INT("Büntető-kísérlet."),
            "pf": INT("Személyi hiba."),
            "tech": INT("Technikai hiba (T)."),
            "unsport": INT("Sportszerűtlen hiba (U)."),
        }),
        "box_score_check": OBJ("Forrás-ellenőrzés a pótlás előtti állapotból (docs/scoresheet-extraction-fix.md). "
                               "A honlap figyelmeztetése a kosarakból kiegészített sorokat is beszámítja, "
                               "ez nem.", {
            "official_points": INT("A hivatalos végeredmény Közgáz-pontja."),
            "box_points": INT("A forrás (Dani adatbázisa) játékossoraihoz rendelt pontok összege, a pótolt "
                              "(repaired) és a kosarakból kiegészített (reconstructed) sorok nélkül."),
            "difference": INT("official_points − box_points; ha nem 0, a forrás jegyzőkönyv-adata hiányos."),
            "repaired_points": INT("A fork által a PDF-jegyzőkönyvből vagy kézi felülírásból pótolt sorok pontjai."),
            "remaining_difference": INT("official_points − box_points − repaired_points: ami a pótlás után is "
                                        "hiányzik; 0, ha a forrás és a pótolt sorok együtt kiadják a hivatalos "
                                        "eredményt. A kosarakból kiegészített (reconstructed) sorok pontjai "
                                        "ebbe beleszámítanak (ellenőrizetlenek)."),
            "unassigned_fouls": INT("Játékoshoz nem rendelhető (mezszám nélküli) Közgáz-faultok."),
        }),
        "opponent_totals": OBJ("Az ellenfél összesítője.", {
            "points": INT("Pont (a hivatalos eredmény)."),
            "fg2_made": INT("Bedobott kétpontos."),
            "fg3_made": INT("Bedobott hárompontos."),
            "ft_made": INT("Bedobott büntető."),
            "ft_att": INT("Büntető-kísérlet."),
            "ft_pct": INT("Büntető-százalék (egészre kerekítve; 0, ha nem volt kísérlet)."),
            "top_scorer": OBJ("Az ellenfél legjobb dobója.", {
                "name": STR("Név (a jegyzőkönyv szerint)."),
                "points": INT("Pont."),
            }, null=True),
        }),
        "players": ARR("A Közgáz játékossorai (box score), pont szerint csökkenő sorrendben.", OBJ("Egy játékos a meccsen.", {
            "key": STR("Játékoskulcs: licencszám, vagy ha nincs, a névből képzett slug."),
            "key_type": ENUM("license = licencszám, name_slug = névből képzett slug.", ("license", "name_slug")),
            "jersey": INT("Mezszám.", null=True),
            "name": STR("Név (a jegyzőkönyv szerint)."),
            "starter": BOOL("Kezdőötös tagja volt-e."),
            "points": INT("Pont."),
            "fg2_made": INT("Bedobott kétpontos."),
            "fg3_made": INT("Bedobott hárompontos."),
            "ft_made": INT("Bedobott büntető."),
            "ft_att": INT("Büntető-kísérlet."),
            "pf": INT("Személyi hiba."),
            "tech": INT("Technikai hiba (T)."),
            "unsport": INT("Sportszerűtlen hiba (U)."),
            "reconstructed": BOOL("A sor a kosarak listájából pótolt (a jegyzőkönyv box score-jából hiányzott)."),
            "repaired": BOOL("A sort a fork pótolta a PDF-jegyzőkönyvből vagy kézi felülírásból (a forrás "
                             "adatbázisából hiányzott; docs/scoresheet-extraction-fix.md)."),
        })),
        "progression": OBJ("Az eredmény alakulása (csak a beesett kosarak; NB2-ben nincs kihagyott dobás).", {
            "events": ARR("Kosarak időrendben.", OBJ("Egy kosár.", {
                "seq": INT("Sorszám a meccsen belül (a grafikon x-tengelye a honlapon)."),
                "quarter": INT("Negyed."),
                "minute": INT("Perc a negyeden belül (0–10)."),
                "minute_estimated": BOOL("A perc becsült: a jegyzőkönyv csak az új percnél ír időt, "
                                         "ilyenkor az előző ismert percet kapja (a negyed elején 0)."),
                "team": ENUM("Melyik csapat dobta: home / away.", SIDE),
                "is_kozgaz": BOOL("A Közgáz dobta-e."),
                "player": STR("A dobó neve, ha ismert.", null=True),
                "points": INT("Pont (1, 2, 3)."),
                "shot": STR("Dobástípus (2FG, 3FG, FT, MULTI)."),
                "home_score": INT("Hazai állás a kosár után."),
                "away_score": INT("Vendég állás a kosár után."),
            })),
            "quarter_ends": ARR("Negyedvégi állások.", OBJ("Egy negyed vége.", {
                "quarter": INT("Negyed."),
                "seq": INT("A negyed utolsó kosarának sorszáma."),
                "home": INT("Hazai állás (kumulált)."),
                "away": INT("Vendég állás (kumulált)."),
            })),
        }),
        "facts": OBJ("Érdekességek (a honlap csempéi, ugyanabban a sorrendben és feltételekkel).", {
            "comparisons": ARR("Kétcsapatos összevetések, hazai–vendég.", OBJ("Egy csempe.", {
                "label": STR("Felirat (pl. Legnagyobb vezetés)."),
                "home": INT("Hazai érték."),
                "away": INT("Vendég érték."),
                "format": ENUM("Kiírás: int = szám, plus = +szám, points = számp, run = szám-0.",
                               ("int", "plus", "points", "run")),
                "note": STR("Megjegyzés a csempe alján.", null=True),
            })),
            "starter_bench": OBJ("Kezdő és cserepontok (csak ha van kezdő-adat).", {
                "home_starter": INT("Hazai kezdők pontja."),
                "home_bench": INT("Hazai cserék pontja."),
                "away_starter": INT("Vendég kezdők pontja."),
                "away_bench": INT("Vendég cserék pontja."),
                "home_unaccounted": INT("Hazai pont, ami nincs játékoshoz rendelve."),
                "away_unaccounted": INT("Vendég pont, ami nincs játékoshoz rendelve."),
            }, null=True),
            "lead_changes": INT("Vezetésváltások száma (null, ha nincs kosár-lista).", null=True),
        }),
        "quarter_mvps": ARR("Negyedenként a legtöbb pontot dobó játékos csapatonként.", OBJ("Egy negyed.", {
            "quarter": INT("Negyed (1–4)."),
            "home": OBJ("Hazai legjobb.", {"player": STR("Név (— ha nem dobott)."), "points": INT("Pont.")}),
            "away": OBJ("Vendég legjobb.", {"player": STR("Név (— ha nem dobott)."), "points": INT("Pont.")}),
        })),
        "scoring_distribution": OBJ("Pontszerzés megoszlása.", {
            "kozgaz": dist("Közgáz (null, ha nincs adat)."),
            "opponent": dist("Ellenfél (null, ha nincs adat)."),
        }),
        "foul_timeline": ARR("A Közgáz játékosok faultjai időrendben, a legtöbb faultot elkövető elöl.", OBJ("Egy játékos.", {
            "jersey": INT("Mezszám."),
            "name": STR("Név (vagy #mezszám, ha a box score-ban nincs)."),
            "player_key": STR("A játékos kulcsa a players[]-ben, ha megtalálható.", null=True),
            "fouled_out": BOOL("Kipontozódott-e (5+ fault)."),
            "fouls": ARR("Faultok.", OBJ("Egy fault.", {
                "quarter": INT("Negyed."),
                "minute": INT("Perc a negyeden belül (0–10, a honlap javításával)."),
                "game_minute": INT("Perc a meccsen (0–40): (negyed−1)·10 + perc."),
            })),
        })),
    })


def player_view():
    return OBJ("Egy nézet (összes / hazai / idegen) a bajnoki meccsekből.", {
        "summary": OBJ("Szezonösszesítő.", {
            "games": INT("Lejátszott meccs."),
            "points": INT("Összes pont."),
            "ppg": NUM("Pontátlag (1 tizedes)."),
            "fg2_made": INT("Bedobott kétpontos."),
            "fg3_made": INT("Bedobott hárompontos."),
            "ft_made": INT("Bedobott büntető."),
            "ft_att": INT("Büntető-kísérlet."),
            "ft_pct": INT("Büntető-százalék (egészre kerekítve; 0, ha nem volt kísérlet)."),
            "pf": INT("Személyi hiba."),
            "pf_per_game": NUM("Fault/meccs (1 tizedes)."),
            "max_points": INT("Csúcs (legtöbb pont egy meccsen)."),
            "starts": INT("Kezdések száma."),
            "share_pct": NUM("A csapat pontjaiból való részesedés, % (1 tizedes)."),
            "tech": INT("Technikai hiba (T)."),
            "unsport": INT("Sportszerűtlen hiba (U)."),
        }),
        "scoring_split": OBJ("Dobásmegoszlás (pontban).", {
            "points_2": INT("Kétpontosokból."),
            "points_3": INT("Hárompontosokból."),
            "points_ft": INT("Büntetőből."),
        }),
        "quarters": ARR("Negyedenkénti teljesítmény (a szezon összesen, nem átlag).", OBJ("Egy negyed.", {
            "quarter": INT("Negyed (1–4)."),
            "points": INT("Pont ebben a negyedben a szezonban."),
            "threes": INT("Bedobott hárompontos ebben a negyedben."),
        })),
        "games": ARR("Meccsenkénti sorok, időrendben; a csapat minden bajnoki meccse.", OBJ("Egy meccs.", {
            "gamecode": STR("A meccs kulcsa (matches[].gamecode)."),
            "competition": STR("Bajnokság-kód.", null=True),
            "date": STR("Dátum.", **DATE),
            "is_home": BOOL("Hazai meccs-e."),
            "opponent": STR("Ellenfél teljes neve."),
            "opponent_short": STR("Ellenfél rövid neve."),
            "opponent_table_short": STR("Ellenfél rövid neve, ahogy a szezon tabelláján (team_short); ha nincs a tabellán (pl. kupaellenfél), a honlap naptárának rövidítése."),
            "result": ENUM("A csapat eredménye: W / L.", RESULT),
            "kozgaz_score": INT("Közgáz pont."),
            "opponent_score": INT("Ellenfél pont."),
            "played": BOOL("Játszott-e a játékos (false = nem lépett pályára; ilyenkor a statok null)."),
            "points": INT("Pont.", null=True),
            "fg2_made": INT("Bedobott kétpontos.", null=True),
            "fg3_made": INT("Bedobott hárompontos.", null=True),
            "ft_made": INT("Bedobott büntető.", null=True),
            "ft_att": INT("Büntető-kísérlet.", null=True),
            "pf": INT("Személyi hiba.", null=True),
            "share_pct": NUM("A csapat pontjaiból való részesedés, %.", null=True),
            "starter": BOOL("Kezdő volt-e.", null=True),
            "repaired": BOOL("A meccs sorát a fork pótolta a PDF-jegyzőkönyvből vagy kézi felülírásból "
                             "(false, ha nem játszott)."),
        })),
        "insights": OBJ("Elemzői meglátások (a honlap szabályaival, erre a nézetre számolva).", {
            "strengths": ARR("Erősségek (legfeljebb 5).", STR("Egy mondat.")),
            "weaknesses": ARR("Fejlesztendő területek (legfeljebb 5).", STR("Egy mondat.")),
        }),
    })


def views(item, d):
    return OBJ(d, {"all": item, "home": item, "away": item})


def team_views():
    item = team_view()
    phase = dict(item, type=["object", "null"],
                 description="Mint a views.all, csak az alapszakasz / rájátszás meccseiből; null, ha a "
                             "szezonban nincs rájátszás (a honlapon ilyenkor nincs Alapszakasz / Rájátszás gomb).")
    return OBJ("Nézetek: összes, hazai, idegen; alapszakasz, rájátszás.",
               {"all": item, "home": item, "away": item, "regular": phase, "playoff": phase})


def team_view():
    run = OBJ("Egy run (válasz nélküli pontsorozat).", {
        "date": STR("Dátum.", **DATE),
        "opponent": STR("Ellenfél teljes neve."),
        "opponent_short": STR("Ellenfél rövid neve."),
        "opponent_table_short": STR("Ellenfél rövid neve, ahogy a szezon tabelláján (team_short); ha nincs a tabellán (pl. kupaellenfél), a honlap naptárának rövidítése."),
        "start_quarter": INT("Kezdő negyed."),
        "end_quarter": INT("Záró negyed."),
        "points": INT("Pont a runban."),
        "baskets": INT("Kosarak száma a runban."),
    })
    return OBJ("Egy nézet (összes / hazai / idegen) a bajnoki meccsekből.", {
        "record": OBJ("Mérleg.", {
            "games": INT("Meccs."),
            "wins": INT("Győzelem."),
            "losses": INT("Vereség."),
            "scored": INT("Dobott pont."),
            "allowed": INT("Kapott pont."),
            "ppg": NUM("Dobott/meccs."),
            "opp_ppg": NUM("Kapott/meccs."),
            "diff_per_game": NUM("Különbség/meccs."),
            "best_score": INT("Legtöbb dobott pont egy meccsen."),
            "most_allowed": INT("Legtöbb kapott pont egy meccsen."),
            "players_used": INT("Pályára lépett játékosok száma."),
            "home_wins": INT("Hazai győzelem."),
            "home_games": INT("Hazai meccs."),
            "away_wins": INT("Idegenbeli győzelem."),
            "away_games": INT("Idegenbeli meccs."),
        }),
        "games": ARR("A meccsek, időrendben.", OBJ("Egy meccs.", {
            "gamecode": STR("A meccs kulcsa."),
            "competition": STR("Bajnokság-kód.", null=True),
            "date": STR("Dátum.", **DATE),
            "is_home": BOOL("Hazai-e."),
            "opponent": STR("Ellenfél teljes neve."),
            "opponent_short": STR("Ellenfél rövid neve."),
            "opponent_table_short": STR("Ellenfél rövid neve, ahogy a szezon tabelláján (team_short); ha nincs a tabellán (pl. kupaellenfél), a honlap naptárának rövidítése."),
            "kozgaz_score": INT("Közgáz pont."),
            "opponent_score": INT("Ellenfél pont."),
            "result": ENUM("W / L.", RESULT),
        })),
        "quarters": ARR("Negyedátlagok.", OBJ("Egy negyed.", {
            "quarter": INT("Negyed (1–4)."),
            "kozgaz_avg": NUM("Közgáz pont/meccs a negyedben."),
            "opponent_avg": NUM("Ellenfél pont/meccs a negyedben."),
            "won": INT("Megnyert negyedek száma."),
            "lost": INT("Elvesztett negyedek száma."),
        })),
        "scenarios": ARR("Félidős és 3 negyed utáni forgatókönyvek.", OBJ("Egy forgatókönyv.", {
            "key": ENUM("HT = félidő, 3Q = 3 negyed után; LEAD = vezet, TRAIL = hátrányban.",
                        ("HT_LEAD", "HT_TRAIL", "3Q_LEAD", "3Q_TRAIL")),
            "label": STR("Felirat."),
            "games": INT("Ennyi meccsen állt így."),
            "wins": INT("Ebből ennyit nyert meg (vezetésnél: győzelem, hátránynál: fordítás)."),
        })),
        "scoring_split": OBJ("Pontmegoszlás dobástípus szerint.", {
            "points_2": INT("Kétpontosokból."),
            "points_3": INT("Hárompontosokból."),
            "points_ft": INT("Büntetőből."),
            "pct_2": INT("Kétpontosok aránya, %."),
            "pct_3": INT("Hárompontosok aránya, %."),
            "pct_ft": INT("Büntetők aránya, %."),
            "ft_made": INT("Bedobott büntető."),
            "ft_att": INT("Büntető-kísérlet."),
        }),
        "runs_for": ARR("Top 5 saját run.", run),
        "runs_against": ARR("Top 5 kapott run.", run),
        "facts": ARR("Fun factek; mindegyik szövegrészek listája (a kiemelt részek bold: true).",
                     ARR("Egy fact.", OBJ("Szövegrész.", {
                         "text": STR("Szöveg."),
                         "bold": BOOL("Kiemelt-e."),
                     }))),
    })


def stats_schema():
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Közgáz B szezonstatisztika (stats.json)",
        **OBJ("Egy szezon minden statisztikája. A szezonösszesítők (players, team) a bajnoki meccsekből "
              "(alapszakasz + rájátszás) készülnek, ahogy a kozgazkosar.hu-n; a kupameccsek a matches[]-ben vannak.", {
            "version": {"const": 1, "description": "Formátum-verzió."},
            "team": {"const": "kozgaz-b", "description": "Csapatkulcs."},
            "team_name": STR("A csapat neve az MKOSZ-nál."),
            "season": STR("Szezonkulcs (pl. x2627).", **SEASON),
            "season_label": STR("Szezon felirata (pl. 2026/27)."),
            "generated_at": STR("A fájl készítése (UTC).", **DATETIME),
            "source": OBJ("Forrás.", {
                "database": STR("A forrásadatbázis."),
                "database_updated_at": STR("Az adatbázis utolsó frissítése (UTC), ha ismert.", null=True),
                "aggregate_competitions": ARR("A szezonösszesítőkbe számító bajnokságok kódjai.", STR("Kód.")),
            }),
            "competitions": ARR("A szezon bajnokságai és kupái, ahol a Közgáz B játszott.", competition()),
            "matches": ARR("Lejátszott meccsek időrendben (bajnoki és kupa).", match()),
            "players": ARR("Játékosok, összpont szerint csökkenő sorrendben.", OBJ("Egy játékos.", {
                "key": STR("Játékoskulcs: licencszám, vagy ha nincs, a névből képzett slug."),
                "key_type": ENUM("license / name_slug.", ("license", "name_slug")),
                "name": STR("Név (a jegyzőkönyv szerint)."),
                "jersey": INT("Mezszám (a szezonban a legnagyobb előforduló).", null=True),
                "slug": STR("A névből képzett slug (a honlap játékosoldalának neve)."),
                "views": views(player_view(), "Nézetek: összes, hazai, idegen."),
            })),
            "team_stats": OBJ("Csapatszint (null, ha a szezonban még nincs bajnoki meccs).", {
                "views": team_views(),
            }, null=True),
            "league_comparison": ARR(
                "Csoport-összehasonlítás bajnokságonként (a honlap csoport.html-je): a csoport minden "
                "csapata a jegyzőkönyvek alapján, mutatónként rangsorolva.",
                OBJ("Egy bajnokság.", {
                    "competition": STR("Bajnokság-kód."),
                    "competition_label": STR("Bajnokság neve."),
                    "phase": ENUM("Szakasz.", PHASE),
                    "team_count": INT("A csoport csapatainak száma."),
                    "metrics": ARR("A mutatók, a honlap sorrendjében.", OBJ("Egy mutató rangsora.", {
                        "key": ENUM("A mutató kulcsa.", ("wl", "ppg", "oppg", "ft_pct", "fg2_pg", "fg3_pg",
                                                         "fta_total", "ftm_pg")),
                        "label": STR("A mutató címe (a honlap szerint)."),
                        "rows": ARR("A csapatok a mutató szerinti sorrendben.", OBJ("Egy csapat.", {
                            "rank": INT("Helyezés ebben a mutatóban (1-től)."),
                            "team": STR("Csapat teljes neve."),
                            "team_short": STR("Csapat rövid neve."),
                            "is_kozgaz": BOOL("A Közgáz B-e."),
                            "games": INT("Lejátszott meccsek a bajnokságban."),
                            "value": STR("Az érték, ahogy a honlap írja (pl. 9-13, 76.9, 67.6%)."),
                        })),
                    })),
                })),
        }),
    }


def standings_schema():
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Közgáz B tabella (standings.json)",
        **OBJ("A szezon tabellái bajnokságonként (rájátszásnál a Közgáz B csoportja).", {
            "version": {"const": 1, "description": "Formátum-verzió."},
            "team": {"const": "kozgaz-b", "description": "Csapatkulcs."},
            "season": STR("Szezonkulcs.", **SEASON),
            "season_label": STR("Szezon felirata."),
            "generated_at": STR("A fájl készítése (UTC).", **DATETIME),
            "tables": ARR("Tabellák.", OBJ("Egy tabella.", {
                "competition": STR("Bajnokság-kód."),
                "competition_label": STR("Bajnokság neve."),
                "phase": ENUM("regular / playoff.", PHASE),
                "source": STR("Forrás (MKOSZ)."),
                "source_url": STR("A forrásoldal."),
                "fetched_at": STR("A lekérés ideje (UTC).", **DATETIME),
                "rows": ARR("Sorok helyezés szerint.", OBJ("Egy csapat.", {
                    "rank": INT("Helyezés."),
                    "team": STR("Csapat teljes neve."),
                    "team_short": STR("Csapat rövid neve (a honlap rövidítése)."),
                    "is_kozgaz": BOOL("A Közgáz B sora-e."),
                    "games": INT("M: lejátszott meccs."),
                    "wins": INT("Gy: győzelem."),
                    "losses": INT("V: vereség."),
                    "scored": INT("Dob: dobott pont."),
                    "allowed": INT("Kap: kapott pont."),
                    "diff": INT("+/-: dobott − kapott."),
                    "points": INT("Pt: bajnoki pont."),
                    "streak": STR("Sorozat (MKOSZ „Sor”, pl. GY5 = 5 győzelem, V1 = 1 vereség).", null=True),
                })),
            })),
        }),
    }


def seasons_schema():
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Közgáz B elérhető szezonok (seasons.json)",
        **OBJ("Az elérhető szezonok, a legújabb elöl.", {
            "version": {"const": 1, "description": "Formátum-verzió."},
            "team": {"const": "kozgaz-b", "description": "Csapatkulcs."},
            "current_season": STR("A mostani (legutóbbi) szezon kulcsa.", **SEASON),
            "generated_at": STR("A fájl készítése (UTC).", **DATETIME),
            "seasons": ARR("Szezonok.", OBJ("Egy szezon.", {
                "season": STR("Szezonkulcs.", **SEASON),
                "label": STR("Felirat (pl. 2025/26)."),
                "competitions": ARR("Bajnokságok és kupák.", competition()),
                "match_count": INT("Lejátszott meccsek száma a stats.json-ban."),
                "first_match_date": STR("Első meccs.", **DATE),
                "last_match_date": STR("Utolsó meccs.", **DATE),
                "stats": STR("A stats.json útvonala a seasons.json-hoz képest."),
                "standings": STR("A standings.json útvonala a seasons.json-hoz képest."),
            })),
        }),
    }


def history_schema():
    rank = OBJ("A Közgáz helyezése egy bajnokság tabelláján.", {
        "competition": STR("Bajnokság-kód."),
        "competition_label": STR("Bajnokság neve."),
        "phase": ENUM("Szakasz.", PHASE),
        "rank": INT("Helyezés (1-től)."),
        "teams": INT("A tabella csapatainak száma."),
    })
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Közgáz B szezonról szezonra (history.json)",
        **OBJ("Minden szezon tömör, meccsenkénti mutatói a csapatra és a játékosokra, a szezonok "
              "összehasonlításához. Ugyanazok a számok, mint a szezonok stats.json-jában (a bajnoki "
              "meccsekből, views.all), csak meccsenkéntire osztva; a helyezés a standings.json-ból.", {
            "version": {"const": 1, "description": "Formátum-verzió."},
            "team": {"const": "kozgaz-b", "description": "Csapatkulcs."},
            "generated_at": STR("A fájl készítése (UTC).", **DATETIME),
            "seasons": ARR("A szezonok, a legrégebbi elöl.", OBJ("Egy szezon.", {
                "season": STR("Szezonkulcs.", **SEASON),
                "label": STR("Felirat (pl. 2025/26)."),
                "team": OBJ("A csapat a bajnoki meccsekből (null, ha még nincs bajnoki meccs).", {
                    "games": INT("Bajnoki meccs."),
                    "wins": INT("Győzelem."),
                    "losses": INT("Vereség."),
                    "win_pct": NUM("Győzelem-arány, % (egy tizedes)."),
                    "ppg": NUM("Dobott/meccs."),
                    "opp_ppg": NUM("Kapott/meccs."),
                    "diff_per_game": NUM("Különbség/meccs."),
                    "ft_pct": NUM("Büntető%, egy tizedes; null, ha nem volt kísérlet.", null=True),
                    "fg2_per_game": NUM("Bedobott kettes/meccs, egy tizedes."),
                    "fg3_per_game": NUM("Bedobott hármas/meccs, egy tizedes."),
                    "home_wins": INT("Hazai győzelem."),
                    "home_games": INT("Hazai meccs."),
                    "away_wins": INT("Idegenbeli győzelem."),
                    "away_games": INT("Idegenbeli meccs."),
                    "quarters": ARR("Negyedátlagok.", OBJ("Egy negyed.", {
                        "quarter": INT("Negyed (1–4)."),
                        "kozgaz_avg": NUM("Közgáz pont/meccs a negyedben."),
                        "opponent_avg": NUM("Ellenfél pont/meccs a negyedben."),
                    })),
                }, null=True),
                "standings": ARR("A Közgáz helyezése a szezon tabelláin (alapszakasz elöl).", rank),
            })),
            "players": ARR("A játékosok, mindegyik a saját szezonjaival (a legrégebbi elöl). A "
                           "szezonokat a játékoskulcs köti össze.", OBJ("Egy játékos.", {
                "key": STR("Játékoskulcs: licencszám, vagy ha nincs, a névből képzett slug."),
                "key_type": ENUM("license / name_slug.", ("license", "name_slug")),
                "name": STR("Név a legutóbbi szezonja jegyzőkönyvei szerint."),
                "seasons": ARR("A szezonjai, amelyekben bajnoki meccsen pályára lépett.", OBJ("Egy szezon.", {
                    "season": STR("Szezonkulcs.", **SEASON),
                    "games": INT("Meccs."),
                    "points": INT("Pont."),
                    "ppg": NUM("Pont/meccs."),
                    "max_points": INT("Legtöbb pont egy meccsen."),
                    "fg2_per_game": NUM("Bedobott kettes/meccs, egy tizedes."),
                    "fg3_per_game": NUM("Bedobott hármas/meccs, egy tizedes."),
                    "ft_made": INT("Bedobott büntető."),
                    "ft_att": INT("Büntető-kísérlet."),
                    "ft_pct": NUM("Büntető%, ahogy a stats.json-ban; null, ha nem volt kísérlet.", null=True),
                    "pf_per_game": NUM("Fault/meccs."),
                })),
            })),
        }),
    }


SCHEMAS = {
    "stats": stats_schema,
    "standings": standings_schema,
    "seasons": seasons_schema,
    "history": history_schema,
}
FILES = {  # séma → a kimenet mely fájljaira vonatkozik (glob a data/kozgaz-b mappán belül)
    "stats": ["stats.json", "x*/stats.json"],
    "standings": ["standings.json", "x*/standings.json"],
    "seasons": ["seasons.json"],
    "history": ["history.json"],
}


# ─────────────────────────── docs ───────────────────────────

DOCS_HEADER = """# A statisztika-JSON-ok (stats.json, standings.json, seasons.json, history.json)

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
  `regular` / `playoff` bontásban is (különben ezek `null`). A kupameccsek (Hepp Kupa) a
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
"""


def _type_str(node):
    t = node.get("type")
    if t is None and "const" in node:
        return f"const {json.dumps(node['const'], ensure_ascii=False)}"
    if isinstance(t, list):
        base = [x for x in t if x != "null"][0]
        s = base + "?"
    else:
        s = t
    if "enum" in node:
        vals = [v for v in node["enum"] if v is not None]
        s += " (" + " | ".join(vals) + ")"
    return s


def _walk(node, path, rows):
    rows.append((path, _type_str(node), node.get("description", "")))
    if node.get("properties"):
        for k, child in node["properties"].items():
            _walk(child, f"{path}.{k}" if path else k, rows)
    if node.get("type") == "array":
        _walk_items(node["items"], path + "[]", rows)


def _walk_items(node, path, rows):
    if node.get("properties") or node.get("type") == "array":
        if node.get("type") == "array":
            rows.append((path, "array", node.get("description", "")))
            _walk_items(node["items"], path + "[]", rows)
        else:
            for k, child in node["properties"].items():
                _walk(child, f"{path}.{k}", rows)


def render_docs():
    out = [DOCS_HEADER]
    titles = {"stats": "stats.json", "standings": "standings.json", "seasons": "seasons.json",
              "history": "history.json"}
    for name, fn in SCHEMAS.items():
        schema = fn()
        out.append(f"\n## {titles[name]}\n\n{schema['description']}\n")
        out.append("| Mező | Típus | Jelentés |\n|---|---|---|")
        rows = []
        for k, child in schema["properties"].items():
            _walk(child, k, rows)
        # A views alatt az all/home/away ugyanaz: csak az all-t írjuk ki, a többire utalunk.
        for path, typ, desc in rows:
            sub = next((m for m in (".views.home", ".views.away", ".views.regular", ".views.playoff")
                        if m in path), None)
            if sub:
                if path.endswith(sub):
                    if sub in (".views.regular", ".views.playoff"):
                        out.append(f"| `{path}` | object? | Mint a `views.all`, csak "
                                   f"{'az alapszakasz' if sub.endswith('regular') else 'a rájátszás'} meccseiből; "
                                   f"null, ha a szezonban nincs rájátszás. |")
                    else:
                        out.append(f"| `{path}` | object | Mint a `views.all`. |")
                continue
            out.append(f"| `{path}` | {typ} | {desc.replace('|', '/')} |")
    return "\n".join(out) + "\n"


def schema_texts():
    return {name: json.dumps(fn(), ensure_ascii=False, indent=2) + "\n" for name, fn in SCHEMAS.items()}


def write():
    os.makedirs(SCHEMA_DIR, exist_ok=True)
    for name, text in schema_texts().items():
        with open(os.path.join(SCHEMA_DIR, f"{name}.schema.json"), "w", encoding="utf-8") as f:
            f.write(text)
    os.makedirs(os.path.dirname(DOCS_PATH), exist_ok=True)
    with open(DOCS_PATH, "w", encoding="utf-8") as f:
        f.write(render_docs())
    print("  ✓ schemas/*.schema.json + docs/STATS_JSON.md")


def check(out_dir):
    import jsonschema  # csak az ellenőrzéshez kell (pip install jsonschema)

    problems = []
    for name, text in schema_texts().items():
        path = os.path.join(SCHEMA_DIR, f"{name}.schema.json")
        if not os.path.exists(path) or open(path, encoding="utf-8").read() != text:
            problems.append(f"schemas/{name}.schema.json nem naprakész (python3 stats_schema.py write)")
    if not os.path.exists(DOCS_PATH) or open(DOCS_PATH, encoding="utf-8").read() != render_docs():
        problems.append("docs/STATS_JSON.md nem naprakész (python3 stats_schema.py write)")

    data_dir = os.path.join(out_dir, "data", "kozgaz-b")
    checked = 0
    for name, patterns in FILES.items():
        schema = SCHEMAS[name]()
        validator = jsonschema.Draft202012Validator(schema)
        files = sorted({f for p in patterns for f in glob.glob(os.path.join(data_dir, p))})
        if not files:
            problems.append(f"nincs {name} fájl a kimenetben")
        for f in files:
            data = json.load(open(f, encoding="utf-8"))
            errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
            for e in errors[:5]:
                loc = "/".join(str(x) for x in e.path)
                problems.append(f"{os.path.relpath(f, out_dir)}: {loc}: {e.message[:200]}")
            checked += 1
    # A seasons.json-ban felsorolt fájlok léteznek-e
    seasons_path = os.path.join(data_dir, "seasons.json")
    if os.path.exists(seasons_path):
        seasons = json.load(open(seasons_path, encoding="utf-8"))
        for s in seasons.get("seasons", []):
            for key in ("stats", "standings"):
                if not os.path.exists(os.path.join(data_dir, s[key])):
                    problems.append(f"seasons.json: hiányzik {s[key]}")
    if problems:
        print("✗ Séma-ellenőrzés sikertelen:")
        for p in problems:
            print("  - " + p)
        sys.exit(1)
    print(f"  ✓ séma-ellenőrzés: {checked} fájl rendben")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "write":
        write()
    elif len(sys.argv) >= 3 and sys.argv[1] == "check":
        check(sys.argv[2])
    else:
        sys.exit(__doc__)
