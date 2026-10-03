# MIT License
#
# Copyright (c) Albert Pamonag Engineering Consultancy
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

"""
concretedesignpy.calculators
============================

Backend calculation modules for reinforced concrete design.
Extracted and consolidated from development notebooks.

Modules:
    - beam_moment: Beam flexural capacity (neutral axis solver)
    - beam_shear: Concrete and steel shear strength, and the single
      combined shear+torsion implementation (shear_torsion_design)
    - beam_deflection: Short-term and long-term deflection
    - frp_flexure: ACI 440.2R-17 Ch 10 FRP flexural strengthening
    - frp_shear: ACI 440.2R-17 Ch 11 FRP shear strengthening
    - column_interaction: P-M interaction diagram generation
    - column_flexural: Minimum flexural strength ratio check
    - column_jacket: RC column concrete jacketing engine (TN-RET-001)
    - column_jacket_design: Jacketing design report, units + advisories boundary
    - footing_jacket: Enlargement of an existing isolated footing
      (ACI 562-25 load history, ACI 318-25M strengths)
    - joint_shear: Joint shear verification for special moment frames
    - mander: Mander's confined concrete model
    - development_length: Hook geometry per NSCP 2015 Section 425
    - moment_curvature: M-phi, M-theta, ASCE 41 backbone curve
    - column_biaxial: P-M-M biaxial interaction surface (fiber approach)
    - rebar_layout: Rebar coordinate generation for rectangular sections
    - alternative_inertia: Alternative moment of inertia per NSCP 2015

Standards:
    NSCP 2015, ACI 318-19, ASCE 41-17, ACI 440.2R-17, ACI 562-16

    The edition is per module, not per package. beam_moment, beam_shear
    and joint_shear implement NSCP 2015 (= ACI 318M-14) and say so in
    their own docstrings; they are not ACI 318-19. The column_jacket
    modules are the ones written to ACI 318-19. footing_jacket is
    written to ACI 562-25 with ACI 318-25M as the design-basis code.
"""

from concretedesignpy.calculators.beam_moment import calculate_beam_moment
from concretedesignpy.calculators.beam_shear import (
    compute_concrete_shear_strength,
    compute_steel_shear_strength,
    compute_shear_spacing,
    shear_design,
    shear_torsion_design,
)
from concretedesignpy.calculators.beam_deflection import deflection_computation
from concretedesignpy.calculators.column_interaction import (
    generate_interaction_diagram,
)
from concretedesignpy.calculators.column_flexural import (
    check_min_flexural_strength,
)
from concretedesignpy.calculators.joint_shear import joint_shear_check
from concretedesignpy.calculators.mander import (
    confined_strength_ratio,
    confined_stress_strain,
)
from concretedesignpy.calculators.development_length import (
    bend_and_hook_deformed_bars,
    bend_and_hook_stirrups,
)
from concretedesignpy.calculators.moment_curvature import (
    moment_curvature_analysis,
    moment_curvature_advanced,
    moment_rotation_from_mphi,
    plastic_hinge_length,
    asce41_backbone_beam,
)
from concretedesignpy.calculators.column_biaxial import (
    generate_biaxial_diagram,
    check_biaxial_capacity,
    extract_contour_at_pu,
)
from concretedesignpy.calculators.rebar_layout import section_generate_rect
from concretedesignpy.calculators.alternative_inertia import (
    alternative_inertia_column_wall,
    alternative_inertia_beam_slab,
)
from concretedesignpy.calculators.frp_flexure import (
    frp_flexural_strengthening,
    get_env_reduction,
    ENV_REDUCTION,
    CREEP_RUPTURE_LIMIT,
)
from concretedesignpy.calculators.frp_shear import (
    frp_shear_strengthening,
)
from concretedesignpy.calculators.column_jacket import (
    Concrete,
    ConfinedConcrete,
    Steel,
    Bar,
    TieSet,
    JacketedColumn,
    rect_perimeter_bars,
    capacity_at_P,
    utilisation,
)
from concretedesignpy.calculators.column_jacket_design import (
    column_jacket_design,
    build_jacketed_column,
    validate_jacket_request,
)
from concretedesignpy.calculators.footing_jacket import (
    footing_jacket_check,
)
