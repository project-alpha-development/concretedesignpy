# MIT License
# Copyright (c) Albert Pamonag Engineering Consultancy

"""
Footing Jacketing (Enlargement of an Existing Isolated Footing)
===============================================================

Checks an existing rectangular isolated footing that is enlarged by a
reinforced-concrete jacket: side extensions ("wings") on any of the four
sides, with or without a bonded overlay on top.

Governing edition
-----------------
**ACI 562-25** for the repair (load history, interface, strength reduction
factors) with **ACI 318-25M** as the design-basis code for every member
strength. ASCE 41-17 C8.7 is the commentary that names the contact pressure
existing when the jacket is cast as something to consider.

Load history - read this first
------------------------------
ACI 562-25 R9.4.1 (printed 85): "bonded repairs or section enlargements
resist only those forces applied after the repair or enlargement is
constructed", unless jacking or shoring relieves the existing stresses.
ASCE 41-17 C8.7, shallow foundation retrofit item 2 (printed 455), is
commentary and says the same of footings in softer words: consideration
of the existing contact pressures "may be required" unless shoring or
jacking achieves a uniform distribution. This module always considers
them.

So ``shored`` is a required argument with no default:

* ``shored=False`` - the load present at casting (P0, M0) stays on the
  old footprint; only the increment spreads over the enlarged footing.
  The old footprint then carries q0 + q1 and the wings carry q1 alone,
  which is what makes bearing under the old footprint the usual
  governing check of an unshored enlargement.
* ``shored=True`` - the existing load is relieved before casting and the
  whole load spreads over the enlarged footing.

The locked-in load is taken UNFACTORED in the strength checks too: it is
the load actually on the soil when the jacket is cast, and every kN of
factored load above it is put through the composite footing, where it
produces the larger moment, shear and interface demand.

Clause register (ACI 318-25M unless noted; printed page)
--------------------------------------------------------
    bearing area ................. 13.3.1.1 (211)
    minimum effective depth ...... 13.3.1.2 (212)
    rigid footing shear .......... 13.2.6.2(a), (b) (208)
    critical sections ............ Table 13.2.7.1, 13.2.7.2 (210)
    design per Ch. 7 and 8 ....... 13.3.3.1 (212)
    shear at face of support ..... 7.4.3.2 (101)
    minimum flexural steel ....... 7.6.1.1 (102), 8.6.1.1 (122)
    minimum steel at the column .. Eq. 8.6.1.2 (122), 8.4.2.2.3 (116-117), Eq. 22.5.5.1.3 (445)
    moment transfer in punching .. Eq. 8.4.2.2.2 (116), 8.4.4.2, R8.4.4.2.3 (118-119)
    horizontal shear transfer .... 16.4.1.2, 16.4.3.1, Table 16.4.4.1, 16.4.6.1, 16.4.7.2 (243-246)
    fy for shear friction ........ Table 20.2.2.4(a) (414)
    stress block, beta1 .......... 22.2.2.4.1, Table 22.2.2.4.3 (438-439)
    composite Mn ................. 22.3.3.2 to 22.3.3.4 (440)
    sqrt(f'c) limit .............. 22.5.3.1 (443), 22.6.3.1 (451)
    composite Vn ................. 22.5.4.2 to 22.5.4.4 (444)
    two-way shear ................ 22.6.2.1, 22.6.4.1 (451), Table 22.6.5.2 (454), 22.6.5.3 (455)
    shear friction ............... Eq. 22.9.4.2, Table 22.9.4.2 (472), Table 22.9.4.4 (474), R22.9.4.5 (474)
    forces across an interface ... 22.3.3.1, R22.3.3.1 (440)
    strength reduction factors ... ACI 562-25 Table 5.3.2 (38)
    interface shear .............. ACI 562-25 9.3.3 (85), 9.4.4 (88), 9.4.4.3 (89)
    shear in two directions ...... ACI 562-25 R9.4.5.3 (90)

Not checked here
----------------
See ``NOT_CHECKED``. The list is returned with every result so that a
report states the gaps instead of implying the design is complete.
"""

import math

ES = 200000.0   # MPa

# ACI 562-25 Table 5.3.2, printed 38 - repair or rehabilitation design.
# The detailed-assessment values of Table 5.4.1 need measured dimensions
# and material properties, which a jacket that is not built yet does not
# have, so they are not offered.
PHI_TENSION_CONTROLLED = 0.90
PHI_COMPRESSION_CONTROLLED = 0.65
PHI_SHEAR = 0.75
PHI_INTERFACE_SHEAR = 0.75

# ACI 318-25M 7.6.1.1 / 8.6.1.1
RHO_MIN_FLEXURE = 0.0018

# ACI 318-25M 22.5.3.1 and 22.6.3.1
SQRT_FC_MAX = 8.3   # MPa

# ACI 318-25M Table 20.2.2.4(a), shear friction
FY_SHEAR_FRICTION_MAX = 420.0   # MPa

# ACI 318-25M Table 22.9.4.2. Row (c) carries no lambda from the 2025 Code.
MU_ROUGHENED = 1.0
MU_NOT_ROUGHENED = 0.6

# ACI 318-25M Table 16.4.4.1
VNH_BOND = 0.55          # MPa, row (a)
VNH_TIES_BASE = 1.8      # MPa, row (c)
VNH_TIES_SLOPE = 0.6
VNH_TIES_MAX = 3.5       # MPa, row (c)
AVF_MIN_COEFF = 0.35     # 16.4.6.1: Avf,min = 0.35 bv s / fy
TIE_SPACING_MAX = 600.0  # mm, 16.4.7.2

# ACI 318-25M 13.3.1.2
D_MIN = 150.0            # mm

SURFACES = ("roughened", "not_roughened")
LEGAL_ALPHA_S = (40, 30, 20)   # 22.6.5.3

NOT_CHECKED = [
    "Anchorage of the post-installed dowels and overlay ties in the existing "
    "footing: as adhesive anchors (ACI 318-25M Chapter 17), or as "
    "post-installed reinforcing bars developed to 25.4.2 and 25.4.9 "
    "(17.1.3) with the bar-group breakout of 25.4.11. Shear friction needs "
    "fy developed on both sides of the plane (22.9.5.1), overlay ties "
    "likewise (16.4.7.3). ACI 562-25 9.4.4.5 and 9.4.3.4 cap the force "
    "credited to post-installed reinforcement at that anchorage value; "
    "9.4.4.6 and 9.4.3.5 do the same on the new-concrete side.",
    "Development of the existing bottom bars beyond the column-face critical "
    "section (ACI 318-25M 13.2.8). They stop at the old footing edge, and "
    "the jacket raises the force they must develop.",
    "Force transfer at the column base: bearing and dowels (ACI 318-25M "
    "16.3 and 22.8).",
    "Partial contact. The pressure model is linear with the whole base in "
    "compression; a case that lifts off is reported as a failed contact "
    "check, not solved.",
    "Sliding, overturning, settlement and the softer response of the soil "
    "under the new wings, which has not been preloaded like the soil under "
    "the old footprint. The permissible bearing pressure is an input "
    "(ACI 318-25M 13.3.1.1).",
    "Where the bars actually are. The minimum of ACI 318-25M Eq. (8.6.1.2) "
    "is checked with the existing bars spread evenly over the old footing "
    "and the new bars evenly over the wings; the band of 13.3.3.3, the "
    "flexural transfer of the column moment within b_slab (8.5.1.1(b)), "
    "bar spacing and crack control are not checked.",
    "Seismic requirements for foundations (ACI 318-25M 18.13) and "
    "capacity-design demands from the column above.",
    "Bond testing of the prepared surfaces (ACI 562-25 13.4.5), which "
    "Tables 9.4.4.1a and 9.4.4.1b call for.",
    "The existing footing during construction: excavation beside it and "
    "any loss of bearing or confinement while the jacket is built "
    "(ACI 562-25 9.2.1, 9.2.3).",
]


def _bar_area(db):
    return math.pi * db ** 2 / 4.0


def _beta1(fc):
    """ACI 318-25M Table 22.2.2.4.3."""
    if fc <= 28.0:
        return 0.85
    if fc >= 55.0:
        return 0.65
    return 0.85 - 0.05 * (fc - 28.0) / 7.0


def _section(layers, b, fc):
    """Rectangular stress block with every tension layer at yield.

    layers : (As mm^2, fy MPa, d mm) per layer; layers with As = 0 are
    ignored. Returns the block, the net tensile strain and phi from
    ACI 562-25 Table 5.3.2 (same limits as ACI 318-25M Table 21.2.2).
    """
    live = [(As, fy, d) for As, fy, d in layers if As > 0]
    As_total = sum(As for As, _, _ in live)
    if As_total <= 0:
        return {"As": 0.0, "T": 0.0, "a": 0.0, "c": 0.0, "d": 0.0, "dt": 0.0,
                "eps_t": 0.0, "eps_ty": 0.0, "phi": PHI_TENSION_CONTROLLED,
                "Mn": 0.0, "phiMn": 0.0, "yields": True}
    T = sum(As * fy for As, fy, _ in live)                 # N
    a = T / (0.85 * fc * b)                                # mm
    c = a / _beta1(fc)
    d = sum(As * dd for As, _, dd in live) / As_total      # centroid, mm
    dt = max(dd for _, _, dd in live)
    eps_t = 0.003 * (dt - c) / c
    eps_ty = max(fy for _, fy, _ in live) / ES
    phi = 0.65 + 0.25 * (eps_t - eps_ty) / 0.003
    phi = min(PHI_TENSION_CONTROLLED, max(PHI_COMPRESSION_CONTROLLED, phi))
    yields = all(0.003 * (dd - c) / c >= fy / ES for _, fy, dd in live)
    Mn = sum(As * fy * (dd - a / 2.0) for As, fy, dd in live) / 1e6   # kN*m
    return {"As": As_total, "T": T / 1000.0, "a": a, "c": c, "d": d,
            "dt": dt, "eps_t": eps_t, "eps_ty": eps_ty, "phi": phi,
            "Mn": Mn, "phiMn": phi * Mn, "yields": yields}


def _strip(P, M, length, x):
    """Resultants of a linear pressure on the strip beyond a section.

    The footing of the given length carries P (kN) and M (kN*m) with the
    whole base in contact. For the part between the section at x (mm from
    the centre) and the edge, on the side where M adds pressure, returns
    (V from P, V from M, moment from P, moment from M) in kN and kN*m.
    """
    a = max(0.0, length / 2.0 - x)
    V_P = P * a / length
    V_M = 6.0 * M * a * (length / 2.0 + x) / length ** 3 * 1000.0
    M_P = P * a ** 2 / (2.0 * length) / 1000.0
    M_M = M * a ** 2 * (4.0 * a + 6.0 * x) / length ** 3
    return V_P, V_M, M_P, M_M


def _friction_caps(surface, lam, fc):
    """ACI 318-25M Table 22.9.4.4, as a stress in MPa."""
    if surface == "roughened" and lam >= 1.0:
        return min(0.2 * fc, 3.3 + 0.08 * fc, 11.0)
    return min(0.2 * fc, 5.5)


def footing_jacket_check(
    *,
    B0, L0, h0, fc0, fy0,
    n0_L, db0_L, n0_B, db0_B, cover0,
    cB, cL,
    eB, eL, t_top, fcj, fyj,
    nj_L, dbj_L, nj_B, dbj_B, cover_j,
    surface,
    nd_L, ndt_L, nd_B, ndt_B, db_dowel, fy_dowel, z_dowel,
    db_tie, s_tie, fy_tie,
    P, ML, MB, qa,
    Pu, MuL, MuB,
    P0, M0L, M0B,
    shored,
    column_engaged=False, alpha_s=40, lam=1.0,
):
    """
    Check an existing isolated footing enlarged by an RC jacket.

    Directions: "L" quantities belong to the cantilevers that project
    along L. Their critical sections are planes of width B, and the bars
    that resist them run parallel to L. "B" quantities are the same thing
    turned through 90 degrees.

    Parameters (mm, MPa, kN, kN*m, kPa)
    -----------------------------------
    B0, L0, h0 : existing footing plan dimensions and thickness.
    fc0, fy0 : existing concrete and reinforcement strengths.
    n0_L, db0_L : existing bottom bars parallel to L (outer layer).
    n0_B, db0_B : existing bottom bars parallel to B (inner layer).
    cover0 : clear cover to the existing outer bottom layer.
    cB, cL : column dimensions parallel to B and to L.
    eB, eL : wing width added on EACH side in the B and L directions.
    t_top : bonded overlay thickness on top (0 for none). The wings are
        cast to the full depth h0 + t_top.
    fcj, fyj : jacket concrete and reinforcement strengths.
    nj_L, dbj_L : new bottom bars parallel to L, total in the two side
        wings, continuous over the full length.
    nj_B, dbj_B : new bottom bars parallel to B, total in the two end wings.
    cover_j : clear cover to the new outer bottom layer.
    surface : "roughened" (about 6 mm amplitude) or "not_roughened", for
        every old-to-new contact surface.
    nd_L, ndt_L : dowels crossing EACH end face (the old faces of width
        B0), and how many of them are in the bottom tension row.
    nd_B, ndt_B : the same for each side face (width L0).
    db_dowel, fy_dowel : dowel diameter and yield strength.
    z_dowel : height of the bottom dowel row above the footing soffit.
    db_tie, s_tie, fy_tie : overlay ties on a square grid of spacing
        s_tie (db_tie = 0 for none).
    P, ML, MB : service load and moments at the top of the footing. ML
        varies the pressure along L, MB along B.
    qa : permissible net bearing pressure for that service combination.
    Pu, MuL, MuB : factored load and moments.
    P0, M0L, M0B : service load and moments on the footing when the
        jacket is cast.
    shored : True if the existing load is relieved before casting.
    column_engaged : True if the overlay is tied to the column (column
        jacket bearing on it, or dowels), so that the column load enters
        at the top of the overlay. If not, punching uses the depth of the
        existing footing alone.
    alpha_s : 40, 30 or 20 (ACI 318-25M 22.6.5.3).
    lam : lightweight concrete factor.

    Returns
    -------
    dict with every intermediate value, an ``*_ok`` flag per check,
    ``overall_pass`` and ``not_checked``.
    """
    if surface not in SURFACES:
        raise ValueError("surface must be one of %s" % (SURFACES,))
    if alpha_s not in LEGAL_ALPHA_S:
        raise ValueError("alpha_s must be 40, 30 or 20 (ACI 318-25M 22.6.5.3)")
    if not isinstance(shored, bool):
        raise ValueError("shored must be True or False - the load history "
                         "is not optional (ACI 562-25 R9.4.1)")
    for name, value in (("B0", B0), ("L0", L0), ("h0", h0), ("fc0", fc0),
                        ("fy0", fy0), ("fcj", fcj), ("fyj", fyj),
                        ("cB", cB), ("cL", cL), ("qa", qa), ("lam", lam)):
        if value <= 0:
            raise ValueError("%s must be positive" % name)
    for name, value in (("eB", eB), ("eL", eL), ("t_top", t_top),
                        ("P", P), ("Pu", Pu), ("P0", P0)):
        if value < 0:
            raise ValueError("%s cannot be negative" % name)
    if cB >= B0 or cL >= L0:
        raise ValueError("the column must be smaller than the existing footing")
    if ndt_L > nd_L or ndt_B > nd_B:
        raise ValueError("the bottom-row dowels are part of the dowels on a "
                         "face: ndt cannot exceed nd")

    # 1.0 Geometry
    B = B0 + 2.0 * eB                       # mm
    L = L0 + 2.0 * eL                       # mm
    h = h0 + t_top                          # mm
    A0 = B0 * L0                            # mm^2
    A = B * L                               # mm^2
    fc = min(fc0, fcj)                      # 22.3.3.4, 22.5.4.3, 22.9.4.4
    sqrt_fc = min(math.sqrt(fc), SQRT_FC_MAX)

    As0_L = n0_L * _bar_area(db0_L)
    As0_B = n0_B * _bar_area(db0_B)
    Asj_L = nj_L * _bar_area(dbj_L)
    Asj_B = nj_B * _bar_area(dbj_B)
    Ab_dowel = _bar_area(db_dowel)
    Asd_L = ndt_L * Ab_dowel                # wing-root tension row
    Asd_B = ndt_B * Ab_dowel

    # Depths from the top of the jacketed footing. The soffits of the old
    # footing and the wings are level.
    d0_L = h - cover0 - db0_L / 2.0
    d0_B = h - cover0 - db0_L - db0_B / 2.0
    dj_L = h - cover_j - dbj_L / 2.0
    dj_B = h - cover_j - dbj_L - dbj_B / 2.0
    dd = h - z_dowel

    # 2.0 Load history - ACI 562-25 R9.4.1, ASCE 41-17 C8.7
    P0e = 0.0 if shored else P0
    M0Le = 0.0 if shored else M0L
    M0Be = 0.0 if shored else M0B
    dP = P - P0e
    dML = ML - M0Le
    dMB = MB - M0Be
    dPu = Pu - P0e
    dMuL = MuL - M0Le
    dMuB = MuB - M0Be

    # 3.0 Bearing - ACI 318-25M 13.3.1.1. Pressures in kPa.
    def pressures(dP_, dML_, dMB_):
        q0 = P0e / A0 * 1e6
        q1 = dP_ / A * 1e6
        g_old = (abs(6e9 * M0Le / (B0 * L0 ** 2) + 6e9 * dML_ * L0 / (B * L ** 3))
                 + abs(6e9 * M0Be / (L0 * B0 ** 2) + 6e9 * dMB_ * B0 / (L * B ** 3)))
        g_wing = (abs(6e9 * dML_ / (B * L ** 2))
                  + abs(6e9 * dMB_ / (L * B ** 2)))
        return {"q0": q0, "q1": q1,
                "old_max": q0 + q1 + g_old, "old_min": q0 + q1 - g_old,
                "wing_max": q1 + g_wing, "wing_min": q1 - g_wing}

    qs = pressures(dP, dML, dMB)
    qu = pressures(dPu, dMuL, dMuB)
    q_max = max(qs["old_max"], qs["wing_max"])
    q_min = min(qs["old_min"], qs["wing_min"])
    qu_min = min(qu["old_min"], qu["wing_min"])
    bearing_ratio = q_max / qa
    bearing_ok = q_max <= qa
    contact_ok = q_min >= 0.0
    contact_u_ok = qu_min >= 0.0

    # 4.0 The four strip checks, once per direction
    def direction(length0, length, width0, width, col, e_wing, e_strip,
                  M0e, dMu, As0, d0, Asj, dj, Asd, nd):
        res = {}
        x_face = col / 2.0

        # Flexure at the column face - Table 13.2.7.1, 22.3.3
        sec = _section([(As0, fy0, d0), (Asj, fyj, dj)], width, fc)
        _, _, m0P, m0M = _strip(P0e, M0e, length0, x_face)
        _, _, m1P, m1M = _strip(dPu, dMu, length, x_face)
        Mu_face = m0P + m1P + abs(m0M + m1M)
        As_min = RHO_MIN_FLEXURE * width * h
        res.update({
            "As": sec["As"], "d": sec["d"], "a": sec["a"], "c": sec["c"],
            "eps_t": sec["eps_t"], "phi_f": sec["phi"], "Mn": sec["Mn"],
            "phiMn": sec["phiMn"], "Mu": Mu_face,
            "flex_ratio": Mu_face / sec["phiMn"] if sec["phiMn"] > 0 else 0.0,
            "flex_ok": sec["yields"] and Mu_face <= sec["phiMn"],
            "yield_ok": sec["yields"],
            "As_min": As_min, "As_min_ok": sec["As"] >= As_min,
        })

        # Longitudinal shear between the old footing and the wings beside
        # this section. Their bars are counted in As, but a wing e_strip
        # wide holds a tension that its own share of the stress block does
        # not balance; the difference crosses the old face as a shear
        # parallel to it (22.3.3.1, R22.3.3.1), at the level the factored
        # moment mobilises. With an overlay the old footing hands its
        # tension to the new concrete through the horizontal surface, which
        # 16.4 covers.
        if e_strip > 0 and not overlay and sec["Mn"] > 0:
            N_strip = (abs(Asj / 2.0 * fyj - 0.85 * fc * sec["a"] * e_strip)
                       / 1000.0 * min(1.0, Mu_face / sec["Mn"]))
        else:
            N_strip = 0.0
        res["N_strip"] = N_strip

        # One-way shear at d from the column face - 13.2.7.2, 13.2.6.2(a).
        # The column bears on the old footing unless the overlay is tied to
        # it, so an untied overlay neither moves the critical section out
        # nor adds to Vc (7.4.3.2 rests the d offset on the reaction).
        d = sec["d"]
        d_v = d if tied else d - t_top
        v0P, v0M, _, _ = _strip(P0e, M0e, length0, x_face + d_v)
        v1P, v1M, _, _ = _strip(dPu, dMu, length, x_face + d_v)
        Vu = v0P + v1P + abs(v0M + v1M)
        phiVc = PHI_SHEAR * 0.17 * lam * sqrt_fc * width * d_v / 1000.0
        res.update({
            "d_v": d_v, "Vu": Vu, "phiVc": phiVc,
            "shear_ratio": Vu / phiVc if phiVc > 0 else 0.0,
            "shear_ok": Vu <= phiVc,
        })

        # Wing - cantilever from the old footing face, 7.4.3.2
        wing = e_wing > 0
        x_root = length0 / 2.0
        wsec = _section([(Asd, fy_dowel, dd), (Asj, fyj, dj)], width, fc)
        if wing:
            wVP, wVM, wMP, wMM = _strip(dPu, abs(dMu), length, x_root)
            Vu_w = wVP + wVM
            Mu_w = wMP + wMM
        else:
            Vu_w = Mu_w = 0.0
        phiVc_w = PHI_SHEAR * 0.17 * lam * sqrt_fc * width * wsec["d"] / 1000.0
        res.update({
            "wing": wing, "Mu_w": Mu_w, "Vu_w": Vu_w,
            "As_w": wsec["As"], "d_w": wsec["d"], "a_w": wsec["a"],
            "phi_w": wsec["phi"], "phiMn_w": wsec["phiMn"],
            "wflex_ratio": Mu_w / wsec["phiMn"] if wsec["phiMn"] > 0 else 0.0,
            "wflex_ok": (not wing) or (wsec["yields"] and Mu_w <= wsec["phiMn"]),
            # 7.6.1.1 / 8.6.1.1 at the old face, where the existing bars
            # have stopped and only the dowels and the new bars cross
            "wAs_min_ok": (not wing) or wsec["As"] >= As_min,
            "phiVc_w": phiVc_w,
            "wshear_ratio": Vu_w / phiVc_w if phiVc_w > 0 else 0.0,
            "wshear_ok": (not wing) or Vu_w <= phiVc_w,
        })

        # Shear friction strength of the old face - 22.9.4.2, Table
        # 22.9.4.4. Nu = 0: nothing clamps a vertical face of a footing.
        Avf = nd * Ab_dowel
        Ac = width0 * h0
        Vn_raw = mu * Avf * fy_sf / 1000.0
        Vn_cap = cap_stress * Ac / 1000.0
        Vn = min(Vn_raw, Vn_cap)
        res.update({
            "Avf": Avf, "Ac_if": Ac, "Vn_raw": Vn_raw, "Vn_cap": Vn_cap,
            "Vn_if": Vn, "phiVn_if": PHI_INTERFACE_SHEAR * Vn,
        })

        # Overlay - horizontal shear at the column face, 16.4.3.1.
        # The stage-0 shear is all within the old width; the increment is
        # spread over the full width and the old width takes its share.
        share = width0 / width
        h0P, h0M, _, _ = _strip(P0e, M0e, length0, x_face)
        h1P, h1M, _, _ = _strip(dPu, dMu, length, x_face)
        Vuh = h0P + h1P * share + abs(h0M + h1M * share) if overlay else 0.0
        phiVnh = PHI_INTERFACE_SHEAR * vnh * width0 * d / 1000.0
        res.update({
            "Vuh": Vuh, "phiVnh": phiVnh,
            "ov_ratio": Vuh / phiVnh if (overlay and phiVnh > 0) else 0.0,
            "ov_ok": (not overlay) or Vuh <= phiVnh,
        })
        return res

    # Interface properties shared by both directions
    fy_sf = min(fy_dowel, FY_SHEAR_FRICTION_MAX)
    # Table 22.9.4.2 footnote [1]: lambda for lightweight concrete shall
    # not exceed 0.85 in the coefficient of friction.
    lam_mu = lam if lam >= 1.0 else min(lam, 0.85)
    mu = MU_ROUGHENED * lam_mu if surface == "roughened" else MU_NOT_ROUGHENED
    cap_stress = _friction_caps(surface, lam, fc)

    overlay = t_top > 0
    wings = eB > 0 or eL > 0
    tied = column_engaged or not overlay
    ties = overlay and db_tie > 0 and s_tie > 0
    rho_v = _bar_area(db_tie) / s_tie ** 2 if ties else 0.0
    fyt = min(fy_tie, FY_SHEAR_FRICTION_MAX) if ties else 0.0
    rho_v_min = AVF_MIN_COEFF / fyt if ties else 0.0
    ties_min_ok = ties and rho_v >= rho_v_min
    # 16.4.1.2: where tension can act across the contact surface, transfer
    # by contact needs the minimum ties. Soil pressure on wings cast with
    # the overlay tends to lift it off the old footing, so bond alone is
    # credited only to an overlay without wings.
    bond_allowed = (not wings) or ties_min_ok
    # Table 16.4.4.1: Avf,min of 16.4.6.1 applies to rows (b), (c) and (d)
    if surface == "roughened":
        vnh_a = VNH_BOND if bond_allowed else 0.0            # row (a)
        vnh_c = (min(lam * (VNH_TIES_BASE + VNH_TIES_SLOPE * rho_v * fyt),
                     VNH_TIES_MAX) if ties_min_ok else 0.0)  # row (c)
    else:
        vnh_a = 0.0
        vnh_c = 0.0
    vnh_sf = (min(mu * rho_v * fyt, cap_stress)
              if ties_min_ok else 0.0)                       # rows (b), (d)
    vnh = max(vnh_a, vnh_c, vnh_sf) if overlay else 0.0
    # ACI 562-25 9.4.4.3: an intentionally roughened substrate shall be
    # specified. An unroughened surface is calculated, for assessing what is
    # there, and reported as not complying.
    surface_ok = surface == "roughened" or not (wings or overlay)
    s_tie_max = min(TIE_SPACING_MAX, 4.0 * t_top) if overlay else 0.0
    tie_spacing_ok = (not ties) or s_tie <= s_tie_max

    rL = direction(L0, L, B0, B, cL, eL, eB, M0Le, dMuL,
                   As0_L, d0_L, Asj_L, dj_L, Asd_L, nd_L)
    rB = direction(B0, B, L0, L, cB, eB, eL, M0Be, dMuB,
                   As0_B, d0_B, Asj_B, dj_B, Asd_B, nd_B)
    if rL["As"] <= 0 or rB["As"] <= 0:
        raise ValueError("no tension reinforcement at the column face - a "
                         "plain concrete footing is outside this check")

    # Demand on each old face: the wing shear across it, and along it the
    # longitudinal shear of the wings it holds, which belongs to flexure in
    # the OTHER direction. Each half of the face takes half the wing shear
    # and one wing's longitudinal force, so the whole face is checked for
    # the resultant of Vu_w and 2 N.
    for r, other in ((rL, rB), (rB, rL)):
        Vu_if = math.hypot(r["Vu_w"], 2.0 * other["N_strip"])
        r.update({
            "Vu_if": Vu_if,
            "if_ratio": Vu_if / r["phiVn_if"] if r["phiVn_if"] > 0 else 0.0,
            "if_ok": (not r["wing"]) or Vu_if <= r["phiVn_if"],
            "Avf_req": (Vu_if * 1000.0 / (PHI_INTERFACE_SHEAR * mu * fy_sf)
                        if r["wing"] else 0.0),
        })

    # 5.0 Two-way shear - 22.6. The overlay only deepens the punching
    # section if the column load enters at the top of the overlay.
    d_avg = (rL["d"] + rB["d"]) / 2.0                       # 22.6.2.1
    d_p = d_avg if tied else d_avg - t_top
    b1 = cL + d_p
    b2 = cB + d_p
    bo = 2.0 * (b1 + b2)
    A0c = min(b1, L0) * min(b2, B0)
    A1c = min(b1, L) * min(b2, B)
    Vu_p = Pu - P0e * A0c / A0 - dPu * A1c / A
    v_uv = Vu_p * 1000.0 / (bo * d_p)
    gamma_f_L = 1.0 / (1.0 + (2.0 / 3.0) * math.sqrt(b1 / b2))   # Eq. 8.4.2.2.2
    gamma_f_B = 1.0 / (1.0 + (2.0 / 3.0) * math.sqrt(b2 / b1))
    gamma_v_L = 1.0 - gamma_f_L                                  # Eq. 8.4.4.2.2
    gamma_v_B = 1.0 - gamma_f_B
    Jc_L = d_p * b1 ** 3 / 6.0 + b1 * d_p ** 3 / 6.0 + d_p * b2 * b1 ** 2 / 2.0
    Jc_B = d_p * b2 ** 3 / 6.0 + b2 * d_p ** 3 / 6.0 + d_p * b1 * b2 ** 2 / 2.0
    v_uM_L = gamma_v_L * abs(MuL) * 1e6 * (b1 / 2.0) / Jc_L
    v_uM_B = gamma_v_B * abs(MuB) * 1e6 * (b2 / 2.0) / Jc_B
    v_u = v_uv + v_uM_L + v_uM_B
    beta_c = max(cL, cB) / min(cL, cB)
    # Table 22.6.5.2 with lambda_s = 1.0 by 13.2.6.2(b)
    vc_a = 0.33 * lam * sqrt_fc
    vc_b = (0.17 + 0.33 / beta_c) * lam * sqrt_fc
    vc_c = (0.17 + 0.083 * alpha_s * d_p / bo) * lam * sqrt_fc
    v_c = min(vc_a, vc_b, vc_c)
    phi_vc = PHI_SHEAR * v_c
    punch_ratio = v_u / phi_vc
    punch_ok = v_u <= phi_vc

    # 6.0 Minimum reinforcement at the column - Eq. (8.6.1.2). Lightly
    # reinforced slabs punch when the bars near the column yield, below the
    # Table 22.6.5.2 strength. The trigger keeps the size effect factor of
    # 22.5.5.1.3: 13.2.6.2(b) lifts it from the strength, not from here.
    lam_s = min(1.0, math.sqrt(2.0 / (1.0 + d_p / 250.0)))
    v_trigger = PHI_SHEAR * 0.17 * sqrt_fc * lam_s * lam
    as2_applies = v_uv > v_trigger
    h_p = h if tied else h0
    for r, col, width0, width, As0, Asj in (
            (rL, cB, B0, B, As0_L, Asj_L), (rB, cL, L0, L, As0_B, Asj_B)):
        bslab = min(col + 3.0 * h_p, width)                 # 8.4.2.2.3
        in_wings = ((bslab - width0) / (width - width0)
                    if (width > width0 and bslab > width0) else 0.0)
        T_slab = (As0 * fy0 * min(1.0, bslab / width0)
                  + Asj * fyj * in_wings) / 1000.0           # kN
        T_slab_min = (5.0 * v_uv * bslab * bo / (PHI_SHEAR * alpha_s) / 1000.0
                      if as2_applies else 0.0)
        r.update({
            "bslab": bslab, "T_slab": T_slab, "T_slab_min": T_slab_min,
            "as2_ratio": T_slab_min / T_slab if T_slab > 0 else 0.0,
            "as2_ok": (not as2_applies) or T_slab >= T_slab_min,
        })

    d_min_ok = min(rL["d"], rB["d"]) >= D_MIN               # 13.3.1.2

    checks = [bearing_ok, contact_ok, contact_u_ok, punch_ok, tie_spacing_ok,
              surface_ok, d_min_ok]
    for r in (rL, rB):
        checks += [r["flex_ok"], r["As_min_ok"], r["as2_ok"], r["shear_ok"],
                   r["wflex_ok"], r["wAs_min_ok"], r["wshear_ok"], r["if_ok"],
                   r["ov_ok"]]
    overall_pass = all(checks)

    result = {
        # geometry and materials
        "B": B, "L": L, "h": h, "A0": A0 / 1e6, "A": A / 1e6,
        "fc": fc, "sqrt_fc": sqrt_fc, "beta1": _beta1(fc),
        "As0_L": As0_L, "As0_B": As0_B, "Asj_L": Asj_L, "Asj_B": Asj_B,
        "Asd_L": Asd_L, "Asd_B": Asd_B,
        "d0_L": d0_L, "d0_B": d0_B, "dj_L": dj_L, "dj_B": dj_B, "dd": dd,
        # load history
        "shored": shored, "P0e": P0e, "M0Le": M0Le, "M0Be": M0Be,
        "dP": dP, "dML": dML, "dMB": dMB,
        "dPu": dPu, "dMuL": dMuL, "dMuB": dMuB,
        # bearing
        "q0": qs["q0"], "q1": qs["q1"],
        "q_old_max": qs["old_max"], "q_wing_max": qs["wing_max"],
        "q_max": q_max, "q_min": q_min, "qa": qa,
        "bearing_ratio": bearing_ratio, "bearing_ok": bearing_ok,
        "contact_ok": contact_ok,
        "qu1": qu["q1"], "qu_old_max": qu["old_max"],
        "qu_wing_max": qu["wing_max"], "qu_min": qu_min,
        "contact_u_ok": contact_u_ok,
        # interfaces
        "surface": surface, "surface_ok": surface_ok, "lam": lam, "mu": mu,
        "fy_sf": fy_sf, "cap_stress": cap_stress,
        "overlay": overlay, "wings": wings, "tied": tied, "ties": ties,
        "bond_allowed": bond_allowed, "rho_v": rho_v,
        "rho_v_min": rho_v_min, "ties_min_ok": ties_min_ok,
        "vnh_a": vnh_a, "vnh_c": vnh_c, "vnh_sf": vnh_sf, "vnh": vnh,
        "s_tie_max": s_tie_max, "tie_spacing_ok": tie_spacing_ok,
        # two-way shear
        "column_engaged": column_engaged, "alpha_s": alpha_s,
        "d_avg": d_avg, "d_p": d_p, "b1": b1, "b2": b2, "bo": bo,
        "Vu_p": Vu_p, "v_uv": v_uv,
        "gamma_v_L": gamma_v_L, "gamma_v_B": gamma_v_B,
        "Jc_L": Jc_L, "Jc_B": Jc_B, "v_uM_L": v_uM_L, "v_uM_B": v_uM_B,
        "v_u": v_u, "beta_c": beta_c,
        "vc_a": vc_a, "vc_b": vc_b, "vc_c": vc_c, "v_c": v_c,
        "phi_vc": phi_vc, "punch_ratio": punch_ratio, "punch_ok": punch_ok,
        "lam_s": lam_s, "v_trigger": v_trigger, "as2_applies": as2_applies,
        "h_p": h_p, "d_min_ok": d_min_ok,
        "overall_pass": overall_pass,
        "not_checked": NOT_CHECKED,
    }
    for tag, r in (("L", rL), ("B", rB)):
        for key, value in r.items():
            result["%s_%s" % (key, tag)] = value
    return result
