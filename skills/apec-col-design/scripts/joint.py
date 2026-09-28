#!/usr/bin/env python3
"""
joint.py -- beam-column joints of special moment frames, NSCP 2015 Section 418.8.

Re-implements concretedesignpy.calculators.joint_shear as rectified 2026-08-15 (vault
Software/14 F-10/F-11; CLAUSES.md A.4) and adds the rest of 418.8.  Pages: NSCP folio
4-117/4-118 and 4-141 READ VISUALLY 2026-09-28 | ACI 318-25M printed.

* 418.8.2.1 beam bar forces at 1.25 fy                                  4-117 | 18.8.2.1, 340
* 418.8.2.3 column dimension parallel to beam bars >= 20 db (26 db lightweight)
                                                                         4-118 | 18.8.2.3, 340-341
* 418.8.2.4 joint depth h >= half the depth of any beam generating joint shear
                                                                         4-118 | 18.8.2.3(c), 341
* 418.8.3.1 joint hoops per 418.7.5.2-.4 and .7; 418.8.3.2: beams on all four sides, each
  >= 3/4 of the column width -> half the Ash and s <= 150 mm within the shallowest beam
                                                                         4-118 | 18.8.3, 341
* Table 418.8.4.1 Vn = gamma lam sqrt(f'c) Aj, gamma = 1.7 (four faces confined) /
  1.2 (three faces or two opposite faces) / 1.0 (other) -- NSCP's 3-row table; ACI
  318-25M Table 18.8.4.3 has 8 rows (edition change, not used)          4-118 | 342
* 418.8.4.2 a face is confined when the beam width >= 3/4 of the effective joint width
                                                                         4-118
* 418.8.4.3 Aj = h x bj, bj = column width, or where the column is wider than the beam
  <= min(b + h, b + 2x) (x = beam face to column side); never > column width
  (R15.5.2.2, 318-25M printed 231-232)                                   4-118 | 18.8.4.3
* phi = 0.85 ............................................................ 421.2.4.3, 4-141 | 21.2.4.4, 435
* Vj = 1.25 fy (As,top one side + As,bot other side) - Vcol  (both sways)
  Vcol = (Sum Mpr of the beams + Sum Ve,beam x hc/2) / l_c between column mid-heights
  (NIST GCR 8-917-1 5.2 Figs 5-4/5-5, printed 13-14; vault Concrete/05).  Without beam Ve
  the hc/2 term is dropped -- smaller Vcol, larger Vj: conservative.
* 418.8.5.1 hooked beam bars terminating in the joint: ldh = fy db / (5.4 lam sqrt(f'c))
  >= max(8 db, 150 mm), within the confined core                        4-118 | 18.8.5.1, 342

Units: kN, kN.m, mm, MPa.  Mpr of a beam is computed here by strain compatibility at
1.25 fy, phi = 1, WITH the compression steel (vault Software/12 D3), unless given.
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pm import Column                                                   # noqa: E402
from section import bar_area, build_section                             # noqa: E402

GAMMA = {4: 1.7, 3: 1.2, "2opp": 1.2, "other": 1.0}
PHI_JOINT = 0.85
VERSION = "apec-col-design/joint 0.1.0"


def _as(bars):
    """[n, db] or [[n, db], [n, db]] -> (area mm2, largest db)."""
    if not bars:
        return 0.0, 0.0
    if isinstance(bars[0], (list, tuple)):
        a = sum(n * bar_area(db) for n, db in bars)
        return a, max(db for _, db in bars)
    n, db = bars
    return n * bar_area(db), db


def beam_mpr(beam, fc, fy, cover=40.0, dbs=10.0):
    """(Mpr_neg, Mpr_pos, Mn_neg, Mn_pos) kN.m of a rectangular beam from its bars."""
    b, h = beam["b"], beam["h"]
    at, dt = _as(beam["top"])
    ab, dbb = _as(beam["bot"])
    et, eb = cover + dbs + dt / 2.0, cover + dbs + dbb / 2.0
    rows = []
    if at:
        rows += [[x, h / 2.0 - et, dt, at / 4.0] for x in (-b / 4, -b / 8, b / 8, b / 4)]
    if ab:
        rows += [[x, -h / 2.0 + eb, dbb, ab / 4.0] for x in (-b / 4, -b / 8, b / 8, b / 4)]
    sec = build_section({"shape": "rect", "b": b, "h": h, "cover": cover}, {"custom": rows})
    col = Column(sec, fc, fy)
    out = {}
    for key, sign, fyf in (("Mpr_pos", 1, 1.25), ("Mpr_neg", -1, 1.25), ("Mn_pos", 1, 1.0), ("Mn_neg", -1, 1.0)):
        # +Mx compresses the top: that is the POSITIVE (sagging) beam moment
        r = col.moment_at("x", 0.0, sign, fyf)
        out[key] = r["M"] / 1e6 if r else 0.0
    return out


def check_joint(j):
    """One joint, one direction.  j: see TEMPLATE."""
    fc, fy, lam = j["fc"], j["fy"], j.get("lam", 1.0)
    hc = j["column"]["h"]                  # column dimension parallel to the beams (joint depth)
    bc = j["column"]["b"]                  # column dimension perpendicular
    beams = [b for b in (j.get("beam_left"), j.get("beam_right")) if b]
    if not beams:
        raise ValueError("a joint needs at least one beam in the direction checked")
    checks, warns = [], []

    def add(cid, clause, page, ok, value, limit, note=""):
        checks.append({"id": cid, "clause": clause, "page": page,
                       "status": ok if isinstance(ok, str) else ("OK" if ok else "FAIL"),
                       "value": value, "limit": limit, "note": note})

    for bm in beams:
        if bm.get("Mpr_neg") is None or bm.get("Mpr_pos") is None:
            bm.update({k: v for k, v in beam_mpr(bm, fc, fy, j.get("beam_cover", 40.0),
                                                 j.get("beam_dbs", 10.0)).items() if bm.get(k) is None})
    Tt = [1.25 * fy * _as(bm["top"])[0] / 1e3 for bm in beams]
    Tb = [1.25 * fy * _as(bm["bot"])[0] / 1e3 for bm in beams]
    # ---------------- column shear from the beam probable moments
    H_ab, H_bl = j.get("H_above"), j.get("H_below")
    if j.get("Vcol") is not None:
        vcol_pair = (float(j["Vcol"]), float(j["Vcol"]))
        vcol_src = "given"
    else:
        lc = ((H_ab + H_bl) / 2.0 if H_ab and H_bl else (H_bl or H_ab)) / 1000.0
        ve = j.get("beam_Ve") or [0.0] * len(beams)
        s1 = beams[0].get("Mpr_neg", 0) + (beams[1].get("Mpr_pos", 0) if len(beams) > 1 else 0)
        s2 = beams[0].get("Mpr_pos", 0) + (beams[1].get("Mpr_neg", 0) if len(beams) > 1 else 0)
        extra = sum(ve) * hc / 2000.0
        vcol_pair = ((s1 + extra) / lc, (s2 + extra) / lc)
        vcol_src = (f"(Sum Mpr{' + Sum Ve hc/2' if any(ve) else ''}) / l_c, l_c = {lc:.2f} m "
                    "(NIST GCR 8-917-1 Fig. 5-4)")
    # both sway senses: left beam hogging (top in tension) + right beam sagging, and reverse
    if len(beams) == 2:
        vj1 = Tt[0] + Tb[1] - vcol_pair[0]
        vj2 = Tb[0] + Tt[1] - vcol_pair[1]
    else:
        vj1, vj2 = Tt[0] - vcol_pair[0], Tb[0] - vcol_pair[1]
    vj = max(vj1, vj2)
    # ---------------- effective area and gamma
    bw = max(bm["b"] for bm in beams)
    x = j.get("x_offset", max(0.0, (bc - bw) / 2.0))
    bj = bc if bw >= bc else min(bc, bw + hc, bw + 2.0 * x)
    Aj = bj * hc
    faces = j.get("confined_faces")
    if faces is None:
        cnt, opp = 0, False
        wide = lambda w: w is not None and w >= 0.75 * bj
        sides = [wide(beams[0]["b"]) if j.get("beam_left") else False,
                 wide(j["beam_right"]["b"]) if j.get("beam_right") else False,
                 wide(j.get("transverse_left_b")), wide(j.get("transverse_right_b"))]
        cnt = sum(sides)
        opp = (sides[0] and sides[1]) or (sides[2] and sides[3])
        cat = 4 if cnt == 4 else (3 if cnt == 3 else ("2opp" if opp and cnt >= 2 else "other"))
    else:
        cat = faces
    gamma = GAMMA[cat]
    vn = gamma * lam * math.sqrt(fc) * Aj / 1e3
    add("joint_shear", "Table 418.8.4.1 + 421.2.4.3 | 18.8.4, 21.2.4.4", "4-118, 4-141 | 342, 435",
        PHI_JOINT * vn >= vj - 1e-6, round(PHI_JOINT * vn, 1), f">= Vj {vj:.1f} kN",
        f"gamma {gamma} ({cat} faces confined), Aj {Aj:,.0f} mm2 (bj {bj:.0f} x h {hc:.0f}), "
        f"Vcol {max(vcol_pair):.1f} kN")
    # ---------------- 418.8.2.3 / .4
    db_max = max(max(_as(bm["top"])[1], _as(bm["bot"])[1]) for bm in beams)
    need = (26.0 if lam < 1.0 else 20.0) * db_max
    if len(beams) == 2 or j.get("bars_continuous", True):
        add("column_depth_20db", "418.8.2.3 | 18.8.2.3", "4-118 | 340-341", hc >= need - 1e-9, hc,
            f">= {need:.0f} mm (D{db_max:g} beam bars)", "the beam bar size sets the column depth")
    hb = max(bm["h"] for bm in beams)
    add("joint_depth_half_beam", "418.8.2.4 | 18.8.2.3(c)", "4-118 | 341", hc >= 0.5 * hb - 1e-9, hc,
        f">= {0.5 * hb:.0f} mm")
    # ---------------- 418.8.5.1 hooked bars (exterior joint)
    if len(beams) == 1 or j.get("hooked"):
        ldh = max(fy * db_max / (5.4 * lam * math.sqrt(fc)), 8.0 * db_max, 150.0)
        avail = hc - j.get("column_cover", 40.0) - j.get("column_dbt", 10.0)
        add("hook_development", "418.8.5.1 | 18.8.5.1", "4-118 | 342", ldh <= avail + 1e-9, round(ldh, 0),
            f"<= {avail:.0f} mm available in the confined core",
            "extend to the far face of the core (418.8.2.2); straight bars through an exterior "
            "joint are not permitted to substitute")
    # ---------------- 418.8.3 joint hoops
    four = cat == 4 and all((w or 0) >= 0.75 * bc for w in (
        beams[0]["b"], (j.get("beam_right") or {}).get("b"), j.get("transverse_left_b"), j.get("transverse_right_b")))
    col_h = j.get("column_hoops")
    note_h = ("beams on all four sides >= 3/4 column width: Ash may be halved and s <= 150 mm within the "
              "shallowest beam depth (418.8.3.2)" if four else
              "provide the column lo hoops (418.7.5.2-.4) through the full joint depth (418.8.3.1)")
    if col_h:
        need_s = 150.0 if four else col_h.get("s_lo_max", col_h.get("s_lo"))
        add("joint_hoops", "418.8.3.1 / 418.8.3.2 | 18.8.3", "4-118 | 341",
            col_h["s_lo"] <= need_s + 1e-9 if not four else True, col_h["s_lo"],
            f"<= {need_s:.0f} mm", note_h)
    return {"id": j.get("id"), "tool": VERSION, "member": "joint", "direction": j.get("direction", "-"),
            "verdict": "FAIL" if any(c["status"] == "FAIL" for c in checks) else "OK",
            "Vj": vj, "Vj_sway": [vj1, vj2], "Vcol": list(vcol_pair), "Vcol_basis": vcol_src,
            "T_top": Tt, "T_bot": Tb, "bj": bj, "Aj": Aj, "gamma": gamma, "category": cat,
            "phiVn": PHI_JOINT * vn, "Vn": vn, "DC": vj / (PHI_JOINT * vn) if vn > 0 else math.inf,
            "beams": beams, "checks": checks, "warnings": warns, "joint_hoops_note": note_h,
            "not_checked": ["beam bar anchorage lengths other than 418.8.5.1 hooks",
                            "joint eccentricity (beam offset > column face) torsion",
                            "ACI 318-25M 8-row gamma table (edition change)"]}


TEMPLATE = {
    "id": "J-C1-2F-X", "direction": "X", "fc": 27.579, "fy": 413.686, "lam": 1.0,
    "column": {"b": 500, "h": 500},
    "beam_left": {"b": 300, "h": 500, "top": [4, 20], "bot": [3, 20]},
    "beam_right": {"b": 300, "h": 500, "top": [4, 20], "bot": [3, 20]},
    "transverse_left_b": 300, "transverse_right_b": 300,
    "H_above": 3600, "H_below": 3600,
    "column_hoops": {"s_lo": 100},
}


def main(argv):
    if "--template" in argv:
        print(json.dumps(TEMPLATE, indent=2)); return 0
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__); return 2
    res = check_joint(json.load(open(args[0])))
    print(json.dumps(res, indent=2, default=str))
    return 1 if res["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
