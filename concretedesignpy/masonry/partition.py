# MIT License
# Copyright (c) Albert Pamonag Engineering Consultancy

"""Non-load-bearing CHB partition / infill — Gap #133 (JB Tower CN-01).

Self weight: NSCP 2015 Table 204-2. Seismic: Fp per §208.9 (Table 208-13 partitions / exterior walls).
Empirical §710.4 lateral-support limit; §709.4.1.2–709.4.1.3 isolation and minimum reinforcement.
When the empirical ratio fails, a reinforced ASD out-of-plane check (span = floor to soffit) picks the
lightest vertical bar/spacing that passes.
"""

import math

from nscp2015 import elements
from nscp2015 import masonry as mas

from concretedesignpy.clause import clause
from concretedesignpy.masonry.wall_oop import chk, flag, require, summarize, wall_out_of_plane

BAR_CANDIDATES = [(12, 1200), (12, 1000), (12, 800), (16, 1200), (12, 600), (16, 800), (12, 400), (16, 600),
                  (16, 400)]  # ascending As/s; 12 mm minimum per §709.4.1.3


@clause("NSCP2015-204-T204-2", "NSCP2015-208.9", "NSCP2015-710", "NSCP2015-709", "NSCP2015-706.2")
def partition(p):
    """p: h_mm, l_mm (clear spacing of vertical stiffeners, or None), t_nom_mm, t_spec_mm, unit_density_kN_m3,
    grout_spacing ('none'|800|600|400|'full'), plastered_faces, location 'interior'|'exterior', fm_MPa, fy_MPa,
    mortar, special_inspection, zone, Ca, Ip, hx_m, hr_m; optional wind_kPa (exterior), face_shell_mm."""
    require(p, "h_mm", "t_nom_mm", "t_spec_mm", "unit_density_kN_m3", "grout_spacing", "plastered_faces",
            "location", "fm_MPa", "fy_MPa", "mortar", "special_inspection", "zone", "Ca", "Ip", "hx_m", "hr_m")
    h, tn = float(p["h_mm"]), float(p["t_nom_mm"])
    l = float(p["l_mm"]) if p.get("l_mm") else None
    loc = p["location"]
    if loc not in ("interior", "exterior"):
        raise ValueError("location must be interior or exterior")
    checks, notes = [], []

    w = mas.chb_wall_weight(p["unit_density_kN_m3"], p["grout_spacing"], tn, int(p["plastered_faces"]))
    key = "partitions" if loc == "interior" else "exterior_wall_braced_above_cg"
    ap, Rp = elements.TABLE_208_13[key]
    Fp, fpd = elements.Fp(float(p["Ca"]), float(p["Ip"]), w, ap, Rp, float(p["hx_m"]), float(p["hr_m"]), detail=True)
    wind = float(p.get("wind_kPa") or 0.0)
    inter = {"wall_kPa": w, "ap": ap, "Rp": Rp, "Fp_kPa": Fp, "Fp_detail": fpd, "wind_kPa": wind}

    # §710.4 empirical lateral support
    ratio_max = mas.lateral_support_ratio_max(False, loc)
    span = h if l is None else min(h, l)
    emp_ok = mas.empirical_lateral_support_ok(h, l, tn, ratio_max)
    s_max = mas.empirical_support_spacing_max(tn, ratio_max)
    checks.append(chk("empirical_710", f"§710.4 min(h, l)/t ≤ {ratio_max} (nonbearing {loc})", span / tn, ratio_max,
                      "NSCP2015-710", "",
                      rf"\frac{{\min(h,\,l)}}{{t}} = \frac{{{span:.0f}}}{{{tn:.0f}}} = {span / tn:.1f} \le {ratio_max}"))
    inter["support_spacing_max_mm"] = s_max

    # §709.4.1.2–709.4.1.3
    mr = mas.partition_min_reinforcement(tn)
    checks.append(flag("isolation_709", "Isolate from the structure; joints take the design storey drift "
                       "(§709.4.1.2)", True, "NSCP2015-709", r"\text{detailing requirement}"))
    notes.append("§709.4.1.3 minimum steel applies in Zones 2 and 4 (hub reading — see vault note NSCP2015-709)")
    notes.append("§709.2: empirical design is part of the §706 route; the Zone 2/4 provisions still apply")

    design = {"vertical": {"bar_db_mm": mr["vertical"]["bar_db_mm"], "spacing_mm": mr["vertical"]["spacing_max_mm"],
                           "basis": "§709.4.1.3 minimum, within 400 mm of wall ends"},
              "horizontal": {"bar_db_mm": mr["horizontal"]["or_bar_db_mm"],
                             "spacing_mm": mr["horizontal"]["or_bar_spacing_max_mm"],
                             "or_joint_reinforcement": f"{mr['horizontal']['joint_wires_MW11']} × MW11 at ≤ 400 mm",
                             "basis": "§709.4.1.3 minimum, within 400 mm of top and bottom"},
              "stiffener_spacing_mm": None if emp_ok else s_max}

    oop = None
    if not emp_ok:
        notes.append("§710.4 ratio exceeded: reinforced ASD check spanning floor to soffit "
                     f"(or add stiffeners at ≤ {s_max:.0f} mm)")
        for db, s in BAR_CANDIDATES:
            gk = s if s in (400, 600, 800) else 800   # 1200/1000 mm grout spacing: 800 mm row (heavier, conservative)
            wk = mas.chb_wall_weight(p["unit_density_kN_m3"], gk, tn, int(p["plastered_faces"]))
            Fpk = elements.Fp(float(p["Ca"]), float(p["Ip"]), wk, ap, Rp, float(p["hx_m"]), float(p["hr_m"]))
            q = dict(method="ASD", support="simple", h_mm=h, t_nom_mm=tn, t_spec_mm=p["t_spec_mm"], grout="partial",
                     fm_MPa=p["fm_MPa"], fy_MPa=p["fy_MPa"], mortar=p["mortar"],
                     special_inspection=p["special_inspection"], zone=p["zone"], bar_db_mm=db, bar_s_mm=s,
                     wall_kPa=wk, wind_kPa=wind, seismic_kPa=Fpk, Ca=p["Ca"], Ip=p["Ip"],
                     face_shell_mm=p.get("face_shell_mm"))
            oop = wall_out_of_plane(q)
            core = [c for c in oop["checks"] if c["id"] in ("unity_asd", "fs_asd", "fv_asd", "slenderness_asd")]
            if all(c.get("ok") for c in core):
                design["vertical"] = {"bar_db_mm": db, "spacing_mm": s,
                                      "basis": "reinforced ASD out-of-plane check (§707.2) + §709.4.1.3"}
                design["stiffener_spacing_mm"] = None
                break
        else:
            design["vertical"]["basis"] = "no candidate bar/spacing passed — add stiffeners"
        checks += [c for c in oop["checks"] if c["id"] not in ("mortar_zone2", "mortar_zone4")]
    else:
        checks.append(flag("reinforced_oop", "Reinforced out-of-plane check not required (§710.4 ratio met)", True,
                           "NSCP2015-710", r"\text{empirical design governs}"))
    checks.append(flag("vertical_min_709", "Vertical bar ≥ 12 mm at ≤ 1.2 m", design["vertical"]["bar_db_mm"] >= 12
                       and design["vertical"]["spacing_mm"] <= 1200, "NSCP2015-709",
                       rf"\phi_b = {design['vertical']['bar_db_mm']}\ \text{{mm}} @ {design['vertical']['spacing_mm']}"
                       r" \le 1200\ \text{mm}"))
    s_ = summarize(checks)
    return {"calculator": "partition", "inputs": p, "intermediate": inter, "design": design,
            "oop": oop and {k: oop[k] for k in ("intermediate", "governing_ratio")},
            "checks": checks, "notes": notes,
            "basis": sorted({"NSCP2015-204-T204-2", "NSCP2015-208.9", "NSCP2015-710", "NSCP2015-709",
                             "NSCP2015-706.2", "NSCP2015-706.1.12"} | set(oop["basis"] if oop else [])), **s_}
