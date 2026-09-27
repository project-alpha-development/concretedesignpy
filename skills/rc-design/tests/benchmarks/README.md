# Benchmarks

Run: `python3 ~/.claude/skills/rc-design/tests/run_benchmarks.py` — must print `ALL PASS`.

| File | Kind | What it pins |
|---|---|---|
| `apec_rcbeam_id25.json` | **past APEC beam** | rc-beam deck beam id 25 (400×800, 4-D25 / 4-D25): d, φMn, Mpr with A′s, Vpr |
| `wm_4_1m_flexure.json` | textbook | W&M 7th Ex 4-1M, singly reinforced |
| `wm_4_4_doubly.json` | textbook | W&M 7th Ex 4-4, doubly reinforced (displaced-concrete term) |
| `wm_6_1m_shear.json` | textbook | W&M 7th Ex 6-1M, Vc and stirrup spacing |
| `wm_7_2_torsion.json` | textbook | W&M 7th Ex 7-2, φTth, At/s, Al (1.7 Aoh divisor) |
| `dp05_crack_spacing.json` | vault worked value | Table 24.3.2 at cc = 75 mm → 192.5 mm |

Plus two guards: zero steel and an impossible demand must both FAIL.

**The APEC beam agrees to +0.2 %, not 0.0 %.** rc-beam's φMn / Mpr come from concretedesignpy's
stepped neutral-axis search (0.32 mm steps, stops at the first c where C < T); this skill
bisects to 1e-7 mm. The pins carry 0.5 % for that reason.

## ⚠ Open — 2 to 3 more past APEC beams needed

The layout asked for 3–4 past APEC beams. Only one with published numbers was reachable
(rc-beam id 25). To add one: copy `apec_rcbeam_id25.json`, fill section/bars/span and the
issued calc-sheet values under `expected`, and give the file a runner in `run_benchmarks.py`
(or reuse `apec_rcbeam` by naming it `apec_rcbeam_<id>.json` and adding it to `RUNNERS`).
Good candidates: a gravity girder with torsion, a deep (h > 900) transfer beam, a Grade 550 beam.
