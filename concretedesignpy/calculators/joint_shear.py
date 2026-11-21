# MIT License
# Copyright (c) Albert Pamonag Engineering Consultancy

"""
Joint Shear Verification
=========================

Verifies joint shear for special moment frames per
**NSCP 2015 Section 418.8.4** (equivalent to ACI 318M-14 Section 18.8.4).

Governing edition
-----------------
This module targets **NSCP 2015**, the governing Philippine code, whose
joint-shear provisions follow **ACI 318M-14**. It is NOT ACI 318-19/-25:
that edition replaced the three-row gamma table used here with the
eight-row Table 18.8.4.3. See NSCP_2015_TABLE_418_8_4_1 below.

Not checked here
----------------
Joint transverse reinforcement, development of beam bars into the joint,
and the column-to-beam flexural strength ratio.
"""

import math

from concretedesignpy.clause import clause

# NSCP 2015 Table 418.8.4.1 -- nominal joint shear strength Vn for special
# moment frames, in SI. Three rows, keyed on how many joint faces are
# confined by framing members.
#
#   1 : joints confined by beams on all four faces        gamma = 1.7
#   2 : joints confined on three faces or on two opposite faces  1.2
#   3 : other joints                                             1.0
#
# ACI 318-25M Table 18.8.4.3 (printed 342) replaced this with an
# EIGHT-row table keyed on column continuity (15.5.2.3) x beam continuity
# (15.5.2.4) x transverse-beam confinement (15.5.2.5):
#     1.7 / 1.3 / 1.3 / 1.0 / 1.3 / 1.0 / 1.0 / 0.7
# The middle value moved 1.2 -> 1.3 and a 0.7 row was added that this
# three-row enum has no slot for. Moving to that table changes every
# result and is deliberately NOT done here -- it is an edition change,
# not a defect fix.
NSCP_2015_TABLE_418_8_4_1 = {1: 1.7, 2: 1.2, 3: 1.0}

# ACI 318-25M Table 15.5.2.1 footnote [1], printed 231: "lambda shall be
# 0.75 for lightweight concrete and 1.0 for normalweight concrete."
# Two legal values, not a continuum.
LEGAL_LAMBDA = (0.75, 1.0)

# ACI 318-25M Section 21.2.4.4, printed 435: "For beam-column joints of
# special moment frames and diagonally reinforced coupling beams, phi for
# shear shall be 0.85." No caller discretion.
PHI_SMF_JOINT = 0.85


def _tension_force(as_bar, n_bars, fy, factor=1.25):
    """Probable tensile force in rebar group (kN). The 1.25 fy
    overstrength is Section 18.8.2.1."""
    return factor * n_bars * as_bar * fy / 1000.0


@clause("NSCP2015-418.8", "NSCP2015-421.2.4")
def joint_shear_check(
    ve, as1, n_bars1, as2, n_bars2, fy, fc,
    beam_width, joint_depth, *, column_width,
    perpendicular_dist=0,
    joint_config=1, lamda=1.0, phi=PHI_SMF_JOINT,
):
    """
    Joint shear verification for special moment frames.

    Parameters
    ----------
    ve : float
        Column shear (kN).
    as1 : float
        Area of one bar in group 1 (mm^2).
    n_bars1 : int
        Number of bars in group 1.
    as2 : float
        Area of one bar in group 2 (mm^2).
    n_bars2 : int
        Number of bars in group 2.
    fy : float
        Steel yield strength (MPa).
    fc : float
        Concrete compressive strength (MPa).
    beam_width : float
        Width of the beam, b (mm).
    joint_depth : float
        Overall depth of the column, h, in the direction of the joint
        shear considered (mm).
    column_width : float
        Overall width of the column perpendicular to the joint shear
        considered (mm). Keyword-only and required: without it the
        governing cap on Aj cannot be applied.
    perpendicular_dist : float
        Perpendicular distance from the column side face to the nearest
        beam edge, x (mm). Zero when the beam is flush with, or wider
        than, the column.

        NOTE for the next reader: this is measured **beam face to column
        face**, and that is deliberate. Section 15.5.2.2(b) is worded
        "twice the perpendicular distance from longitudinal axis of beam
        to nearest side face of the column", i.e. 2 * (b/2 + x), which is
        identically b + 2x. Fig. R15.5.2.2 draws the same limit as
        "b + 2x" with x face-measured. Do not "fix" this back to 2 * x.
    joint_config : int
        Row of NSCP 2015 Table 418.8.4.1 (a three-row table):
        1 = confined on all 4 faces (gamma 1.7),
        2 = confined on 3 or 2 opposite faces (gamma 1.2),
        3 = other (gamma 1.0).
        An unrecognised value raises rather than silently scoring 1.0.
    lamda : float
        Lightweight concrete factor. Must be 0.75 (lightweight) or
        1.0 (normalweight) -- these are the only two legal values.
    phi : float
        Strength reduction factor for shear. Fixed at 0.85 for
        special-moment-frame joints; passing anything else raises.

    Returns
    -------
    dict
        Keys: t1, t2, v_joint, joint_width, aj, vn, phi_vn, status

    Notes
    -----
    This function checks joint shear only. It does not check joint
    transverse reinforcement, bar development into the joint, or the
    column-to-beam flexural strength ratio.
    """
    if column_width <= 0:
        raise ValueError("column_width must be positive.")
    if lamda not in LEGAL_LAMBDA:
        raise ValueError(
            "lamda must be 0.75 (lightweight) or 1.0 (normalweight); "
            "got {!r}. ACI 318-25M Table 15.5.2.1 footnote [1], "
            "printed 231.".format(lamda)
        )
    if phi != PHI_SMF_JOINT:
        raise ValueError(
            "phi for special-moment-frame joint shear is fixed at {}; "
            "got {!r}. ACI 318-25M Section 21.2.4.4, printed 435, gives "
            "no caller discretion.".format(PHI_SMF_JOINT, phi)
        )
    if joint_config not in NSCP_2015_TABLE_418_8_4_1:
        raise ValueError(
            "joint_config must be 1, 2 or 3 (NSCP 2015 Table 418.8.4.1); "
            "got {!r}.".format(joint_config)
        )

    t1 = _tension_force(as1, n_bars1, fy)
    t2 = _tension_force(as2, n_bars2, fy)
    v_joint = t1 + t2 - ve

    # Effective joint area, Section 15.5.2.2.
    # "Effective joint width shall be the overall width of the column
    #  where the beam is wider than the column. Where the column is wider
    #  than the beam, effective joint width shall not exceed the lesser of
    #  (a) and (b)."  R15.5.2.2: "In no case is Aj greater than the column
    #  cross-sectional area."
    # Both sentences are satisfied by taking the least of the three.
    option_a = beam_width + joint_depth
    option_b = beam_width + 2 * perpendicular_dist
    joint_width = min(column_width, option_a, option_b)
    aj = joint_width * joint_depth

    # Joint shear strength factor, NSCP 2015 Table 418.8.4.1
    factor = NSCP_2015_TABLE_418_8_4_1[joint_config]

    vn = factor * lamda * math.sqrt(fc) * aj / 1000.0
    phi_vn = phi * vn

    compliant = phi_vn >= v_joint

    return {
        "t1": round(t1, 2),
        "t2": round(t2, 2),
        "v_joint": round(v_joint, 2),
        "joint_width": round(joint_width, 2),
        "column_width": column_width,
        "aj": round(aj, 2),
        "vn": round(vn, 2),
        "phi_vn": round(phi_vn, 2),
        "ve": ve,
        "joint_config": joint_config,
        "gamma": factor,
        "lamda": lamda,
        "phi": phi,
        "basis": "NSCP 2015 Table 418.8.4.1 (= ACI 318M-14)",
        "status": "OK" if compliant else "REINFORCEMENT REQUIRED",
    }
