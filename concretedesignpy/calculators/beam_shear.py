# MIT License
# Copyright (c) Albert Pamonag Engineering Consultancy

"""
Beam Shear and Torsion Calculator
==================================

Computes concrete and steel shear strength, required stirrup spacing, and
combined shear + torsion design. ``shear_torsion_design`` is the package's
single implementation of Section 22.7.

Governing edition
-----------------
**NSCP 2015 Sections 422.5 and 422.7** (equivalent to **ACI 318M-14**),
the governing Philippine code. These modules previously claimed
ACI 318-19; they never implemented it.

The Vc law here is the 318-14 one, ``Vc = lam sqrt(f'c) bw d / 6``.
ACI 318-19/-25 Table 22.5.5.1 restructured it: for ``Av >= Av,min`` the
coefficient is numerically the same 0.17, but for ``Av < Av,min`` it adds
a ``rho_w^(1/3)`` term and the size-effect factor
``lam_s = sqrt(2/(1 + d/250)) <= 1`` (Section 22.5.5.1.3). For a 900 mm
beam without minimum stirrups that is ``lam_s = 0.66``. There is no
``lam_s`` here, and there should not be under NSCP 2015.

What these functions do NOT check
---------------------------------
Deep-beam provisions (Section 9.9), shear friction, shear at
discontinuities, torsional compatibility redistribution (Section
22.7.3), and hollow-section torsion -- ``shear_torsion_design`` uses the
solid-section rows of Tables 22.7.4.1 and 22.7.5.1 only. Longitudinal
torsion steel is returned as a required area, not distributed; Section
9.7.5.1 caps its spacing at 300 mm, so a deep beam needs more than the
four corner bars.
"""

import math

from concretedesignpy.clause import clause


@clause("NSCP2015-422.5.5.1", "NSCP2015-422.5.6")
def compute_concrete_shear_strength(
    fc, b, d, lamda=1.0, vc_type="simple",
    vu=None, mu=None, nu=None, rho_w=None,
    h=None, db=None, ds=None, cover=None, n_bars=None,
):
    """
    Compute concrete shear strength Vc.

    Parameters
    ----------
    fc : float
        Concrete compressive strength (MPa).
    b : float
        Beam width (mm).
    d : float
        Effective depth (mm).
    lamda : float
        Lightweight concrete factor (1.0 for normal weight).
    vc_type : str
        One of: 'simple', 'detailed', 'axial_compression',
        'detailed_axial_compression', 'axial_tension'.
    vu, mu, nu : float or None
        Factored shear (N), moment (N-mm), axial force (N).
    rho_w : float or None
        Longitudinal reinforcement ratio. If None, computed from inputs.
    h, db, ds, cover, n_bars : float or None
        Section geometry for computing Ag and rho_w when needed.

    Returns
    -------
    dict
        Keys: vc (N), vc_kn (kN), type
    """
    if fc <= 0 or b <= 0 or d <= 0:
        raise ValueError("fc, b, d must all be positive.")

    # Compute Ag and rho_w if not given
    if h is None:
        h = d + (db / 2 if db else 0) + (ds if ds else 0) + (cover if cover else 40)
    ag = h * b

    if rho_w is None and n_bars and db:
        as_bar = n_bars * math.pi * (db / 2) ** 2
        rho_w = as_bar / (b * d)

    if vc_type == "simple":
        vc = (1.0 / 6.0) * lamda * math.sqrt(fc) * b * d

    elif vc_type == "detailed":
        if vu is None or mu is None:
            raise ValueError("vu and mu are required for 'detailed' type.")
        if rho_w is None:
            raise ValueError("rho_w is required for 'detailed' type.")
        ratio = min(vu * d / mu, 1.0) if mu != 0 else 1.0
        vc1 = (0.16 * lamda * math.sqrt(fc) + 17 * rho_w * ratio) * b * d
        vc2 = 0.29 * lamda * math.sqrt(fc) * b * d
        vc = min(vc1, vc2)

    elif vc_type == "axial_compression":
        if nu is None:
            raise ValueError("nu is required for 'axial_compression' type.")
        vc = (1.0 / 6.0) * (1 + nu / (14 * ag)) * lamda * math.sqrt(fc) * b * d

    elif vc_type == "detailed_axial_compression":
        if nu is None or vu is None or mu is None:
            raise ValueError("nu, vu, mu required for 'detailed_axial_compression'.")
        if rho_w is None:
            raise ValueError("rho_w is required.")
        mm = mu - nu * ((4 * h - d) / 8)
        vc2 = 0.29 * lamda * math.sqrt(fc) * b * d * math.sqrt(1 + 0.29 * nu / ag)
        if mm <= 0:
            vc = vc2
        else:
            vc1 = (0.16 * lamda * math.sqrt(fc) + 17 * rho_w * (vu * d / mm)) * b * d
            vc = min(vc1, vc2)

    elif vc_type == "axial_tension":
        if nu is None:
            raise ValueError("nu is required for 'axial_tension' type.")
        vc = (1.0 / 6.0) * (1 + 0.29 * nu / ag) * lamda * math.sqrt(fc) * b * d
        vc = max(vc, 0)

    else:
        raise ValueError(f"Unknown vc_type: {vc_type}")

    return {"vc": round(vc, 2), "vc_kn": round(vc / 1000, 2), "type": vc_type}


@clause("NSCP2015-422.5.10")
def compute_steel_shear_strength(av, fyt, d, s):
    """
    Compute steel shear reinforcement strength Vs = Av * fyt * d / s.

    Parameters
    ----------
    av : float
        Total area of shear reinforcement (mm^2).
    fyt : float
        Yield strength of transverse reinforcement (MPa).
    d : float
        Effective depth (mm).
    s : float
        Stirrup spacing (mm).

    Returns
    -------
    dict
        Keys: vs (N), vs_kn (kN)
    """
    if s <= 0:
        raise ValueError("Stirrup spacing must be positive.")
    vs = av * fyt * d / s
    return {"vs": round(vs, 2), "vs_kn": round(vs / 1000, 2)}


@clause("NSCP2015-422.5.1", "NSCP2015-409.6.3", "NSCP2015-409.7.6")
def compute_shear_spacing(fc, b, d, fyt, vu_required, phi, av,
                          lamda=1.0, vc_type="simple", **kwargs):
    """
    Compute required stirrup spacing given a required Vu.

    Parameters
    ----------
    fc, b, d, fyt : float
        Material and section properties.
    vu_required : float
        Required ultimate shear (N).
    phi : float
        Strength reduction factor for shear.
    av : float
        Total area of shear reinforcement (mm^2).
    lamda : float
        Lightweight concrete factor.
    vc_type : str
        Type of Vc calculation.

    Returns
    -------
    dict
        Keys: spacing (mm, None when the section is UNSAFE), status,
        vs_required (N), vs_max (N), smax (mm), s_avmin (mm), av_min_per_s,
        vc_kn.

    Notes
    -----
    ``spacing`` is None, and ``status`` is an explicit UNSAFE string, when
    Vs exceeds the Section 22.5.1.2 limit. A section the Code forbids must
    not come back carrying a spacing that looks usable.
    """
    vc_result = compute_concrete_shear_strength(fc, b, d, lamda, vc_type, **kwargs)
    vc = vc_result["vc"]
    vs_required = (vu_required / phi) - vc
    # Section 9.7.6.2.2: the s_max halving trigger.
    vs_limit = (1.0 / 3.0) * math.sqrt(fc) * b * d
    # Section 22.5.1.2: Vu <= phi (Vc + 0.66 sqrt(fc') bw d). The section
    # itself is inadequate above this; no stirrup spacing rescues it.
    vs_max = (2.0 / 3.0) * math.sqrt(fc) * b * d

    # Table 9.6.3.4(a) and (b). Applies on BOTH branches: the strength
    # requirement can be satisfied by a spacing wider than Av,min allows,
    # and used to be returned unchecked whenever Vu > phi*Vc.
    avmin_per_s = max(0.062 * math.sqrt(fc) * b / fyt, 0.35 * b / fyt)
    s_avmin = av / avmin_per_s

    if vs_required <= vs_limit:
        smax = min(d / 2.0, 600.0)
    else:
        smax = min(d / 4.0, 300.0)

    result = {
        "vs_required": round(vs_required, 2),
        "vs_required_kn": round(vs_required / 1000, 2),
        "vs_max": round(vs_max, 2),
        "vs_max_kn": round(vs_max / 1000, 2),
        "smax": round(smax, 2),
        "s_avmin": round(s_avmin, 2),
        "av_min_per_s": round(avmin_per_s, 4),
        "vc_kn": vc_result["vc_kn"],
    }

    if vs_required > vs_max:
        result["spacing"] = None
        result["status"] = (
            "UNSAFE - Vs required ({:.1f} kN) exceeds the 22.5.1.2 limit "
            "(2/3)sqrt(f'c)bw*d = {:.1f} kN. Enlarge the section.".format(
                vs_required / 1000, vs_max / 1000)
        )
        return result

    if vu_required > phi * vc:
        strength_s = av * fyt * d / vs_required if vs_required > 0 else 600.0
    else:
        strength_s = 600.0

    result["spacing"] = round(min(strength_s, s_avmin, smax), 2)
    result["status"] = "OK"
    return result


@clause("NSCP2015-422.5.6", "NSCP2015-409.7.6", "NSCP2015-422.7.4", "NSCP2015-422.7.6", "NSCP2015-422.7.7", "NSCP2015-409.6.4")
def shear_torsion_design(fc, fyv, fy, phi, bw, h, cc, c, d,
                         vu, tu, nu, s_chosen, n_legs, db_stirrup, db_long):
    """
    Combined shear and torsion design per NSCP 2015 Sections 422.5 and
    422.7 (equivalent to ACI 318M-14).

    Follows the computation flow from EA Spreadsheet Suite. This is the
    package's only implementation of Section 22.7.

    Parameters
    ----------
    fc : float       Concrete compressive strength (MPa).
    fyv : float      Yield strength of stirrups (MPa).
    fy : float       Yield strength of longitudinal rft (MPa).
    phi : float      Strength reduction factor for shear/torsion.
    bw : float       Width of beam (mm).
    h : float        Total height of beam (mm).
    cc : float       Clear cover to links (mm).
    c : float        Cover to centroid of reinforcement (mm).
    d : float        Effective depth (mm).
    vu : float       Factored shear force (kN).
    tu : float       Factored torsional moment (kN.m).
    nu : float       Factored axial force (kN), positive = compression.
    s_chosen : float Chosen stirrup spacing (mm).
    n_legs : int     Total number of stirrup legs.
    db_stirrup : float  Stirrup bar diameter (mm).
    db_long : float  Longitudinal bar diameter for torsion (mm).

    Returns
    -------
    dict with all intermediate values and step references.
    """
    steps = []
    ag = bw * h  # gross area mm^2

    # ── 1. Material checks ──
    fc_check = "OK" if fc <= 70 else "fc' > 70 MPa limit"
    fyv_check = "OK" if fyv <= 420 else "fyv > 420 MPa limit"
    steps.append({
        "title": "Material Properties",
        "items": [
            {"label": "f'c", "value": fc, "unit": "MPa", "check": fc_check,
             "ref": "ACI 318M-14 Cl. 22.5.3.1"},
            {"label": "fyv", "value": fyv, "unit": "MPa", "check": fyv_check,
             "ref": "ACI 318M-14 Cl. 20.2.2.4"},
            {"label": "fy", "value": fy, "unit": "MPa"},
            {"label": "\u03c6", "value": phi, "ref": "ACI 318M-14 Cl. 21.2.1(b)"},
        ],
    })

    # ── 2. Section dimensions ──
    steps.append({
        "title": "Section Dimensions",
        "items": [
            {"label": "bw", "value": bw, "unit": "mm"},
            {"label": "h", "value": h, "unit": "mm"},
            {"label": "Cc", "value": cc, "unit": "mm"},
            {"label": "c", "value": c, "unit": "mm"},
            {"label": "d", "value": d, "unit": "mm",
             "formula": "h - c = {} - {} = {}".format(h, c, d)},
        ],
    })

    # ── 3. Concrete shear strength Vc ──
    # ACI 318M-14 Cl. 22.5.5.1 with axial load modification
    if nu > 0:
        # Compression: Cl. 22.5.6.1, W&M Eq. (6-13aM) printed 282.
        # There used to be a second branch here,
        #     0.3 sqrt(fc) bw d (1 + 0.3 Nu/Ag),
        # taken as an upper bound and selected with min(). It is not an
        # expression `reference/` supports, and it was provably inert:
        # its ratio to the branch below is 1.8 (1 + 0.3q)/(1 + q/14) with
        # q = Nu/Ag, which equals 1.8 at Nu = 0 and only grows, because
        # 0.3 > 1/14. min() therefore always returned the first branch,
        # for every Nu >= 0. Deleted rather than replaced.
        vc = (1 + nu * 1000 / (14 * ag)) * (math.sqrt(fc) / 6) * bw * d / 1000
        vc_note = "with axial compression"
    elif nu < 0:
        # Tension: Cl. 22.5.7.1
        vc = max(0, (1 + 0.29 * nu * 1000 / ag) * (math.sqrt(fc) / 6) * bw * d / 1000)
        vc_note = "with axial tension"
    else:
        vc = (math.sqrt(fc) / 6) * bw * d / 1000
        vc_note = "no axial load"

    steps.append({
        "title": "Concrete Shear Strength",
        "items": [
            {"label": "Vc", "value": round(vc, 2), "unit": "kN",
             "note": vc_note,
             "ref": "ACI 318M-14 Cl. 22.5.5.1\u20137"},
        ],
    })

    # ── 4. Required stirrup shear strength Vs ──
    vs_max = (2.0 / 3.0) * math.sqrt(fc) * bw * d / 1000
    vs_req_raw = (vu - phi * vc) / phi

    if vs_req_raw <= 0:
        vs = 0
        shear_status = "Provide Min. Rft"
    elif vs_req_raw > vs_max:
        vs = vs_req_raw
        shear_status = "UNSAFE - Vs exceeds limit"
    else:
        vs = vs_req_raw
        shear_status = "SAFE"

    # Check: Vu <= phi*(Vc + 0.66*sqrt(fc')*bw*d), Cl. 22.5.1.2.
    # Note this is the SAME condition as vs_req_raw > vs_max above:
    #   vs_req_raw > vs_max  <=>  vu/phi - vc > vs_max  <=>  vu > vu_max.
    # shear_status was computed and then thrown away, overall_check being
    # returned under that key, so "UNSAFE - Vs exceeds limit" could never
    # reach a caller. It is now returned as vs_status. No verdict changes:
    # the two agree by construction.
    vu_max = phi * (vc + (2.0 / 3.0) * math.sqrt(fc) * bw * d / 1000)
    overall_check = "SAFE" if vu <= vu_max else "UNSAFE"

    # Av/s required for shear
    av_s_shear = (vu * 1000 - phi * vc * 1000) / (phi * fyv * d) if vs > 0 else 0

    steps.append({
        "title": "Transverse Rft for Shear",
        "items": [
            {"label": "Vs,req", "value": round(max(vs, 0), 2), "unit": "kN",
             "formula": "(Vu - \u03c6Vc)/\u03c6 = ({} - {}x{})/{} = {}".format(
                 vu, phi, round(vc, 2), phi, round(vs_req_raw, 2)),
             "ref": "ACI 318M-14 Cl. 22.5.10.5.3"},
            {"label": "Vs,max", "value": round(vs_max, 2), "unit": "kN",
             "formula": "\u03c6(2/3)\u221afc'bwd",
             "ref": "ACI 318M-14 Cl. 22.5.1.2"},
            {"label": "Check", "value": overall_check,
             "formula": "Vu \u2264 \u03c6Vc + \u03c6(0.66\u221afc')bwd = {} kN".format(
                 round(vu_max, 2)),
             "ref": "ACI 318M-14 Cl. 22.5.1.2"},
            {"label": "Av/s (shear)", "value": round(av_s_shear, 4), "unit": "mm\u00b2/mm",
             "ref": "ACI 318M-14 R22.5.10.5"},
        ],
    })

    # ── 5. Torsion geometry ──
    # Assume stirrup diameter for Aoh calculation
    aoh = (h - 2 * cc - db_stirrup) * (bw - 2 * cc - db_stirrup)
    ph = 2 * (h - 2 * cc - db_stirrup) + 2 * (bw - 2 * cc - db_stirrup)

    steps.append({
        "title": "Torsion Geometry",
        "items": [
            {"label": "Aoh", "value": round(aoh, 0), "unit": "mm\u00b2",
             "ref": "ACI 318M-14 R22.7.6.1.1"},
            {"label": "Ph", "value": round(ph, 0), "unit": "mm"},
        ],
    })

    # ── 6. Torsional thresholds ──
    # Table 22.7.4.1(a), printed 463, and Table 22.7.5.1, printed 464, both
    # read at the page. Solid cross section, nonprestressed:
    #   Tth = 0.083 lam sqrt(fc') (Acp^2/pcp)
    #   Tcr = 0.33  lam sqrt(fc') (Acp^2/pcp)
    # and rows (c) of both tables multiply by
    #   sqrt(1 + Nu/(0.33 Ag lam sqrt(fc')))
    # for a member subject to axial force, Nu positive for compression and
    # negative for tension. That factor was omitted entirely -- Nu is an
    # argument of this function and was never used for torsion. Omitting it
    # is conservative under compression and UNCONSERVATIVE under net
    # tension, which is the case that matters.
    #
    # The coefficients were also 1/12 and 1/3 (0.0833, 0.3333) against the
    # printed 0.083 and 0.33, i.e. +0.4% on Tth and +1.0% on Tcr, both in
    # the direction of neglecting torsion. Now the printed values.
    lam = 1.0
    acp = bw * h
    pcp = 2 * (bw + h)
    axial_ratio = 1.0 + nu * 1000.0 / (0.33 * ag * lam * math.sqrt(fc))
    # Net tension beyond 0.33 Ag lam sqrt(fc') drives the radicand negative;
    # clamp at zero so the thresholds vanish and torsion is always designed
    # for, rather than taking the square root of a negative number.
    axial_factor = math.sqrt(max(0.0, axial_ratio))
    tcr = phi * 0.33 * lam * math.sqrt(fc) * acp ** 2 / pcp * axial_factor / 1e6
    tth = phi * 0.083 * lam * math.sqrt(fc) * acp ** 2 / pcp * axial_factor / 1e6

    if tu < tth:
        torsion_action = "Neglect Torsion"
    else:
        torsion_action = "Design for Torsion"

    # Cross-section dimension check
    shear_stress = vu * 1000 / (bw * d)
    if tu >= tth:
        torsion_stress = tu * 1e6 * ph / (1.7 * aoh ** 2)
        combined = math.sqrt(shear_stress ** 2 + torsion_stress ** 2)
        limit = phi * (vc * 1000 / (bw * d) + (2.0 / 3.0) * math.sqrt(fc))
        dim_check = "SAFE" if combined <= limit else "UNSAFE"
    else:
        torsion_stress = 0
        combined = shear_stress
        limit = phi * (vc * 1000 / (bw * d) + (2.0 / 3.0) * math.sqrt(fc))
        dim_check = "SAFE"

    steps.append({
        "title": "Torsion Thresholds",
        "items": [
            {"label": "\u03c6Tcr", "value": round(tcr, 4), "unit": "kN.m",
             "ref": "ACI 318M-14 Cl. 22.7.5.1"},
            {"label": "\u03c6Tth", "value": round(tth, 4), "unit": "kN.m",
             "ref": "ACI 318M-14 Cl. 22.7.4.1"},
            {"label": "Action", "value": torsion_action},
            {"label": "Section Check", "value": dim_check,
             "ref": "ACI 318M-14 Cl. 22.7.7.1"},
        ],
    })

    # ── 7. Torsion reinforcement ──
    if torsion_action == "Neglect Torsion":
        at_s = 0
        al = 0
        al_min = 0
    else:
        # Eq. (22.7.6.1a): Tn = 2 Ao At fyt cot(theta) / s, with
        # Ao = 0.85 Aoh (22.7.6.1.1) and theta = 45 deg (22.7.6.1.2a),
        # so At/s = Tu / (phi * 1.7 * Aoh * fyt), per leg.
        at_s = tu * 1e6 / (phi * 2 * 0.85 * aoh * fyv)
        # Eq. (22.7.6.1b): Tn = 2 Ao Al fy tan(theta) / ph, same Ao and
        # theta, so Al = (Tu/phi) ph / (1.7 Aoh fy) cot(theta).
        # The divisor is 1.7 Aoh, NOT 2 Aoh: 2 Ao = 2 (0.85 Aoh) = 1.7 Aoh.
        # Using 2 Aoh made every Al exactly 1.7/2 = 0.85 of the required
        # area, i.e. 15.00% short, unconservatively, on every section.
        al = tu * 1e6 * ph / (1.7 * phi * aoh * fy)
        # Al,min
        # Section 9.6.4.3(a), printed 152:
        #   Al,min = 0.42 sqrt(f'c) Acp / fy - (At/s) ph (fyt/fy)
        # This read 5/12 = 0.4167, which is not a printed value. Note the
        # SI 0.42 is itself 1.16% above the exact conversion of the
        # inch-pound 5 sqrt(f'c) Acp / fy that Wight & MacGregor works in,
        # so a ~1% gap against a W&M worked example here is code rounding,
        # not a defect.
        al_min = (0.42 * math.sqrt(fc) * bw * h / fy
                  - max(at_s, 0.175 * bw / fyv) * ph * fyv / fy)

    steps.append({
        "title": "Torsion Reinforcement",
        "items": [
            {"label": "At/s", "value": round(at_s, 4), "unit": "mm\u00b2/mm/leg",
             "ref": "ACI 318M-14 Cl. 22.7.6.1a"},
            {"label": "A\u2113", "value": round(max(al, al_min, 0), 2), "unit": "mm\u00b2",
             "ref": "ACI 318M-14 Cl. 22.7.6.1b"},
            {"label": "A\u2113,min", "value": round(max(al_min, 0), 2), "unit": "mm\u00b2",
             "ref": "ACI 318M-14 Cl. 9.6.4.3"},
        ],
    })

    # ── 8. Minimum shear reinforcement ──
    # Table 9.6.3.4(a)/(b), printed 151: 0.062 sqrt(f'c) bw/fyt and
    # 0.35 bw/fyt. This used to read 1/16 = 0.0625 -- W&M Eq. (6-20M)'s
    # rounding -- while compute_shear_spacing() used 0.062. Two constants
    # 0.8% apart for one provision, inside one package. Now one constant.
    av_min_1 = 0.062 * math.sqrt(fc) * bw / fyv
    av_min_2 = 0.35 * bw / fyv
    av_min = max(av_min_1, av_min_2)

    steps.append({
        "title": "Minimum Shear Reinforcement",
        "items": [
            {"label": "Av,min/s", "value": round(av_min, 4), "unit": "mm\u00b2/mm",
             "ref": "ACI 318M-14 Table 9.6.3.3"},
        ],
    })

    # ── 9. Total required ──
    total_req = max(av_s_shear + 2 * at_s, av_min)

    steps.append({
        "title": "Total Required Reinforcement",
        "items": [
            {"label": "(Av+2At)/s", "value": round(total_req, 4),
             "unit": "mm\u00b2/mm",
             "ref": "ACI 318M-14 Cl. 9.6.4.2"},
            {"label": "A\u2113 (torsion)", "value": round(max(al, al_min, 0), 2),
             "unit": "mm\u00b2"},
        ],
    })

    # ── 10. Chosen reinforcement check ──
    av_leg = math.pi * (db_stirrup / 2) ** 2
    av_provided_per_s = n_legs * av_leg / s_chosen

    # Max spacing
    if vs > (1.0 / 3.0) * math.sqrt(fc) * bw * d / 1000:
        smax = min(300, d / 4, ph / 8)
    else:
        smax = min(600, d / 2)
    if torsion_action != "Neglect Torsion":
        smax = min(smax, ph / 8, 300)

    spacing_check = "OK" if s_chosen <= smax else "NOT OK"
    rft_check = "OK" if av_provided_per_s >= total_req else "NOT OK"

    # Compute chosen bar sizes
    if total_req > av_min:
        ext_dia = math.ceil(math.sqrt(4 / math.pi * (at_s * s_chosen + av_s_shear * s_chosen / n_legs)) / 2) * 2
    else:
        ext_dia = math.ceil(math.sqrt(4 / math.pi * av_min * s_chosen / n_legs) / 2) * 2

    steps.append({
        "title": "Chosen Reinforcement",
        "items": [
            {"label": "Spacing", "value": s_chosen, "unit": "mm",
             "check": spacing_check},
            {"label": "Smax", "value": round(smax, 0), "unit": "mm",
             "ref": "ACI 318M-14 Cl. 9.7.6.2.2"},
            {"label": "Legs", "value": n_legs},
            {"label": "Provided (Av+2At)/s", "value": round(av_provided_per_s, 4),
             "unit": "mm\u00b2/mm", "check": rft_check},
            {"label": "Suggested ext. stirrup \u2300", "value": ext_dia, "unit": "mm"},
        ],
    })

    return {
        "steps": steps,
        "vc": round(vc, 2),
        "vs": round(max(vs, 0), 2),
        "vs_max": round(vs_max, 2),
        "vu_max": round(vu_max, 2),
        "av_s_shear": round(av_s_shear, 4),
        "at_s": round(at_s, 4),
        "al": round(max(al, al_min, 0), 2),
        "total_req": round(total_req, 4),
        "av_min": round(av_min, 4),
        "aoh": round(aoh, 0),
        "ph": round(ph, 0),
        "tcr": round(tcr, 4),
        "tth": round(tth, 4),
        "torsion_action": torsion_action,
        "shear_status": overall_check,
        "vs_status": shear_status,
        "dim_check": dim_check,
        "smax": round(smax, 0),
        "spacing_check": spacing_check,
    }


def shear_design(fc, fyv, phi, bw, h, cc, c, d, vu, nu,
                 s_chosen, n_legs, db_stirrup):
    """
    Beam shear design per NSCP 2015 Section 422.5 (= ACI 318M-14),
    shear only, no torsion.

    Parameters
    ----------
    fc : float       Concrete compressive strength (MPa).
    fyv : float      Yield strength of stirrups (MPa).
    phi : float      Strength reduction factor for shear.
    bw : float       Width of beam (mm).
    h : float        Total height of beam (mm).
    cc : float       Clear cover to links (mm).
    c : float        Cover to centroid of reinforcement (mm).
    d : float        Effective depth (mm).
    vu : float       Factored shear force (kN).
    nu : float       Factored axial force (kN), positive = compression.
    s_chosen : float Chosen stirrup spacing (mm).
    n_legs : int     Total number of stirrup legs.
    db_stirrup : float  Stirrup bar diameter (mm).

    Returns
    -------
    dict with all intermediate values for shear design report.
    """
    ag = bw * h  # gross area mm^2

    # ── 1. Concrete shear strength Vc ──
    if nu > 0:
        # Cl. 22.5.6.1 / W&M Eq. (6-13aM), printed 282. See the note in
        # shear_torsion_design(): the deleted min() second branch had no
        # basis in reference/ and never governed for any Nu >= 0.
        vc = (1 + nu * 1000 / (14 * ag)) * (math.sqrt(fc) / 6) * bw * d / 1000
        vc_note = "with axial compression"
    elif nu < 0:
        vc = max(0, (1 + 0.29 * nu * 1000 / ag) * (math.sqrt(fc) / 6) * bw * d / 1000)
        vc_note = "with axial tension"
    else:
        vc = (math.sqrt(fc) / 6) * bw * d / 1000
        vc_note = "no axial load"

    # ── 2. Required stirrup shear strength Vs ──
    vs_max = (2.0 / 3.0) * math.sqrt(fc) * bw * d / 1000
    vs_req = (vu - phi * vc) / phi

    if vs_req <= 0:
        vs = 0
    elif vs_req > vs_max:
        vs = vs_req
    else:
        vs = vs_req

    vu_max = phi * (vc + vs_max)
    shear_status = "SAFE" if vu <= vu_max else "UNSAFE"

    # Av/s required for shear
    av_s_req = (vu * 1000 - phi * vc * 1000) / (phi * fyv * d) if vs > 0 else 0

    # ── 3. Minimum shear reinforcement ──
    # Table 9.6.3.4(a)/(b), printed 151: 0.062 sqrt(f'c) bw/fyt and
    # 0.35 bw/fyt. This used to read 1/16 = 0.0625 -- W&M Eq. (6-20M)'s
    # rounding -- while compute_shear_spacing() used 0.062. Two constants
    # 0.8% apart for one provision, inside one package. Now one constant.
    av_min_1 = 0.062 * math.sqrt(fc) * bw / fyv
    av_min_2 = 0.35 * bw / fyv
    av_min = max(av_min_1, av_min_2)

    # Governing Av/s
    av_s_govern = max(av_s_req, av_min)

    # ── 4. Maximum spacing ──
    if vs > (1.0 / 3.0) * math.sqrt(fc) * bw * d / 1000:
        smax = min(300, d / 4)
    else:
        smax = min(600, d / 2)

    # ── 5. Chosen reinforcement check ──
    av_leg = math.pi * (db_stirrup / 2) ** 2
    av_provided = n_legs * av_leg / s_chosen

    spacing_ok = "OK" if s_chosen <= smax else "NOT OK"
    rft_ok = "OK" if av_provided >= av_s_govern else "NOT OK"

    return {
        "vc": round(vc, 2),
        "vc_note": vc_note,
        "vs": round(max(vs, 0), 2),
        "vs_req": round(max(vs_req, 0), 2),
        "vs_max": round(vs_max, 2),
        "vu_max": round(vu_max, 2),
        "shear_status": shear_status,
        "av_s_req": round(max(av_s_req, 0), 4),
        "av_min": round(av_min, 4),
        "av_s_govern": round(av_s_govern, 4),
        "smax": round(smax, 0),
        "av_provided": round(av_provided, 4),
        "spacing_ok": spacing_ok,
        "rft_ok": rft_ok,
    }
