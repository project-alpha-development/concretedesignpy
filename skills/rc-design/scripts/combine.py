"""
combine.py -- merge torsion steel into flexure and shear steel, then pick stirrups.

Basis (ACI 318-25M printed page)
--------------------------------
* torsion steel is ADDED to that for Vu, Mu, Pu ........... 9.5.4.3, p. 147
* Al around the perimeter of the closed stirrup, <= 300 mm apart, a bar in every
  corner, db >= max(0.042 s, 10 mm) ........................ 9.7.5.1-9.7.5.2, p. 158
  -> Al is split in proportion to the stirrup-centreline perimeter: top and bottom
     each x0/ph, each side y0/ph. The compression-zone reduction permitted by 318 is
     NOT taken (conservative).
* (Av + 2At)/s >= max(0.062 sqrt(f'c) bw/fyt, 0.35 bw/fyt) .. 9.6.4.2, p. 152
* per outer leg: Av/(n s) + At/s .......................... Eq. (22.7.6.1a) is per leg
* closed stirrups / hoops where torsion is designed ........ 9.7.6.3.1, p. 160
* spacing: the least of every s_max supplied by shear.py, torsion.py, seismic.py.

Rounding (spacing DOWN to the APEC increment, not below the practical minimum) is office
practice, not code -- references/apec_standards.md.
"""

import math


def split_al(al, x0, y0, ph):
    top = al * x0 / ph
    side_each = al * y0 / ph
    return {"top": top, "bot": top, "side_each": side_each}


def side_bars(y0, al_side_each, s_stirrup, bar_sizes):
    """Intermediate side-face bars so vertical spacing <= 300 mm (9.7.5.1)."""
    n_gaps = max(1, math.ceil(y0 / 300.0))
    n_int = n_gaps - 1
    if al_side_each <= 0:
        return {"n_per_face": 0, "db": None, "note": "no torsion Al on the sides"}
    db_min = max(0.042 * s_stirrup, 10.0)
    if n_int == 0:
        return {"n_per_face": 0, "db": None,
                "note": f"side share {al_side_each:.0f} mm2/face carried by the corner bars "
                        "(add it to top/bottom)", "carry_to_corners": al_side_each}
    need_each = al_side_each / n_int
    for db in bar_sizes:
        if db >= db_min and math.pi / 4 * db * db >= need_each:
            return {"n_per_face": n_int, "db": db, "As_each_req": need_each}
    return {"n_per_face": n_int, "db": None, "note": "no listed bar big enough -- add a row"}


def pick_stirrups(av_s, at_s, av_s_min, s_max, n_legs, stirrup_sizes, increment, s_min,
                  legs_max=6):
    """Smallest stirrup size, then more legs, whose rounded spacing is >= s_min.

    av_s: all-legs shear demand (mm2/mm); at_s: per-leg torsion demand.
    """
    tried = []
    legs = n_legs
    while legs <= legs_max:
        for db in stirrup_sizes:
            a_leg = math.pi / 4.0 * db * db
            s_need = []
            if av_s + 2 * at_s > 0:
                s_need.append(legs * a_leg / (av_s + 2.0 * at_s))
            if av_s / legs + at_s > 0:
                s_need.append(a_leg / (av_s / legs + at_s))
            s_need.append(legs * a_leg / av_s_min if av_s_min > 0 else math.inf)
            s_raw = min(s_need + [s_max])
            s = math.floor(s_raw / increment + 1e-9) * increment
            tried.append((legs, db, s))
            if s >= s_min:
                return {"legs": legs, "db": db, "s": s, "s_raw": s_raw, "s_max": s_max,
                        "Av_s_prov": legs * a_leg / s, "Av_s_req_total": max(av_s + 2 * at_s, av_s_min),
                        "status": "OK"}
        legs += 2
    return {"status": "FAIL", "tried": tried,
            "reason": f"no stirrup up to {legs_max} legs x D{max(stirrup_sizes):g} reaches s >= {s_min} mm"}
