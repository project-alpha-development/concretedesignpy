# Input schema, units and sign conventions

Units everywhere: **kN, kN·m, mm, MPa** (footing plan in **m**, soil pressure in **kPa**).
Get a working file with `--template` from any script.

## Load cases — the heart of every input

Give each member its **UNFACTORED** forces per load case. The scripts build the NSCP 2015 §203
combinations themselves; nothing should arrive pre-factored.

```json
"loads": {"f1": 0.5, "rho": 1.0, "Ca": 0.523, "I": 1.0, "orthogonal": true},
"cases": {"D": {...}, "SDL": {...}, "L": {...}, "EX": {...}, "EY": {...}},
"case_types": {"SIDL": "D"}          // only for names the script cannot recognise
```

Case names are typed automatically — `D, DL, SW, SDL, SD` → D · `L, LL` → L · `LR, RLL` → Lr ·
`W*` → W · `E*, EQ*, RS*, SX, SY` → E · `H` → H · `F` → F · `T` → T · `R` → R. An unrecognised
name **raises** (it is never dropped silently). Several D cases are summed with the same factor.

- Give **one case per seismic direction** (EX, EY). The ± sign, Ev = ±0.5CaI·D and the 100/30
  orthogonal mix are generated. **Accidental torsion** belongs inside EX/EY from the analysis.
- **Response-spectrum** results are unsigned (CQC): P and M lose their relative sign. The ±
  permutation still covers them, but prefer the ELF (static) E cases for signed columns, or
  check the governing combination against the ELF signs.
- Pre-factored combinations may be added under `"combos": [{"name", "P", "Mx_top", …, "seismic"}]`
  — they are checked **in addition** and flagged as not verified against §203.

## Column (`design_column.py`)

```text
section    {"shape": "rect", "b", "h", "cover", "dbt"?, "edge"?, "dagg"?}
           {"shape": "circle", "D", "cover", "hoop": "spiral" | "circular"}
materials  {"fc", "fy", "fyt", "Es"?, "lam"?}
geometry   {"lu" (clear height, mm; required for SMF), "k"?, "second_order"?, "sway"?}
cases      {case: {"P", "Mx_top", "Mx_bot", "My_top", "My_bot", "Vx", "Vy"}}
bars       (check mode) {"db", "nx", "ny"} | {"db", "n"} | {"custom": [[x, y, db, A?], ...]}
hoops      (check mode) {"db", "legs_x", "legs_y", "s_lo", "s_mid"}   (circle: {"db", "s_lo", "s_mid"})
joints     {"top": {"Mx": {"Mnb": [sway+, sway-], "Mpr_b": value, "DF": 0.5},
                    "My": {...}, "column_other": {"P": [Pmin, Pmax]} | {"Mnc_x", "Mnc_y"}, "roof"?},
            "bottom": {"foundation": true} | {...same as top...}}
design     {"bar_sizes", "hoop_sizes", "min_bars_per_face", ..., "vc_zero_in_lo", "shear_d"}
frame      "SMF" (default) | "gravity";  phi_rule "nscp2015" | "aci318-19" | "aci318-25" | "envelope"
```

**Axes (W&M 7th Fig. 11-35).** Origin at the centroid; **x along the width b**, **y along the depth h**.

```text
            +y (depth h)
      ┌─────────────────┐      nx = bars on each face PARALLEL TO x (top and bottom faces)
      │  o     o     o  │      ny = bars on each face PARALLEL TO y (left and right faces)
      │                 │      total = 2nx + 2ny - 4
      │  o           o  │  +x (width b)
      │                 │      legs_x = tie legs running parallel to x -> resist Vx,
      │  o     o     o  │               confine across bc_y
      └─────────────────┘      legs_y = legs parallel to y -> resist Vy, confine across bc_x
```

- `P` positive in **compression**.
- `+Mx` compresses the **+y** face (bending across the depth h); `+My` compresses the **+x** face.
  For a doubly symmetric section only the magnitudes matter; for custom asymmetric layouts they do not.
- `Vx` acts along x and pairs with `My`; `Vy` acts along y and pairs with `Mx`.
- `_top` / `_bot` are the two ends of the **clear height** (joint faces).
- ⚠ *Software guidance, not vault-cited:* MIDAS Gen / ETABS report axial force **positive in
  tension** (flip the sign) and moments about the **element local** axes — map local 2/3 (y/z) to
  this skill's x/y with the column's beta angle, and check one hand-traced case before a batch run.

## Beam (`beam.py` → rc-design)

Everything rc-design accepts (`section`, `materials`, `span.L`, `columns.hc_i/hc_j`, `gravity.wD/wL`,
`service`, `bars`, `provided`), **plus**
`cases: {case: {"I": {"M", "V", "T"?, "N"?}, "M": {...}, "J": {...}}}` with **M > 0 sagging**.
The per-station envelope of the §203.3.1 combinations becomes rc-design's `demand`; its Ve gravity
load gets ev = 0.5CaI and fL = f1.

## Joint (`joint.py`)

```text
{"id", "direction", "fc", "fy", "lam"?,
 "column": {"b": perpendicular, "h": parallel to the beams},
 "beam_left" / "beam_right": {"b", "h", "top": [n, db] | [[n, db], ...], "bot": ..., "Mpr_neg"?, "Mpr_pos"?},
 "transverse_left_b"?, "transverse_right_b"?, "x_offset"?, "confined_faces"? (4 | 3 | "2opp" | "other"),
 "H_above", "H_below" | "Vcol", "beam_Ve"?, "column_hoops"?: {"s_lo"}}
```

## Footing (`footing.py`)

```text
{"id", "column": {"b", "h"}, "materials": {"fc", "fy"},
 "soil": {"q_allow", "gamma_soil", "Df", "mu" | "cohesive_kPa", "FS_overturning", "FS_sliding", ...},
 "footing": {"B"?, "L"?, "t"?, "ratio"?, "cover"?, "bar_sizes"?, "column_case"?, "pedestal_h"?},
 "cases": {case: {"P", "Mx", "My", "Vx", "Vy"}}   // column-base forces at the top of the footing
}
```
Omit `B`, `L`, `t` to size them. The footing self-weight and the soil above it are added as dead load
in the service set (gross pressure) and cancel in the factored (net) design.

## Project (`project.py`) — one run, one zip

```text
{"project", "loads", "materials": {"column": {...}, "beam": {...}, "footing": {...}}, "case_types"?,
 "beams":    [beam inputs with "id"],
 "columns":  [column inputs; joints may use "beam_ends": [["2G1", "J"], ["2G2", "I"]] instead of numbers],
 "joints":   [{"id", "column": "C1", "direction": "X"|"Y", "beam_left": {"beam": "2G1", "end": "J"},
               "beam_right": {...}, "transverse_left_b", "transverse_right_b", "H_above", "H_below"}],
 "footings": [{"id", "column": "C1", "soil": {...}, "footing": {...}}]}
```
`beam_ends` order is (left, right): sway + = Mn⁻(left) + Mn⁺(right). Beams along **X** give the
column's **My**; beams along **Y** give **Mx**. Output: `<out>/<project>/` + `<project>_results.zip`.
