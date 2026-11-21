# MIT License
# Copyright (c) Albert Pamonag Engineering Consultancy

"""
Calculator registry
===================

Single source of truth for the calculator directory. The landing page,
the sidebar navigation and the per-page breadcrumbs all render from this
list, so adding a calculator here is the only step needed to surface it
everywhere in the UI.

Icons are Lucide icon names (https://lucide.dev, ISC license).
"""

# Category display order for the sidebar and the landing page.
CATEGORIES = ["Beam", "Column", "Retrofit", "Joint", "Masonry", "Analysis",
              "Material", "Detailing"]

CALCULATORS = [
    {"id": "beam-moment", "name": "Beam Moment Capacity",
     "short": "Moment Capacity",
     "desc": "Flexural capacity with iterative neutral-axis solver",
     "ref": "NSCP 2015 §422.2", "category": "Beam", "icon": "trending-up"},
    {"id": "beam-shear", "name": "Beam Shear Design",
     "short": "Shear Design",
     "desc": "Concrete and stirrup shear capacity with spacing design",
     "ref": "ACI 318M-14", "category": "Beam", "icon": "scissors"},
    {"id": "beam-torsion", "name": "Beam Torsion Design",
     "short": "Torsion Design",
     "desc": "Combined shear-torsion interaction checks",
     "ref": "NSCP 2015 §422.7", "category": "Beam", "icon": "rotate-cw"},
    {"id": "beam-deflection", "name": "Beam Deflection",
     "short": "Deflection",
     "desc": "Immediate and long-term deflection with effective inertia",
     "ref": "NSCP 2015 §424.2", "category": "Beam", "icon": "trending-down"},
    {"id": "column-interaction", "name": "Column Design",
     "short": "P-M Interaction",
     "desc": "P-M / P-M-M interaction diagram with section layout",
     "ref": "NSCP 2015 / ACI 318-19", "category": "Column",
     "icon": "crosshair"},
    {"id": "column-flexural", "name": "Column Flexural Check",
     "short": "Flexural Check",
     "desc": "Minimum column-to-beam flexural strength ratio",
     "ref": "NSCP 2015 §418.7.3", "category": "Column",
     "icon": "bar-chart-2"},
    {"id": "column-jacket", "name": "Column Concrete Jacketing",
     "short": "Concrete Jacketing",
     "desc": "RC jacket on an existing column — P-M, confinement, "
             "shear, interface transfer",
     "ref": "ACI 318-19 / ACI 562-16", "category": "Retrofit",
     "icon": "layers"},
    {"id": "joint-shear", "name": "Joint Shear",
     "short": "Joint Shear",
     "desc": "Joint shear verification for special moment frames",
     "ref": "NSCP 2015 §418.8.4", "category": "Joint", "icon": "git-merge"},
    {"id": "masonry", "name": "Masonry (CHB) Walls",
     "short": "CHB Walls",
     "desc": "Partitions, fences, reinforced walls out of plane and in plane "
             "(interim home; vault clause functions)",
     "ref": "NSCP 2015 Ch.7", "category": "Masonry", "icon": "box"},
    {"id": "mander", "name": "Mander Confined Concrete",
     "short": "Mander Model",
     "desc": "Confined concrete strength and strain (Mander 1988)",
     "ref": "Mander et al. (1988)", "category": "Material", "icon": "box"},
    {"id": "development-length", "name": "Development Length",
     "short": "Development Length",
     "desc": "Hook geometry for deformed bars and stirrups",
     "ref": "NSCP 2015 §425", "category": "Detailing", "icon": "ruler"},
    {"id": "moment-curvature", "name": "Moment-Curvature",
     "short": "Moment-Curvature",
     "desc": "M-φ relationship, quick 6-point or incremental fiber",
     "ref": "NSCP 2015 / ACI 318-19", "category": "Analysis",
     "icon": "activity"},
    {"id": "alternative-inertia", "name": "Alternative Inertia",
     "short": "Alternative Inertia",
     "desc": "Effective moment of inertia, alternative method",
     "ref": "NSCP 2015 §424.2.3.5", "category": "Analysis",
     "icon": "sliders"},
]


def calculators_by_category():
    """Registry grouped by category, in CATEGORIES display order."""
    groups = []
    for cat in CATEGORIES:
        items = [c for c in CALCULATORS if c["category"] == cat]
        if items:
            groups.append({"category": cat, "items": items})
    return groups


def get_calculator(calc_id):
    """Registry entry for one calculator id, or None."""
    for c in CALCULATORS:
        if c["id"] == calc_id:
            return c
    return None
