# MIT License
# Copyright (c) Albert Pamonag Engineering Consultancy

"""
Beam Flexural Capacity Calculator
==================================

Computes nominal and ultimate moment capacity of RC beams
using an iterative neutral-axis solver with strain compatibility.

Governing edition
-----------------
**NSCP 2015** (equivalent to **ACI 318M-14**), the governing Philippine
code. This module previously claimed ACI 318-19; it never implemented it.
The difference that matters is the strength reduction factor: this module
uses the pre-2019 rule, tension-controlled at ``eps_t >= 0.005``, which is
NSCP 2015 / ACI 318-14. ACI 318-19 and 318-25 Table 21.2.2 replaced it
with ``eps_t >= eps_ty + 0.003``; for Grade 550 and 690 bars the two
differ by +7.5% and +15.5% on phi. Moving to that rule is an edition
change, deliberately not made here.

``beta1`` follows Table 22.2.2.4.3, including the ``f'c >= 55 -> 0.65``
floor, and is unchanged between the editions.

What this module does NOT check
-------------------------------
``calculate_beam_moment`` computes capacity. It does not certify a
section. It does not check:

* ``As,min``  -- Section 9.6.1.2 (ACI 318-25M printed 149)
* ``rho <= 0.025`` for special moment frames -- Section 18.6.3.1
* ``Mn+ >= 0.5 Mn-`` at a joint face -- Section 18.6.3.2
* bar spacing, cover, or development

Non-convergence raises ValueError rather than reporting a zero capacity.
"""

import math

from concretedesignpy.clause import clause
from concretedesignpy.calculators.moment_curvature import (
    polygon_area,
    polygon_centroid,
    polygon_width_at,
)


def _polygon_strip_area_and_centroid(vertices, y_lo, y_hi, n_strips=80):
    """Numerically integrate polygon area and y-centroid in [y_lo, y_hi]."""
    if y_hi <= y_lo:
        return 0.0, (y_lo + y_hi) / 2.0
    dy = (y_hi - y_lo) / n_strips
    a_total = 0.0
    ay_total = 0.0
    for i in range(n_strips):
        y_mid = y_lo + (i + 0.5) * dy
        wi = polygon_width_at(vertices, y_mid)
        ai = wi * dy
        a_total += ai
        ay_total += ai * y_mid
    if a_total <= 0:
        return 0.0, (y_lo + y_hi) / 2.0
    return a_total, ay_total / a_total


@clause("NSCP2015-422.2.2.4")
def _calculate_beta_one(fc):
    """Whitney stress block factor per NSCP 2015 Section 422.2.2.4.3."""
    if fc <= 17:
        return 0.85
    elif fc <= 28:
        return 0.85
    elif fc < 55:
        return max(0.85 - 0.05 * (fc - 28) / 7, 0.65)
    else:
        return 0.65


@clause("NSCP2015-421.2")
def _strength_reduction_factor(epsilon_t, epsilon_ty):
    """Strength reduction factor (phi) based on tensile strain."""
    if epsilon_t >= 0.005:
        return 0.90, "tension-controlled"
    elif epsilon_t <= epsilon_ty:
        return 0.65, "compression-controlled"
    else:
        phi = 0.65 + 0.25 * (epsilon_t - epsilon_ty) / (0.005 - epsilon_ty)
        return phi, "transition"


@clause("NSCP2015-422.2.2.4")
def calculate_beam_moment(
    rebar_list, fc, fy, b, h, es=200000.0,
    section_vertices=None,
    plate_top_thickness=0.0, plate_bottom_thickness=0.0,
    plate_fy=250.0, plate_es=200000.0,
):
    """
    Calculate moment capacity of an RC beam section.

    Parameters
    ----------
    rebar_list : list of dict
        Each dict has keys:
            - 'd': depth from top (mm)
            - 'diam': bar diameter (mm)
            - 'num': number of bars
    fc : float
        Concrete compressive strength (MPa).
    fy : float
        Steel yield strength (MPa).
    b : float
        Beam width (mm). For polygon sections this is the bbox width
        (used as fallback for plate widths if polygon-width lookup fails).
    h : float
        Beam total height (mm).
    es : float, optional
        Steel modulus of elasticity (MPa). Default 200000.
    section_vertices : list of (x, y) or None
        Optional polygon vertices in mm describing the concrete cross-section.
        When provided, the Whitney compression block uses the polygon area
        in the top `a` strip (instead of `a*b`). Width above NA is taken from
        the polygon. y=0 is the bottom; y=h the top.
    plate_top_thickness, plate_bottom_thickness : float
        External A36 steel plate thickness (mm) bonded above/below the section.
        Plate width = polygon top/bottom face width (or `b` for rectangular).
    plate_fy, plate_es : float
        Plate yield strength and modulus (MPa). Default A36.

    Returns
    -------
    dict
        Keys: neutral_axis, mn, mu, phi, classification, rebar_forces
    """
    if not rebar_list:
        raise ValueError("rebar_list must not be empty.")
    if fc <= 0 or fy <= 0 or b <= 0 or h <= 0:
        raise ValueError("fc, fy, b, h must all be positive.")

    beta1 = _calculate_beta_one(fc)
    epsilon_ty = fy / es
    ecu = 0.003

    use_polygon = section_vertices is not None and len(section_vertices) >= 3

    # Process rebar data
    rebars = []
    for bar in rebar_list:
        area = (math.pi / 4) * bar["diam"] ** 2 * bar["num"]
        rebars.append({"d": bar["d"], "area": area, "num": bar["num"], "diam": bar["diam"]})

    # External steel plates (A36) — modelled as virtual rebar layers
    # at depth-from-top d_plate. Top plate is "above" the polygon (negative d).
    plate_layers = []
    if plate_top_thickness > 0 or plate_bottom_thickness > 0:
        if use_polygon:
            xs = [v[0] for v in section_vertices]
            bbox_w = max(xs) - min(xs)
            if plate_top_thickness > 0:
                w_top = polygon_width_at(section_vertices, h - 1e-3) or bbox_w
                plate_layers.append({
                    "label": "Top Plate (A36)",
                    "d": -plate_top_thickness / 2.0,  # above polygon top
                    "thickness": plate_top_thickness,
                    "width": w_top,
                    "area": w_top * plate_top_thickness,
                    "fy": plate_fy,
                })
            if plate_bottom_thickness > 0:
                w_bot = polygon_width_at(section_vertices, 1e-3) or bbox_w
                plate_layers.append({
                    "label": "Bottom Plate (A36)",
                    "d": h + plate_bottom_thickness / 2.0,  # below polygon bottom
                    "thickness": plate_bottom_thickness,
                    "width": w_bot,
                    "area": w_bot * plate_bottom_thickness,
                    "fy": plate_fy,
                })
        else:
            if plate_top_thickness > 0:
                plate_layers.append({
                    "label": "Top Plate (A36)",
                    "d": -plate_top_thickness / 2.0,
                    "thickness": plate_top_thickness,
                    "width": b,
                    "area": b * plate_top_thickness,
                    "fy": plate_fy,
                })
            if plate_bottom_thickness > 0:
                plate_layers.append({
                    "label": "Bottom Plate (A36)",
                    "d": h + plate_bottom_thickness / 2.0,
                    "thickness": plate_bottom_thickness,
                    "width": b,
                    "area": b * plate_bottom_thickness,
                    "fy": plate_fy,
                })

    # d_max for c/dt ratio (extreme tension fibre — bottom plate if present)
    d_max = max(rb["d"] for rb in rebars)
    if plate_layers:
        d_max = max(d_max, max(pl["d"] for pl in plate_layers))

    # Helper: compute forces at a given neutral axis depth
    def _compute_forces(c_val):
        a_val = beta1 * c_val
        if use_polygon:
            y_lo = max(0.0, h - a_val)
            fc_area, y_centroid_compr = _polygon_strip_area_and_centroid(
                section_vertices, y_lo, h)
            fc_val = 0.85 * fc * fc_area
            d_compr = h - y_centroid_compr  # depth from top to compression centroid
        else:
            fc_val = 0.85 * fc * a_val * b
            d_compr = a_val / 2.0
        comp_steel = 0.0  # compression steel (absolute)
        tens_steel = 0.0  # tension steel
        fs_net = 0.0      # net steel force (tension positive)
        forces = []
        for rb in rebars:
            strain = ecu * (rb["d"] - c_val) / c_val
            stress = max(-fy, min(fy, strain * es))
            # Bars inside the Whitney block displace concrete that the
            # block has already counted at 0.85 f'c, so the compression
            # bar force is A's(f's - 0.85 f'c), not A's f's.
            # W&M Ex 4-4 step 5, printed 170:
            #   Cs = 3 x 1.00 in^2 x (43.5 - 3.42 ksi) = 120 kips.
            # Only bars above the neutral axis AND within depth a are
            # inside the block; a bar in compression but below a sits in
            # cracked concrete and displaces nothing.
            if stress < 0 and rb["d"] < a_val:
                stress += 0.85 * fc
                stress = min(stress, 0.0)
            force = stress * rb["area"]
            fs_net += force
            if force >= 0:
                tens_steel += force
            else:
                comp_steel += abs(force)
            forces.append({
                "d": rb["d"], "area": rb["area"],
                "num": rb["num"], "diam": rb["diam"],
                "strain": strain, "stress": stress, "force": force,
            })
        for pl in plate_layers:
            strain = ecu * (pl["d"] - c_val) / c_val
            stress = max(-pl["fy"], min(pl["fy"], strain * plate_es))
            force = stress * pl["area"]
            fs_net += force
            if force >= 0:
                tens_steel += force
            else:
                comp_steel += abs(force)
            forces.append({
                "d": pl["d"], "area": pl["area"],
                "num": 1, "diam": 0,
                "strain": strain, "stress": stress, "force": force,
                "label": pl["label"], "thickness": pl["thickness"],
                "width": pl["width"], "is_plate": True,
            })
        return fc_val, comp_steel, tens_steel, fs_net, forces, d_compr

    # Phase 1: coarse search for neutral axis
    iterations = []
    step_coarse = h * 0.02  # 2% of h per step
    c = h
    prev_ratio = None
    coarse_iter = 0

    while c > 0:
        fc_concrete, comp_steel, tens_steel, fs_net, _, _ = _compute_forces(c)
        # Ratio: (concrete compression + steel compression) / steel tension
        ratio = (fc_concrete + comp_steel) / tens_steel if tens_steel > 1e-9 else float('inf')
        coarse_iter += 1
        iterations.append({
            "iteration": coarse_iter,
            "c": round(c, 2),
            "c_dt": round(c / d_max, 2),
            "fc_kn": round(fc_concrete / 1000, 2),
            "ft_kn": round(comp_steel / 1000, 2),
            "fc_ft_kn": round((fc_concrete + comp_steel) / 1000, 2),
            "fs_kn": round(tens_steel / 1000, 2),
            "ratio": round(ratio, 3) if ratio != float('inf') else "Infinity",
        })

        if prev_ratio is not None and ratio <= 1.0 and prev_ratio > 1.0:
            break
        prev_ratio = ratio
        c -= step_coarse

    # Phase 2: fine refinement (0.32mm steps for precision)
    c_start = c + step_coarse
    step_fine = step_coarse / 50
    c = c_start
    fine_iter = 0

    converged = False
    for _ in range(int(step_coarse / step_fine) + 500):
        if c <= step_fine:
            break
        fc_concrete, comp_steel, tens_steel, fs_net, rebar_forces, d_compr = _compute_forces(c)
        ratio = (fc_concrete + comp_steel) / tens_steel if tens_steel > 1e-9 else float('inf')
        fine_iter += 1
        iterations.append({
            "iteration": fine_iter,
            "c": round(c, 2),
            "c_dt": round(c / d_max, 2),
            "fc_kn": round(fc_concrete / 1000, 2),
            "ft_kn": round(comp_steel / 1000, 2),
            "fc_ft_kn": round((fc_concrete + comp_steel) / 1000, 2),
            "fs_kn": round(tens_steel / 1000, 2),
            "ratio": round(ratio, 3) if ratio != float('inf') else "Infinity",
        })

        if abs(fc_concrete - fs_net) < 0.5:
            converged = True
            break
        if fc_concrete < fs_net:
            converged = True
            break
        c -= step_fine

    if not converged or c <= 1.0:
        raise ValueError(
            "No flexural equilibrium found at axial load = 0. The compression "
            "capacity (top plate / compression rebar / Whitney block) exceeds "
            "the available tension capacity. Try a thinner top plate, more "
            "tension rebar / a thicker bottom plate, or apply axial compression."
        )

    # Compute moment about the centroid of the concrete compression block
    a = beta1 * c
    mn = 0.0
    for rf in rebar_forces:
        mn += rf["force"] * (rf["d"] - d_compr)
    mn_knm = mn / 1e6

    # Tensile strain at extreme tension bar
    epsilon_t = ecu * (d_max - c) / c
    phi, classification = _strength_reduction_factor(epsilon_t, epsilon_ty)
    mu_knm = phi * mn_knm

    # Build rebar pattern summary (group by depth)
    rebar_pattern = []
    for bar in rebar_list:
        area = (math.pi / 4) * bar["diam"] ** 2 * bar["num"]
        rebar_pattern.append({
            "d": bar["d"],
            "diam": bar["diam"],
            "n": bar["num"],
            "as_mm2": round(area, 2),
        })

    section_info = {"type": "polygon" if use_polygon else "rectangular"}
    if use_polygon:
        section_info["vertices"] = [[round(x, 3), round(y, 3)]
                                    for x, y in section_vertices]
        section_info["area"] = round(polygon_area(section_vertices), 2)
        section_info["centroid_y"] = round(polygon_centroid(section_vertices)[1], 2)

    plates_info = None
    if plate_layers:
        plates_info = {"fy": plate_fy, "es": plate_es}
        for pl in plate_layers:
            key = "top" if pl["d"] < 0 else "bottom"
            plates_info[key] = {
                "thickness": pl["thickness"],
                "width": round(pl["width"], 2),
                "area": round(pl["area"], 2),
                "d": pl["d"],
            }

    return {
        "neutral_axis": round(c, 2),
        "a": round(a, 2),
        "beta1": round(beta1, 4),
        "d_compr": round(d_compr, 2),
        "mn": round(mn_knm, 2),
        "mu": round(mu_knm, 2),
        "phi": round(phi, 4),
        "classification": classification,
        "epsilon_t": round(epsilon_t, 6),
        "epsilon_ty": round(epsilon_ty, 6),
        "ecu": ecu,
        "d_max": d_max,
        "fc_concrete": round(fc_concrete / 1000, 2),
        "fs_total": round(fs_net / 1000, 2),
        "rebar_forces": rebar_forces,
        "rebar_pattern": rebar_pattern,
        "iterations": iterations,
        "section": section_info,
        "steel_plates": plates_info,
    }
