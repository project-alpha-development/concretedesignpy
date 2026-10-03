# ConcreteDesignPy

[![PyPI version](https://img.shields.io/pypi/v/concretedesignpy)](https://pypi.org/project/concretedesignpy/)
[![Python](https://img.shields.io/pypi/pyversions/concretedesignpy)](https://pypi.org/project/concretedesignpy/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![GitHub release](https://img.shields.io/github/v/release/albertp16/concretedesignpy)](https://github.com/albertp16/concretedesignpy/releases)
[![GitHub issues](https://img.shields.io/github/issues/albertp16/concretedesignpy)](https://github.com/albertp16/concretedesignpy/issues)

A Python library and web application for reinforced concrete structural design per **NSCP 2015** and **ACI 318-19**.

> **Disclaimer:** This is an internal tool for Albert Pamonag Engineering Consultancy (APEC). All results must be verified by a licensed professional engineer. The developers assume no liability for errors or misuse.

## Features

### Beam Design
- **Flexural Capacity** — Strain compatibility method with iterative neutral axis solver, strength reduction factor (phi) plot per ACI 318-19 Table 21.2.2
- **Shear Strength** — Concrete and steel shear capacity, stirrup spacing design with Excel export (ACI 318M-14)
- **Torsion Design** — Combined shear-torsion interaction checks
- **Deflection** — Immediate and long-term deflection with effective moment of inertia

### Column Design
- **P-M Interaction** — Strain compatibility analysis with Plotly interaction diagrams, load combination overlay
- **Minimum Flexural Strength** — Column-to-beam strength ratio verification

### Analysis Tools
- **Moment-Curvature** — Dual-mode M-phi analysis:
  - *Quick (6-Point)* — Closed-form key points (cracking, yield, ultimate) per ACI 318-19
  - *Advanced (Incremental)* — Hognestad parabolic concrete model with fiber-layer approach, axial load support, 60-point smooth curve
- **Mander Confined Concrete** — Full Mander, Priestley & Park (1988) model with 13-step transparent report, biaxial confinement (Fig. 5), Plotly stress-strain curves, and confinement effectiveness charts
- **Joint Shear** — Verification for special moment frames (Section 422.7)

### Retrofitting & Strengthening
- **RC Column Concrete Jacketing** — Four-sided cast-in-place jacket on an existing rectangular column, per TN-RET-001 / ACI 318-19 / ACI 562-16. P-M interaction with a single stress block (β₁ from the extreme compression fibre), Mander confinement with k_e computed from the actual tie and bar geometry, one-way shear, interface shear transfer (both ACI capacity routes reported, neither chosen), unshored-jacket preload split, stiffness feedback, detailing checks, and Lampropoulos et al. (2012) monolithic coefficients reported but never applied. Every result carries provenance and an `advisories` list. Partial (one/two/three-sided) jackets compute their geometry and P-M curve and *declare* the checks that have no model rather than answering with four-sided behaviour
- **FRP Strengthening** — Externally bonded flexural (ACI 440.2R-17 Ch 10) and shear (Ch 11) strengthening with a 20-iteration Hognestad neutral-axis solver, debonding strain, and service stress checks

### Detailing
- **Development Length** — Hook geometry for deformed bars and stirrups (Section 425)
- **Alternative Inertia** — Effective moment of inertia per Section 424.2.3.5

### Web Application
- Flask-based interactive calculators
- Plotly charts for all visualizations (M-phi diagrams, P-M interaction, stress-strain curves, section analysis)
- MathJax-rendered calculation reports with full formula substitution
- Print-ready output with engineering notation

## Installation

```bash
pip install -e .
```

### Dependencies

- Python 3.8+
- Flask
- NumPy
- Gunicorn (production)
- openpyxl

## Running Locally

```bash
python run.py
```

Then open [http://localhost:5000](http://localhost:5000) in your browser.

## Project Structure

```
concretedesignpy/
├── calculators/          # Backend calculation modules
│   ├── beam_moment.py    # Flexural capacity (neutral axis solver)
│   ├── beam_shear.py     # Concrete & steel shear strength
│   ├── beam_deflection.py
│   ├── column_interaction.py  # P-M interaction diagram
│   ├── column_flexural.py     # Min flexural strength ratio
│   ├── column_jacket.py       # RC jacketing engine (mm/MPa/N, vendored)
│   ├── column_jacket_design.py # Jacketing report: units + advisories boundary
│   ├── footing_jacket.py      # Footing enlargement (ACI 562-25 / ACI 318-25M)
│   ├── frp_flexure.py         # ACI 440.2R-17 Ch 10
│   ├── frp_shear.py           # ACI 440.2R-17 Ch 11
│   ├── joint_shear.py
│   ├── mander.py              # Confined concrete model
│   ├── moment_curvature.py    # M-phi analysis
│   ├── development_length.py  # Hook geometry
│   ├── alternative_inertia.py
│   ├── rebar_layout.py        # Section rebar coordinates
│   └── diagrams.py            # SVG diagram generators
├── webapp/
│   ├── app.py            # Flask application factory
│   ├── routes/           # API endpoints (beam, column, section, joint, mander)
│   ├── templates/        # Jinja2 HTML templates with MathJax
│   └── static/           # CSS & JavaScript
├── tests/                # pytest suite
├── Procfile              # Railway/Heroku deployment
├── railway.json          # Railway config
├── requirements.txt      # Python dependencies
└── setup.py              # Package setup
```

## API Endpoints

See the [Wiki — API Reference](https://github.com/albertp16/concretedesignpy/wiki/API-Reference) for the full list of 17 POST endpoints.

## Testing

```bash
python -m pytest
```

The suite covers the column jacketing modules. It distinguishes two kinds of
test, and the distinction matters when you add one:

- **Independent recomputation** — the expected value is derived from the code
  equation inside the test. These catch behaviour changing. Prefer them.
- **Regression pins** — a recorded value with a tight tolerance, used only
  where recomputation would mean reimplementing a layer integration. They would
  happily pin a bug, so they are labelled. If one fails, work out which
  behaviour changed before updating the number.

## Library Usage — Column Jacketing

```python
from concretedesignpy import column_jacket_design

report = column_jacket_design(
    existing=dict(width=400, depth=400, fc=21, fy=275, bar_dia=20,
                  bars_per_face_width=3, bars_per_face_depth=3,
                  cover_to_bar_centre=50),
    jacket=dict(thickness=100, fc=28, fy=415, bar_dia=20,
                bars_per_face_width=4, bars_per_face_depth=4,
                tie_dia=12, tie_spacing=100, tie_fy=275,
                bars_restrained_per_face=2),
    demand=dict(Pu=3200, Mu=520, Vu=300, clear_height=2800),
    construction=dict(P0_at_casting=900, P_service=2240,
                      continuity="discontinuous"),
)

report["interaction"]["phiMn_at_Pu_jacketed"]   # 535.2 kN-m
report["adequate"]                              # computed checks only
for a in report["advisories"]:                  # part of the answer
    print(a["severity"], a["code"])
```

Forces are **kN** and moments **kN-m** at this boundary; the engine underneath
works in N and N-mm. `adequate` is a statement about the *computed checks
only* — it is deliberately not called `safe`. Read the advisories: each one is
an engineering trap the arithmetic cannot rule out, and a caller that renders
only the DCRs is using the module wrong.

## Code Standards & References

- **NSCP 2015** — National Structural Code of the Philippines
- **ACI 318-19 / ACI 318M-14** — American Concrete Institute
- **ACI 562-16** — Evaluation, Repair, and Rehabilitation of Existing Concrete Structures (interface bond, §7.3–7.4)
- **ACI 440.2R-17** — Externally Bonded FRP Systems
- **ACI SP-17** — Design Handbook
- **Mander, Priestley & Park (1988)** — Theoretical stress-strain model for confined concrete, *J. Structural Engineering*, ASCE, Vol. 114, No. 8
- **fib Bulletin 14 (2001)** — Confined concrete equations (6-3), (6-5), (6-34)–(6-36) as printed
- **Lampropoulos, Tsioulou & Dritsos (2012)** — Monolithic coefficients for jacketed columns, *J. Earthquake Engineering* 16(7):1023–1042, Tables 2–5
- **Hognestad (1951)** — A study of combined bending and axial load in reinforced concrete members, University of Illinois Bulletin No. 399

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature-name`)
3. Commit your changes
4. Submit a pull request

## License

MIT License. See [LICENSE](LICENSE) for details.
