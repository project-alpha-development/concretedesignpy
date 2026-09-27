# APEC office standards — bar sizes, cover, rounding

These are **office practice, not code** — mark them **(not vault-cited)** in any report.
They are mirrored in `scripts/design_beam.py::DEFAULTS`; change both together.
Every value can be overridden per beam in the input JSON.

Source of the carried values: `~/Desktop/Programs/rc-beam/AGENTS.md` "Locked-in design decisions"
(APEC's beam tool, reviewed in vault Software/03 and /12). Items marked ⚠ are placeholders set
when this skill was created (2026-09-27) — **confirm with Albert and update this table**.

| Item | Default | JSON key | Source / status |
|---|---|---|---|
| f′c | 27.579 MPa (4 ksi) | `materials.fc` | rc-beam default |
| fy main bars | 413.686 MPa (Grade 60 / 420) | `materials.fy` | rc-beam default |
| fyt stirrups | 275.79 MPa (Grade 40 / 280) | `materials.fyt` | rc-beam default |
| Clear cover to stirrup | 40 mm (interior beam) | `section.cover` | rc-beam default; code minimum Table 20.5.1.3.1, p. 421: 40 not exposed, 50 exposed D19+, 75 cast against earth |
| Stirrup diameter (for d) | 12 mm | `section.dbs` | rc-beam default |
| Max aggregate | 20 mm | `section.dagg` | ⚠ placeholder |
| Main bar sizes | 12, 16, 20, 25, 28, 32, 36 mm | `bars.main_sizes` | ⚠ PH deformed-bar sizes in office use — confirm list |
| Preferred main bar | D20 top and bottom | `bars.db_top`, `bars.db_bot` | ⚠ placeholder — set per project |
| Stirrup sizes tried | 10, 12, 16 mm | `bars.stirrup_sizes` | ⚠ placeholder |
| Stirrup legs (start) | 2 (more added for leg spacing / 350 mm rule) | `bars.n_legs` | rc-beam fallback used 4 legs Ø12 |
| Max bar layers | 2 | `bars.max_layers` | ⚠ placeholder |
| Vertical clear between layers | max(25 mm, db) | fixed in `flexure.face_layers` | code minimum is 25 mm (§25.2.2) — APEC uses the larger |
| Stirrup spacing rounding | round **down** to 25 mm | `bars.s_increment` | ⚠ placeholder |
| Minimum practical spacing | 75 mm | `bars.s_min` | ⚠ placeholder |
| Bar count rounding | round **up** to whole bars; every count scanned (φMn is not monotone in n) | — | rc-beam auto-sizer decision |
| φ rule | `nscp2015` | `phi_rule` | concretedesignpy CLAUSES.md Option A |
| Vg in Ve | (1.2 + ev)·wD + fL·wL on ln; ev = 0 unless given | `gravity.*` | Fig. R18.6.5 form; NSCP ev = 0.5 Ca I (§208.5.1.1, folio not vault-read) |
| Deflection Ie | envelope (smaller of Branson, Bischoff) | `service.ie_law` | conservative; see nscp_clauses.md |
| Sustained live fraction | 0.25 | `service.sustained_L` | ⚠ placeholder — project decision |
| Deflection limit case | ℓ/480 (attached, likely damaged) | `service.limit_case` | ⚠ strictest row of Table 24.2.2 by default |
| Member tag | `G` girder · `B` gravity beam · `2G1` = floor–type–ID | `id` | Albert Pamonag, 2026-08-04 (Internal Learning/01) |

## Drawing notes the report should carry (from the code, not office practice)

- SMF: hoops over **2h** from each column face, first hoop ≤ 50 mm, seismic hooks outside the zone
  (§18.6.4); no lap splice within a joint or within 2h of the face (§18.6.3.3).
- Torsion: closed stirrups; a longitudinal bar in every corner; side bars ≤ 300 mm (§9.7.5.1).
- Beam bar size sets the column depth: ≥ 20 db (Gr 420) through the joint (§18.8.2.3).
