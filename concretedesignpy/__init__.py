__version__ = '0.10.0'

from .general import area_diam, steel_area, area_ratio
from .mgt import generateFIBERMGT

# v0.5.0 public API
from .calculators.moment_curvature import (
    moment_curvature_analysis,
    moment_curvature_advanced,
    moment_rotation_from_mphi,
    plastic_hinge_length,
    asce41_backbone_beam,
)
from .calculators.column_interaction import generate_interaction_diagram
from .calculators.column_biaxial import generate_biaxial_diagram
from .calculators.mander import confined_stress_strain
from .calculators.frp_flexure import frp_flexural_strengthening, get_env_reduction
from .calculators.frp_shear import frp_shear_strengthening

# v0.7.0 — RC column concrete jacketing (TN-RET-001, ACI 318-19 / ACI 562-16)
from .calculators.column_jacket_design import (
    column_jacket_design,
    build_jacketed_column,
    validate_jacket_request,
)
from .calculators.column_jacket import JacketedColumn

# Footing jacketing (ACI 562-25 / ACI 318-25M)
from .calculators.footing_jacket import footing_jacket_check
