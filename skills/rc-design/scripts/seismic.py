"""
seismic.py -- SMF beam: Mpr, Ve, NSCP 418.6 detailing.

Basis (ACI 318-25M printed page | NSCP 2015 twin folio -- vault Internal Learning/01)
------------------------------------------------------------------------------------
* geometry: ln >= 4d; bw >= max(0.3h, 250); projection <= min(c2, 0.75 c1)
                                      18.6.2.1, p. 327 | 418.6.2, 4-113
  (318-25M prints 0.7 c1; the 14 May 2026 errata changes it to 0.75)
* >= 2 continuous bars top & bottom; As >= As,min (9.6.1.2, no 4/3 exemption);
  rho <= 0.025 (Gr 420) / 0.02 (Gr 550)  18.6.3.1, p. 328 | 418.6.3.1, 4-113
* Mn+ >= 0.5 Mn- at each joint face; Mn+/- >= 0.25 max joint-face Mn everywhere
                                      18.6.3.2, p. 328 | 418.6.3.2, 4-113
* lap splices: not within joints, not within 2h of a joint face  18.6.3.3, p. 328
* hoops over 2h from each column face; first hoop <= 50 mm; spacing <= least of
  d/4, 150 mm, 6 db (Gr 420) / 5 db (Gr 550) of the smallest primary bar
                                      18.6.4.1 / 18.6.4.4, p. 330-331 | 418.6.4, 4-114
* outside the hoop zone: seismic-hooked stirrups at <= d/2   18.6.4.5, p. 331
* supported-bar transverse spacing <= 350 mm  18.6.4.2, p. 330-331
* Mpr: 1.25 fy, phi = 1.0, joint-face properties INCLUDING A's  Notation p. 24;
  18.6.5.1 + Fig. R18.6.5, p. 331-333 | 418.6.5, 4-115.  Tension-only closed form
  understates Mpr 8-26 % (vault Software/12 D3) -- not used.
* Ve = (Mpr1 + Mpr2)/ln + wu ln/2, CLEAR span ln (Software/12 D4), both sway directions;
  wu = (1.2 + ev) D + fL L  (Fig. R18.6.5 prints (1.2 + 0.2 SDS) D + 1.0 L + 0.2 S;
  under NSCP enter ev = 0.5 Ca I per 208.5.1.1 -- folio not vault-verified)
* Vc = 0 in the hoop zone when Vpr >= 0.5 Ve AND Pu < Ag f'c / 20   18.6.5.2, p. 333
* joint depth parallel to beam bars >= 20 db / lam (Gr 420), 26 db (Gr 550)
                                      18.8.2.3, p. 340-341 | 418.8.2.3, 4-118

Not checked here: joint shear (use concretedesignpy joint_shear), development and hooks
in the joint (18.8.5), lap-splice lengths, column strong-column/weak-beam.
Units: kN, kN.m, m for spans, mm for sections.
"""

import math

from flexure import as_min, face_layers, section_capacity


def mpr(b, h, cover, dbs, fc, fy, n_t, db_t, n_c, db_c, dagg=None):
    """Probable moment strength (kN.m), 1.25 fy, phi = 1, with A's."""
    t = face_layers(n_t, db_t, b, h, cover, dbs, dagg)
    c = face_layers(n_c, db_c, b, h, cover, dbs, dagg) if n_c else ()
    r = section_capacity(b, h, fc, fy, t, c, fy_factor=1.25)
    return r["Mn"] if r["ok"] else 0.0, r


def capacity_shear(stations, geo, mat, span, grav, Pu_kN=0.0):
    """stations: {"I": {"top": (n, db), "bot": (n, db)}, "J": {...}}.

    Returns Mpr at both ends, Vpr for both sway directions, Ve per end and the
    18.6.5.2 Vc = 0 verdict.
    """
    b, h, cover, dbs = geo["b"], geo["h"], geo["cover"], geo["dbs"]
    fc, fy = mat["fc"], mat["fy"]
    dagg = geo.get("dagg")
    out, warn = {}, []
    for end in ("I", "J"):
        (nt, dt), (nb, dbb) = stations[end]["top"], stations[end]["bot"]
        neg, _ = mpr(b, h, cover, dbs, fc, fy, nt, dt, nb, dbb, dagg)   # top in tension
        pos, _ = mpr(b, h, cover, dbs, fc, fy, nb, dbb, nt, dt, dagg)   # bottom in tension
        out[f"Mpr_neg_{end}"], out[f"Mpr_pos_{end}"] = neg, pos
        if neg <= 0 or pos <= 0:
            warn.append(f"Mpr at {end} could not be solved -- capacity design is INVALID")
    ln = span["ln"]
    if span.get("ln_assumed"):
        warn.append("ln not derivable (column depths missing) -- centreline L used; "
                    "Vpr understated ~8-15 % for 500-700 mm columns (Software/12 D4)")
    vpr_a = (out["Mpr_neg_I"] + out["Mpr_pos_J"]) / ln
    vpr_b = (out["Mpr_pos_I"] + out["Mpr_neg_J"]) / ln
    vpr = max(vpr_a, vpr_b)
    wu = (1.2 + grav.get("ev", 0.0)) * grav.get("wD", 0.0) + grav.get("fL", 1.0) * grav.get("wL", 0.0)
    vg = grav.get("Vg_override") if grav.get("Vg_override") is not None else wu * ln / 2.0
    if grav.get("wD", 0.0) <= 0 and grav.get("Vg_override") is None:
        warn.append("no gravity load given for Ve -- Vg = 0 (unconservative)")
    ve = vpr + vg
    ag = b * h
    vc_zero = (vpr >= 0.5 * ve) and (Pu_kN * 1e3 < ag * fc / 20.0)
    out.update({"ln": ln, "Vpr_sway_A": vpr_a, "Vpr_sway_B": vpr_b, "Vpr": vpr,
                "wu": wu, "Vg": vg, "Ve": ve, "eq_fraction": vpr / ve if ve > 0 else 0.0,
                "Vc_zero_in_hinge": vc_zero, "warnings": warn})
    return out


def detailing_checks(geo, mat, span, stations, caps, d_by_station, col=None, lam=1.0):
    """418.6 / 18.6 checks on the final bars. caps[station][face] = check_face dict."""
    b, h = geo["b"], geo["h"]
    fc, fy = mat["fc"], mat["fy"]
    gr550 = fy > 420.0
    chk = []

    def add(cid, clause, page, ok, value, limit, note=""):
        chk.append({"id": cid, "clause": clause, "page": page,
                    "status": "OK" if ok else "FAIL", "value": value, "limit": limit, "note": note})

    d_min = min(d_by_station.values())
    add("smf_ln_4d", "18.6.2.1(a) | NSCP 418.6.2", "327 | 4-113",
        span["ln"] * 1000 >= 4 * d_min, round(span["ln"] * 1000), f">= 4d = {4 * d_min:.0f} mm")
    add("smf_bw", "18.6.2.1(b) | NSCP 418.6.2", "327 | 4-113",
        b >= max(0.3 * h, 250.0), b, f">= max(0.3h, 250) = {max(0.3 * h, 250):.0f} mm")
    if col and col.get("c1") and col.get("c2"):
        proj = max(0.0, (b - col["c2"]) / 2.0)
        lim = min(col["c2"], 0.75 * col["c1"])
        add("smf_projection", "18.6.2.1(c) + errata 2026", "327", proj <= lim, proj, f"<= {lim:.0f} mm")

    rho_max = 0.02 if gr550 else 0.025
    n_cont = {"top": min(s["top"][0] for s in stations.values()),
              "bot": min(s["bot"][0] for s in stations.values())}
    for face in ("top", "bot"):
        add(f"smf_2_continuous_{face}", "18.6.3.1 | NSCP 418.6.3.1", "328 | 4-113",
            n_cont[face] >= 2, n_cont[face], ">= 2 continuous bars",
            "assumes the least count along the span is continuous -- confirm on the drawing")
    for st, faces in caps.items():
        d = d_by_station[st]
        for face, r in faces.items():
            rho = r["As_prov"] / (b * d)
            add(f"smf_rho_{st}_{face}", "18.6.3.1", "328", rho <= rho_max, round(rho, 5), f"<= {rho_max}")
            amin = as_min(fc, fy, b, d)
            add(f"smf_asmin_{st}_{face}", "18.6.3.1 -> 9.6.1.2 (no 4/3 exemption)", "328 / 149",
                r["As_prov"] >= amin, round(r["As_prov"]), f">= {amin:.0f} mm2")
    mn = {st: {f: caps[st][f]["Mn"] for f in caps[st]} for st in caps}
    for end in ("I", "J"):
        if end in mn:
            add(f"smf_half_rule_{end}", "18.6.3.2 | NSCP 418.6.3.2", "328 | 4-113",
                mn[end]["bot"] >= 0.5 * mn[end]["top"], round(mn[end]["bot"], 1),
                f">= 0.5 Mn- = {0.5 * mn[end]['top']:.1f} kN.m")
    mmax = max(max(mn[e].values()) for e in ("I", "J") if e in mn)
    for st in mn:
        for face, v in mn[st].items():
            add(f"smf_quarter_rule_{st}_{face}", "18.6.3.2", "328", v >= 0.25 * mmax,
                round(v, 1), f">= 0.25 x {mmax:.1f} kN.m")
    if col:
        db_max = max(max(s["top"][1], s["bot"][1]) for s in stations.values())
        need = (26.0 if gr550 else 20.0 / lam) * db_max
        for end, key in (("I", "hc_i"), ("J", "hc_j")):
            if col.get(key):
                add(f"joint_depth_{end}", "18.8.2.3 | NSCP 418.8.2.3", "340-341 | 4-118",
                    col[key] >= need, col[key], f">= {need:.0f} mm for D{db_max:g}",
                    "bar size sets the column dimension")
    return chk


def hoop_limits(d, h, db_smallest, fy):
    """Hinge-zone hoop spacing limit, hinge length, outside-zone limit (mm)."""
    k = 5.0 if fy > 420.0 else 6.0
    return {"s_hinge_max": min(d / 4.0, 150.0, k * db_smallest), "hinge_length": 2.0 * h,
            "first_hoop_max": 50.0, "s_outside_max": d / 2.0, "leg_spacing_max": 350.0}
