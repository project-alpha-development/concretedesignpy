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

### Masonry (CHB) — NSCP 2015 Ch.7 *(interim subpackage)*
- **Partition / infill (non-load-bearing)** — Table 204-2 wall weight, Fp per §208.9 (Table 208-13), §710.4 empirical h/t or l/t limit, §709.4.1.2–709.4.1.3 isolation and minimum steel; if the empirical limit fails, a reinforced ASD check picks the bar size and spacing, else the stiffener (RC column) spacing
- **Freestanding wall / fence** — wind per §207D (Case A body or Case C end zone), seismic per Table 208-13 (fences), unreinforced (empirical) or reinforced stem, footing overturning / sliding / bearing (Table 304-1, FS 1.5)
- **Reinforced wall, out of plane** — §708.2.4 slender-wall strength design with P-Δ, or §707.2 allowable stress design (stresses halved without special inspection)
- **Shear wall, in plane** — §708.2.5 axial, flexure (strain compatibility), shear, minimum steel
- **Existing walls** — f'm from §705.3.5 cut prisms or Table 705-1; knowledge factor κ (ASCE 41-17 §11.2.4) only when its inputs are given
- Every result lists each check's limit, ratio and pass/fail, and the vault clause notes it rests on. Provisions the code book does not support (unreinforced allowables on the missing p.7-31, Cd, the Table 708-1 Vn cap) are returned as `not_checked` with the reason, never guessed.

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
- **apec-provisions** (masonry only) — the Mind vault clause functions: `pip install -e ~/Desktop/Mind/03_Modelling/Python`. Without it the app still runs; `/api/masonry/*` returns 503.
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
│   ├── frp_flexure.py         # ACI 440.2R-17 Ch 10
│   ├── frp_shear.py           # ACI 440.2R-17 Ch 11
│   ├── joint_shear.py
│   ├── mander.py              # Confined concrete model
│   ├── moment_curvature.py    # M-phi analysis
│   ├── development_length.py  # Hook geometry
│   ├── alternative_inertia.py
│   ├── rebar_layout.py        # Section rebar coordinates
│   └── diagrams.py            # SVG diagram generators
├── masonry/              # CHB masonry, NSCP 2015 Ch.7 (self-contained; imports only the vault + clause.py)
│   ├── partition.py      # Non-load-bearing partitions / infill
│   ├── fence.py          # Freestanding walls: wind, seismic, stem, footing
│   ├── wall_oop.py       # Reinforced wall out of plane (SD / ASD), existing-wall mode
│   ├── wall_inplane.py   # Reinforced shear wall in plane (SD)
│   └── report.py         # One display equation per check
├── clause.py             # @clause tags linking functions to vault clause notes
├── webapp/
│   ├── app.py            # Flask application factory
│   ├── routes/           # API endpoints (beam, column, section, joint, mander, masonry)
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

Masonry: `POST /api/masonry/partition`, `/api/masonry/fence`, `/api/masonry/wall-oop`, `/api/masonry/wall-inplane` (JSON in, result with `checks`, `basis` and `report` out). Page: `/calculator/masonry`.

## Testing

```bash
python -m pytest
```

Masonry tests (`tests/test_masonry_*.py`) cover the engine, the routes, worked partition and fence examples with the hand calculation written in each docstring, and an import-seam test that fails if `concretedesignpy/masonry` imports from `concretedesignpy.calculators`. `tests/conftest.py` finds the vault package at `~/Desktop/Mind/03_Modelling/Python` (or `$APEC_PROVISIONS`) if it is not installed.

The suite covers the column jacketing modules. It distinguishes two kinds of
test, and the distinction matters when you add one:

- **Independent recomputation** — the expected value is derived from the code
  equation inside the test. These catch behaviour changing. Prefer them.
- **Regression pins** — a recorded value with a tight tolerance, used only
  where recomputation would mean reimplementing a layer integration. They would
  happily pin a bug, so they are labelled. If one fails, work out which
  behaviour changed before updating the number.

## Library Usage — Masonry Fence

```python
from concretedesignpy.masonry import fence, build_report

r = fence(dict(
    H_mm=2400, L_m=30, t_nom_mm=200, t_spec_mm=190, unit_density_kN_m3=16.5,
    grout="solid", plastered_faces=2, fm_MPa=10, fy_MPa=275, mortar="S",
    special_inspection=True, zone=4, Ca=0.44,               # required: no defaults
    V_kph=258.4, exposure="B", Kzt=1.0, wind_zone="body", method="SD",
    bar_db_mm=12, bar_s_mm=400,
    footing=dict(B_mm=1200, D_mm=300, Df_mm=900, soil_class=4, gamma_c_kN_m3=23.6)))
print(r["ok"], r["governing_ratio"])        # True 0.787
print(build_report(r)["status"])
```

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
