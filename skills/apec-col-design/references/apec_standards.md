# APEC office standards — column, joint and footing defaults

These are **office practice or project inputs, not code** — mark them **(not vault-cited)** in any
report. They are mirrored in `scripts/design_column.py::DEFAULTS` and `scripts/footing.py::DEFAULTS`;
change both together. Every value can be overridden per member in the input JSON.
Items marked ⚠ are placeholders set when this skill was created (2026-09-28) — **confirm with Albert
and update this table.** Beam defaults stay in rc-design `references/apec_standards.md`.

## Columns

| Item | Default | JSON key | Source / status |
|---|---|---|---|
| f′c | 27.579 MPa (4 ksi) | `materials.fc` | same as rc-design |
| fy longitudinal | 413.686 MPa (Grade 60 / 420) | `materials.fy` | same as rc-design |
| fyt hoops | 275.79 MPa (Grade 40 / 280) | `materials.fyt` | ⚠ rc-design stirrup default; Grade 60 hoops are common in SMF — set per project |
| Clear cover to hoops | 40 mm | `section.cover` | NSCP Table 420.6.1.3.1 (4-136): 40 mm not exposed; 50 exposed D19+; 75 cast against earth |
| Hoop diameter used for bar edge distance | 10 mm | `section.dbt` | ⚠ placeholder; the designed hoop is reported separately |
| Max aggregate | 20 mm | `section.dagg` | ⚠ placeholder |
| Longitudinal bar sizes | 16, 20, 25, 28, 32, 36 mm | `design.bar_sizes` | ⚠ PH sizes in office use — confirm |
| Bars per face | ≥ 3 (SMF), ≥ 2 (gravity); ≤ 10 | `design.min_bars_per_face`, `max_bars_per_face` | 3 follows NIST GCR 8-917-1 printed 17 (3 legs per face) — guidance, not code |
| Hoop sizes tried | 10, 12, 16 mm | `design.hoop_sizes` | ⚠ placeholder; 12 mm minimum for D36+ (425.7.2.2) is enforced |
| Hoop spacing rounding | down to 25 mm; 10 mm below the practical minimum | `design.s_increment` | ⚠ placeholder |
| Practical minimum hoop spacing | 75 mm (WARN, then down to 50 mm if the code forces it) | `design.s_min` | ⚠ placeholder |
| Preferred spacing (tie-break only) | 100 mm | `design.s_target` | ⚠ placeholder |
| Hoop choice | least steel volume Σlegs·Ab/s; within 5 % → larger s | — | office choice |
| Bar layout choice | least Ast, then fewest bars, then larger bar | — | office choice |
| d for column shear | extreme bar layer (`actual`) | `design.shear_d` | W&M Ex 19-2; `0.8h` allowed (ACI 318-25M 22.5.2.1(a), conservative) |
| Vc in ℓo | code rule 418.7.6.2.1 | `design.vc_zero_in_lo` | `always` = W&M 7th “prudent” practice (printed 1075) |
| Beam-moment split to columns at a joint | DF = 0.5 | `joints.<end>.<Mx/My>.DF` | W&M Eq. (19-30); Moehle printed 566 warns it is unreliable low in the building |
| φ rule | `nscp2015` | `phi_rule` | CLAUSES.md Option A |
| Effective length factor k | 1.0 | `geometry.k` | ⚠ placeholder — SMF sway columns are k > 1; demands should be second-order |
| Demands from a second-order analysis | true | `geometry.second_order` | project fact — MIDAS P-Delta on/off (state it) |

## Load combinations

| Item | Default | JSON key | Source / status |
|---|---|---|---|
| f1 | 0.5 (1.0 for assembly, L > 4.8 kPa, garages) | `loads.f1` / `loads.public_assembly` | NSCP §203.3.1 (2-11) |
| ρ | 1.0 | `loads.rho` | APEC design criteria §3.6 (project); NSCP §208.6.1 bounds 1.0–1.25 for SMF |
| Ca, I | none — **must be given** when E cases exist | `loads.Ca`, `loads.I` | project seismic parameters (e.g. Ca = 0.523, I = 1.0 per APEC §3.6) |
| Ev senses | ± with every ±Eh | — | superset of the literal and ASCE readings (combos.py docstring) |
| Orthogonal 100 %/30 % | off | `loads.orthogonal` | turn ON for columns in two intersecting systems (§208.7.1) — SMF corner/interior columns |
| ASD set for footings | §203.4.1 basic + 0.6D rows for stability | `loads.alternate_asd`, `loads.stability_rows` | vault Design Procedures/02 |

## Footings

| Item | Default | JSON key | Source / status |
|---|---|---|---|
| f′c footing | 20.684 MPa (3 ksi) | `materials.fc` | ⚠ placeholder |
| q_allow (gross) | 150 kPa | `soil.q_allow` | ⚠ **geotechnical report value — never default it on a real job** |
| γ soil / γ concrete | 18 / 24 kN/m³ | `soil.gamma_soil`, `footing.gamma_c` | ⚠ placeholder |
| Df (base depth below grade) | 1.5 m | `soil.Df` | ⚠ project input |
| μ sliding | 0.35 | `soil.mu` | NSCP Table 304-1 row 3 (provisional 150 dpi read); give the geotech value |
| FS overturning / sliding | 1.5 / 1.5 | `soil.FS_overturning`, `soil.FS_sliding` | office practice; NSCP §304.1(e) delegates to the geotechnical report |
| Cover | 75 mm | `footing.cover` | Table 420.6.1.3.1 (4-136) |
| Plan step / thickness step | 50 mm / 50 mm; t ≥ 300 mm | `footing.increment`, `t_increment`, `t_min` | ⚠ placeholder |
| Bar sizes / spacing step / min | 16, 20, 25 / 25 mm / 100 mm | `footing.bar_sizes`, `s_increment`, `s_min` | ⚠ placeholder |
| Plan ratio L/B | 1.0 (square) | `footing.ratio` | ⚠ placeholder |
| Column case for αs | interior (40) | `footing.column_case` | isolated pad = interior (vault Design Procedures/04) |

## Member tags (drawings)

`C` column, `G` girder, `B` beam, `J` joint, `F` footing; floor–type–ID as in rc-design
(Albert Pamonag, 2026-08-04, vault Internal Learning/01).
