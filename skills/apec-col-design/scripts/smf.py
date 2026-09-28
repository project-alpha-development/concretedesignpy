"""
smf.py -- columns of special moment frames, NSCP 2015 Section 418.7 (= ACI 318M-14 18.7).

Basis: NSCP folios read VISUALLY 2026-09-28 (4-115, 4-116, 4-117) | ACI 318-25M printed
----------------------------------------------------------------------------------------
* 418.7.2.1 least dimension >= 300 mm; least/perpendicular >= 0.4     4-115 | 18.7.2.1, 334
* 418.7.3.2 SUM Mnc >= (6/5) SUM Mnb, Mnc at the factored axial force (direction of the
  lateral forces) giving the LOWEST Mnc; both sway senses              4-115 | 18.7.3.2, 335
  418.7.3.1 has NO roof exemption in NSCP 2015 (ACI 318-19+ 18.7.3.1 exempts a
  discontinuous-above column with Pu < Ag f'c/10) -- reported as a WARN option only.
  418.7.3.3: if not satisfied, the column's lateral strength and stiffness are ignored
  and it must conform to 418.14.
* 418.7.4.1 0.01 Ag <= Ast <= 0.06 Ag                                  4-115 | 18.7.4.1, 336
* 418.7.4.2 circular hoops: >= 6 bars                                 4-115 | 18.7.4.2, 336
* 418.7.4.3 lap splices only in the centre half, tension splices, confined per
  418.7.5.2-.3                                                         4-115 | 18.7.4.4, 336
  (318-19+ 18.7.4.3 bond-splitting rule 1.25 ld <= lu/2 or Ktr >= 1.2 db is not NSCP)
* 418.7.5.1 lo >= max(depth at joint face, lu/6, 450 mm)              4-116 | 18.7.5.1, 336
* 418.7.5.2(e) hx <= 350 mm; (f) Pu > 0.3 Ag f'c or f'c > 70 MPa: every bar supported by
  a hoop corner or seismic hook and hx <= 200 mm, Pu = largest compression of the
  combinations including E                                             4-116 | 18.7.5.2, 337
* 418.7.5.3 s <= min(least dimension/4, 6 db, so), so = 100 + (350 - hx)/3,
  100 <= so <= 150                                                     4-116 | 18.7.5.3, 338
  (318-19+ adds 5 db for Grade 550 -- reported as a WARN when fy > 420)
* Table 418.7.5.4 Ash/(s bc) >= max[0.3(Ag/Ach - 1) f'c/fyt, 0.09 f'c/fyt,
  and 0.2 kf kn Pu/(fyt Ach) when Pu > 0.3 Ag f'c or f'c > 70]; spirals rho_s >= max[
  0.45(Ag/Ach - 1) f'c/fyt, 0.12 f'c/fyt, 0.35 kf Pu/(fyt Ach)]        4-117 | Table 18.7.5.4, 338
  kf = f'c/175 + 0.6 >= 1.0; kn = nl/(nl - 2)                          4-116 | Eq. 18.7.5.4a/b, 338
  NSCP prints 0.35 kf kn in row (f); kn is defined only for rectilinear hoops, so the
  ACI form (no kn) is used for spirals and the variance is flagged.
  Both directions: legs parallel to x confine across bc_y and vice versa (R18.7.5.4, 338).
  fyt in Table 418.7.5.4 <= 690 MPa (R18.7.5.4, 338).
* 418.7.5.5 beyond lo: s <= min(6 db, 150)                             4-116 | 18.7.5.5, 339
* 418.7.6.1.1 Ve from Mpr at both ends over the RANGE of factored axial forces; need not
  exceed the shear from Mpr of the beams framing into the joints; >= analysis Vu
                                                                       4-117 | 18.7.6.1.1, 339
  Beam moments are split to the columns above/below by DF (0.5 by default = W&M 7th
  Eq. (19-30), printed 1069; Moehle printed 566 warns the split is unreliable in the lower
  storeys -- the column-Mpr bound is the robust one).
* 418.7.6.2.1 Vc = 0 over lo when the earthquake-induced shear >= half the maximum
  required shear AND Pu (incl. E) < Ag f'c/20                          4-117 | 18.7.6.2.1, 340
* 421.2.4.1 phi = 0.60 if Vn < the shear at nominal moment strength (max over the axial
  loads of the E combinations)                                         4-141 | 21.2.4.1, 435
* Mpr: 1.25 fy, phi = 1.0 (ACI 318-25M 2.2 notation; W&M 7th printed 1069, Eq. (19-29))
* NIST GCR 8-917-1 (printed 15-17): keep Pu below the balanced point; >= 3 hoop/crosstie
  legs per face -- GUIDANCE, reported as WARN, never FAIL.
"""

import math


def kf(fc):
    return max(fc / 175.0 + 0.6, 1.0)


def kn(nl):
    return nl / (nl - 2.0) if nl > 2 else 2.0


def so_limit(hx):
    return min(max(100.0 + (350.0 - hx) / 3.0, 100.0), 150.0)


def lo_length(sec, lu):
    return max(sec["dmax"], lu / 6.0, 450.0)


def hx_rule(Pu_E_max_kN, Ag, fc):
    """(hx limit mm, every bar supported?) -- 418.7.5.2(e)/(f)."""
    trig = (Pu_E_max_kN * 1e3 > 0.3 * Ag * fc) or fc > 70.0
    return (200.0, True) if trig else (350.0, False)


def s_max_lo(sec, db_min, hx):
    parts = {"least_dim/4": sec["dmin"] / 4.0, "6db": 6.0 * db_min, "so": so_limit(hx)}
    return min(parts.values()), parts


def s_max_mid(db_min):
    return min(6.0 * db_min, 150.0)


def confinement(sec, fc, fyt, Pu_max_kN, nl=None):
    """Required confinement.  Rect: Ash/(s bc) ratio; circle: rho_s.  Pu_max = the largest
    factored compression (all combinations -- conservative; W&M 7th Ex 19-2 uses the
    gravity combination's 918 kips)."""
    fyt_c = min(fyt, 690.0)
    Ag, Ach = sec["Ag"], sec["Ach"]
    trig = (Pu_max_kN * 1e3 > 0.3 * Ag * fc) or fc > 70.0
    out = {"triggered_c_f": trig, "kf": kf(fc), "fyt_used": fyt_c}
    if sec["shape"] == "rect":
        a = 0.3 * (Ag / Ach - 1.0) * fc / fyt_c
        b = 0.09 * fc / fyt_c
        k_n = kn(nl or 4)
        c = 0.2 * kf(fc) * k_n * Pu_max_kN * 1e3 / (fyt_c * Ach) if trig else 0.0
        out.update({"kn": k_n, "nl": nl, "a": a, "b": b, "c": c,
                    "ratio": max(a, b, c), "governs": max((a, "a"), (b, "b"), (c, "c"))[1]})
    else:
        d = 0.45 * (Ag / Ach - 1.0) * fc / fyt_c
        e = 0.12 * fc / fyt_c
        f = 0.35 * kf(fc) * Pu_max_kN * 1e3 / (fyt_c * Ach) if trig else 0.0
        out.update({"d": d, "e": e, "f": f, "rho_s": max(d, e, f),
                    "governs": max((d, "d"), (e, "e"), (f, "f"))[1],
                    "note": "NSCP Table 418.7.5.4 row (f) prints 0.35 kf kn; kn is defined for "
                            "rectilinear hoops only, so the ACI 318-25M form (no kn) is used"})
    return out


def rho_s_provided(Asp, dsp, s, Dc):
    """Volumetric ratio of a spiral / circular hoop: volume of one turn over the core
    volume out-to-out (conservative: steel measured on its centreline)."""
    return 4.0 * Asp * (Dc - dsp) / (s * Dc * Dc)


def design_shear(col, axis, lu, P_E, Vu_analysis, V_E_share, joints, P_all_min):
    """Capacity-design shear for shear ALONG `axis`-direction's companion moment.

    axis: 'x' -> moments about x (Mx) -> shear along y;  'y' -> My -> shear along x.
    P_E: (Pmin, Pmax) of the combinations including E (kN).  Returns a dict in kN, kN.m.
    joints: {"top": {"Mpr_b": .., "DF": ..} | None, "bottom": {...} | None} for this axis.
    """
    Pmin, Pmax = P_E
    Mpr, P_at = col.moment_extreme(axis, Pmin * 1e3, Pmax * 1e3, fyf=1.25, kind="max")
    Mn, Pn_at = col.moment_extreme(axis, Pmin * 1e3, Pmax * 1e3, fyf=1.0, kind="max")
    Mpr, Mn = Mpr / 1e6, Mn / 1e6
    ends, notes = {}, []
    for end in ("top", "bottom"):
        j = (joints or {}).get(end) or {}
        mprb = j.get("Mpr_b")
        if mprb is not None:
            mprb = max(mprb) if isinstance(mprb, (list, tuple)) else float(mprb)
            df = float(j.get("DF", 0.5))
            m_beam = df * mprb
            ends[end] = {"Mpr_col": Mpr, "beam_limit": m_beam, "DF": df, "M_used": min(Mpr, m_beam),
                         "governed_by": "beams" if m_beam < Mpr else "column Mpr"}
        else:
            ends[end] = {"Mpr_col": Mpr, "beam_limit": None, "M_used": Mpr,
                         "governed_by": "column Mpr (no beam data at this end)"}
    lu_m = lu / 1000.0
    Ve_col = 2.0 * Mpr / lu_m
    Ve_cap = (ends["top"]["M_used"] + ends["bottom"]["M_used"]) / lu_m
    Ve = max(Vu_analysis, Ve_cap)
    if Ve_cap < Ve_col:
        notes.append("Ve limited by beam Mpr (418.7.6.1.1); Moehle printed 566: the beam-moment "
                     "split above/below a joint is indeterminate -- the column-Mpr shear "
                     f"{Ve_col:.1f} kN is the robust bound")
    V_eq = Ve_cap if Ve_cap >= Vu_analysis else V_E_share
    Ag, fc = col.Ag, col.fc
    cond_a = V_eq >= 0.5 * Ve - 1e-9
    cond_b = Pmin * 1e3 < Ag * fc / 20.0
    return {"Mpr": Mpr, "P_at_Mpr": P_at / 1e3, "Mn_max": Mn, "P_at_Mn": Pn_at / 1e3,
            "ends": ends, "lu": lu, "Ve_col": Ve_col, "Ve_cap": Ve_cap, "Vu_analysis": Vu_analysis,
            "Ve": Ve, "V_at_Mn": 2.0 * Mn / lu_m, "V_eq": V_eq, "vc_zero_a": cond_a,
            "vc_zero_b": cond_b, "vc_zero": cond_a and cond_b, "P_E": [Pmin, Pmax],
            "P_all_min": P_all_min, "notes": notes}


def scwb(col, axis, P_E, joint, P_other=None, Mnc_other=None, has_other=True):
    """418.7.3.2 at one joint for bending about `axis`.  Returns ratios for both sways.
    joint: {"Mnb": [sway+, sway-] | value}.  Mnc of this column: least over the E range."""
    mnb = joint.get("Mnb")
    if mnb is None:
        return None
    mnb = list(mnb) if isinstance(mnb, (list, tuple)) else [float(mnb), float(mnb)]
    Mnc_this, P_this = col.moment_extreme(axis, P_E[0] * 1e3, P_E[1] * 1e3, fyf=1.0, kind="min")
    Mnc_this /= 1e6
    other, src = 0.0, "none (discontinuous above -- 418.7.3.1)"
    if has_other:
        if Mnc_other is not None:
            other, src = float(Mnc_other), "given"
        elif P_other:
            m, _ = col.moment_extreme(axis, min(P_other) * 1e3, max(P_other) * 1e3, fyf=1.0, kind="min")
            other, src = m / 1e6, "same section at the given axial range"
        else:
            other, src = Mnc_this, "ASSUMED equal to this column (no data for the other column)"
    sum_c = Mnc_this + other
    rows = []
    for k, v in enumerate(mnb):
        rows.append({"sway": "+" if k == 0 else "-", "SumMnb": v, "SumMnc": sum_c,
                     "ratio": sum_c / v if v > 0 else math.inf, "ok": sum_c >= 1.2 * v - 1e-9})
    return {"Mnc_this": Mnc_this, "P_this": P_this / 1e3, "Mnc_other": other, "other_source": src,
            "rows": rows, "ok": all(r["ok"] for r in rows)}
