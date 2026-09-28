#!/usr/bin/env python3
"""
project.py -- design every beam, column, joint and footing of a project for the NSCP 2015
load combinations generated from their UNFACTORED load cases, and compile all results
(JSON + Markdown calc sheets + P-M figures + summary) into ONE zip.

    python3 project.py project.json [--out DIR] [--no-zip]
    python3 project.py --template            # a two-storey SMRF example

Order (each step feeds the next):
  1. beams    -> rc-design (subprocess) on the per-station envelope of the combinations
  2. columns  -> P-M-M + SMF; strong column uses the DESIGNED beams' Mn, the Ve cap their Mpr
  3. joints   -> 418.8 with the designed beam bars and the column's hoops
  4. footings -> service + strength design from the column-base load cases
Members reference each other by id: column joints list beam ends ("beam_ends": [["B1", "J"]]);
joints name their column and beams; footings name their column.
"""

import csv
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import beam as bm                                                       # noqa: E402
import combos as cmb                                                    # noqa: E402
import report                                                           # noqa: E402
from design_column import design_one as design_column, merge, rnd       # noqa: E402
from footing import design_footing                                      # noqa: E402
from joint import check_joint                                           # noqa: E402

VERSION = "apec-col-design/project 0.1.0"


def slug(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(s)).strip("_") or "project"


def _with_globals(member, proj, kind):
    g = {}
    if proj.get("loads"):
        g["loads"] = proj["loads"]
    if proj.get("case_types"):
        g["case_types"] = proj["case_types"]
    mat = (proj.get("materials") or {}).get(kind)
    if mat:
        g["materials"] = mat
    return merge(g, member)


def _beam_pair(beam_res, ends):
    """Sum of Mn / Mpr for both sway senses from [[beam_id, end], ...] (first = left)."""
    s = [bm.end_strengths(beam_res[b], e) for b, e in ends if b in beam_res]
    if not s or any(x["Mn_neg"] is None or x["Mn_pos"] is None for x in s):
        return None
    if len(s) == 1:
        mnb = [s[0]["Mn_neg"], s[0]["Mn_pos"]]
        mpr = [s[0]["Mpr_neg"] or 0.0, s[0]["Mpr_pos"] or 0.0]
    else:
        a, b = s[0], s[1]
        mnb = [a["Mn_neg"] + b["Mn_pos"], a["Mn_pos"] + b["Mn_neg"]]
        mpr = [(a["Mpr_neg"] or 0) + (b["Mpr_pos"] or 0), (a["Mpr_pos"] or 0) + (b["Mpr_neg"] or 0)]
    return {"Mnb": mnb, "Mpr_b": max(mpr) if any(mpr) else None}


def run(proj, outdir, make_zip=True):
    name = slug(proj.get("project", "project"))
    root = os.path.join(outdir, name)
    if os.path.isdir(root):
        shutil.rmtree(root)
    for sub in ("beams", "columns", "joints", "footings", "input"):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    json.dump(proj, open(os.path.join(root, "input", "project.json"), "w"), indent=2)
    results = {"beams": [], "columns": [], "joints": [], "footings": []}
    beam_res, col_res, col_in = {}, {}, {}
    combos_md = []
    log = []

    # 1 ---------------------------------------------------------------- beams
    for m in proj.get("beams", []):
        inp = _with_globals(m, proj, "beam")
        r = bm.design_beam(inp, keep_dir=os.path.join(root, "beams"))
        beam_res[r["id"]] = r
        results["beams"].append(r)
        json.dump(rnd(r), open(os.path.join(root, "beams", f"{slug(r['id'])}.json"), "w"), indent=2, default=str)
        open(os.path.join(root, "beams", f"{slug(r['id'])}.md"), "w").write(report.beam_md(r))
        combos_md.append(f"## Beam {r['id']}\n\n{report._combos_table(r['combinations'])}\n")
        log.append(f"beam {r['id']}: {r.get('verdict')}")

    # 2 ---------------------------------------------------------------- columns
    for m in proj.get("columns", []):
        inp = _with_globals(m, proj, "column")
        for end in ("top", "bottom"):
            j = (inp.get("joints") or {}).get(end) or {}
            for ax in ("Mx", "My"):
                ref = j.get(ax)
                if ref and ref.get("beam_ends"):
                    pair = _beam_pair(beam_res, ref["beam_ends"])
                    if pair:
                        ref.setdefault("Mnb", pair["Mnb"])
                        if pair["Mpr_b"] is not None:
                            ref.setdefault("Mpr_b", pair["Mpr_b"])
                    else:
                        log.append(f"column {inp.get('id')}: {end}.{ax} beams not designed -- SCWB/Ve cap skipped")
        r = design_column(inp)
        import plots
        r["figures"] = plots.column_figures(r, os.path.join(root, "columns"))
        col_res[r["id"]], col_in[r["id"]] = r, inp
        results["columns"].append(r)
        json.dump(rnd(r), open(os.path.join(root, "columns", f"{slug(r['id'])}.json"), "w"), indent=2, default=str)
        open(os.path.join(root, "columns", f"{slug(r['id'])}.md"), "w").write(report.column_md(r))
        combos_md.append(f"## Column {r['id']}\n\n{report._combos_table(r['combinations'])}\n")
        log.append(f"column {r['id']}: {r['verdict']}")

    # 3 ---------------------------------------------------------------- joints
    for m in proj.get("joints", []):
        j = dict(m)
        c = col_res.get(j.get("column"))
        cin = col_in.get(j.get("column")) or {}
        if c:
            sec = c["section"]
            par = sec["b"] if str(j.get("direction", "X")).upper() == "X" else sec["h"]
            per = sec["h"] if str(j.get("direction", "X")).upper() == "X" else sec["b"]
            j.setdefault("column", None)
            j["column"] = {"h": par, "b": per}
            j.setdefault("fc", c["materials"]["fc"])
            j.setdefault("column_cover", sec["cover"])
            j.setdefault("column_dbt", (c.get("hoops") or {}).get("db", sec.get("dbt", 10.0)))
            if c.get("hoops") and c["hoops"].get("s_lo"):
                j.setdefault("column_hoops", {"s_lo": c["hoops"]["s_lo"]})
        for side in ("beam_left", "beam_right"):
            ref = j.get(side)
            if isinstance(ref, dict) and ref.get("beam"):
                br = beam_res.get(ref["beam"])
                if not br or not br.get("rc_design"):
                    j[side] = None
                    log.append(f"joint {j.get('id')}: beam {ref['beam']} not designed")
                    continue
                top, bot = bm.end_bars(br, ref["end"])
                st = bm.end_strengths(br, ref["end"])
                sec_b = br["rc_design_input"]["section"]
                j[side] = {"id": ref["beam"], "b": sec_b["b"], "h": sec_b["h"], "top": top, "bot": bot,
                           "Mpr_neg": st["Mpr_neg"], "Mpr_pos": st["Mpr_pos"]}
                j.setdefault("fy", br["rc_design_input"].get("materials", {}).get("fy", 413.686))
                j.setdefault("beam_cover", sec_b.get("cover", 40.0))
                j.setdefault("beam_dbs", sec_b.get("dbs", 12.0))
        j.setdefault("fy", 413.686)
        r = check_joint(j)
        results["joints"].append(r)
        json.dump(rnd(r), open(os.path.join(root, "joints", f"{slug(r['id'])}.json"), "w"), indent=2, default=str)
        open(os.path.join(root, "joints", f"{slug(r['id'])}.md"), "w").write(report.joint_md(r))
        log.append(f"joint {r['id']}: {r['verdict']}")

    # 4 ---------------------------------------------------------------- footings
    for m in proj.get("footings", []):
        f = _with_globals(m, proj, "footing")
        cid = f.get("column")
        if isinstance(cid, str):
            cin = col_in.get(cid)
            if not cin:
                raise ValueError(f"footing {f.get('id')}: column {cid!r} not found")
            f["cases"] = f.get("cases") or {k: {"P": v.get("P", 0.0), "Mx": v.get("Mx_bot", 0.0),
                                                "My": v.get("My_bot", 0.0), "Vx": v.get("Vx", 0.0),
                                                "Vy": v.get("Vy", 0.0)} for k, v in cin["cases"].items()}
            f.setdefault("case_types", cin.get("case_types"))
            sec = col_res[cid]["section"]
            f["column"] = {"b": sec["b"], "h": sec["h"]} if sec["shape"] == "rect" else {"b": sec["D"], "h": sec["D"]}
        r = design_footing(f)
        results["footings"].append(r)
        json.dump(rnd(r), open(os.path.join(root, "footings", f"{slug(r['id'])}.json"), "w"), indent=2, default=str)
        open(os.path.join(root, "footings", f"{slug(r['id'])}.md"), "w").write(report.footing_md(r))
        combos_md.append(f"## Footing {r['id']} — service\n\n{report._combos_table(r['combinations_service'])}\n")
        log.append(f"footing {r['id']}: {r['verdict']}")

    # ---------------------------------------------------------------- summary + zip
    open(os.path.join(root, "00_summary.md"), "w").write(report.project_md(proj, results, combos_md))
    open(os.path.join(root, "combinations.md"), "w").write(
        "# Load combinations generated per member (NSCP 2015 §203)\n\n" + "\n".join(combos_md))
    with open(os.path.join(root, "summary.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["type", "id", "verdict", "detail"])
        for kind, lst in results.items():
            for r in lst:
                if kind == "columns":
                    g = r["governing"]
                    det = f"{r['schedule']['longitudinal']} | DC {max(g['DC_M'], g['DC_PMM'] or 0):.3f} {g['combo']}"
                elif kind == "joints":
                    det = f"Vj {r['Vj']:.1f} / phiVn {r['phiVn']:.1f} kN"
                elif kind == "footings":
                    det = f"{r['schedule']['plan']} | {r['schedule']['bars_x']}"
                else:
                    det = json.dumps(r.get("schedule") or {})[:200]
                w.writerow([kind[:-1], r["id"], r.get("verdict"), det])
    open(os.path.join(root, "run_log.txt"), "w").write("\n".join([VERSION] + log) + "\n")
    zpath = None
    if make_zip:
        zpath = shutil.make_archive(os.path.join(outdir, f"{name}_results"), "zip", root_dir=outdir, base_dir=name)
    return {"root": root, "zip": zpath, "log": log,
            "verdicts": {k: {r["id"]: r.get("verdict") for r in v} for k, v in results.items()}}


def main(argv):
    if "--template" in argv:
        here = os.path.dirname(os.path.abspath(__file__))
        print(open(os.path.join(here, "..", "examples", "project_two_storey.json")).read()); return 0
    args = [a for a in argv if not a.startswith("--")]
    out = argv[argv.index("--out") + 1] if "--out" in argv else "."
    args = [a for a in args if a != out]
    if not args:
        print(__doc__); return 2
    proj = json.load(open(args[0]))
    res = run(proj, out, make_zip="--no-zip" not in argv)
    print(json.dumps(res, indent=2))
    bad = [i for v in res["verdicts"].values() for i, s in v.items() if s in ("FAIL", "ERROR", "NOT RUN")]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
