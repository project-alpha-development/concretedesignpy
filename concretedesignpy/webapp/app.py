# MIT License
# Copyright (c) Albert Pamonag Engineering Consultancy

"""
Flask Application Factory
===========================

Creates and configures the Flask application with all
calculator route blueprints.
"""

from flask import Flask

import concretedesignpy
from concretedesignpy.webapp import nav
from concretedesignpy.webapp.routes import (
    main_bp,
    beam_bp,
    column_bp,
    column_jacket_bp,
    joint_bp,
    mander_bp,
    section_bp,
    masonry_bp,
)


def create_app():
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config["SECRET_KEY"] = "concretedesignpy-dev"

    app.register_blueprint(main_bp)
    app.register_blueprint(beam_bp, url_prefix="/api/beam")
    app.register_blueprint(column_bp, url_prefix="/api/column")
    app.register_blueprint(column_jacket_bp, url_prefix="/api/column-jacket")
    app.register_blueprint(joint_bp, url_prefix="/api/joint")
    app.register_blueprint(mander_bp, url_prefix="/api/mander")
    app.register_blueprint(section_bp, url_prefix="/api/section")
    app.register_blueprint(masonry_bp, url_prefix="/api/masonry")

    # The navbar badge used to be the literal string "v0.7 | NSCP 2015 /
    # ACI 318-19" in base.html. It went stale, and it was wrong on both
    # halves: the beam and joint modules are NSCP 2015 (= ACI 318M-14), not
    # 318-19. Injecting it means the version can no longer drift from
    # __init__, and the edition label lives in exactly one place.
    @app.context_processor
    def inject_version():
        return {
            "app_version": concretedesignpy.__version__,
            "code_basis_short": "NSCP 2015",
            "code_basis_long": (
                "NSCP 2015 (= ACI 318M-14) for beam flexure, shear, torsion "
                "and joint shear. The column jacketing and FRP modules "
                "target ACI 318-19 / ACI 562-16 / ACI 440.2R-17. The edition "
                "is per module -- see CLAUSES.md."
            ),
            # Sidebar navigation renders on every page from the registry.
            "nav_groups": nav.calculators_by_category(),
        }

    return app


def main():
    """Entry point for the console script."""
    import os
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("RAILWAY_ENVIRONMENT") is None
    app.run(debug=debug, host="0.0.0.0", port=port)
