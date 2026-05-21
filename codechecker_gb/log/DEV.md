# Dev Documentation — Karamba3D GB50017 Steel Checker

## Overview

Library for Rhino Grasshopper Python components. Extracts beam forces, section
properties, and materials from a Karamba3D model, then runs GB50017-2017 steel
design checks per element per load case.

**Two modules:** `karamba_helper.py` (extraction) and `code_checker.py` (checks).

---

## Environment

- **Runtime:** Rhino 8 + Grasshopper, IronPython 2.7 (.NET interop)
- **Dependency:** Karamba3D 3.1.4 (or compatible)
- **No external PyPI packages.** Uses `math`, `re`, and Karamba .NET assemblies.
- **Cannot run standalone** — Karamba objects exist only inside the Rhino process.

## Installation

Add the project folder to Rhino's Python search path:

```python
import sys
sys.path.append(r"F:\00 PRODUCTION\0001_RD\2026_karamba3d_steel check_chn\codechecker_gb")
```

---

## Module: `karamba_helper.py`

### Unit conventions

| Quantity | Karamba internal | GB50017 working |
|---|---|---|
| Length | m | mm (×10³) |
| Area | m² | mm² (×10⁶) |
| Moment of inertia | m⁴ | mm⁴ (×10¹²) |
| Section modulus | m³ | mm³ (×10⁹) |
| Warping constant | m⁶ | mm⁶ (×10¹⁸) |
| Force | kN | N (×10³) |
| Moment | kN·m | N·mm (×10⁶) |
| Stress (E, fy) | kN/m² | MPa (×10⁻³) |

**Rule:** `extract_element_forces()` returns native kN/kN·m. Conversion to N/N·mm
happens inside `check_steel_element()`. All section/material properties are
converted to mm/MPa at extraction time.

### Data flow

```
Karamba Model
     │
     ├─ expand_load_combinations(model, ['ULS'])  → [(lc_name, factors), …]
     ├─ extract_element_info(model)                → [{id, type, length, sec_index}, …]
     │
     ├─ for sec in model.crosecs:                 ─┐ cached once
     │     extract_section_properties(sec)          │
     │     extract_material(sec)                   ─┘
     │
     └─ extract_element_forces(model, ids, lc_names)
          → {lc: [[{N,Vy,Vz,Mx,My,Mz} per pos] per elem]}
```

### Functions

#### `expand_load_combinations(model, comb_names)`

Queries `model.lcActivation.TryGetLoadCaseCombination()` for each group name.
Returns flat list of `(lc_name, factors_dict)`.

The Load-Case-Combinator syntax (`&`, `|`, `+`, `-`, regex) is handled by
Karamba internally; this function only reads the expanded results.

#### `extract_element_forces(model, elem_ids, lc_names, n_positions=5)`

Calls `Karamba.Results.BeamForces.solve(model, List[String], lcName, maxDist, nIntervals)`.

Returns 3D dict: `results[lc][elem_idx][pos_idx] = {'N': …, 'Vy': …, …}`.

Forces are in **global coordinates**:
- X = axial (N)
- Y = shear local-y (Vy)
- Z = shear local-z (Vz)
- Mx = torsion
- My = strong-axis bending
- Mz = weak-axis bending

#### `extract_element_info(model)`

Iterates `model.Elements()`. Builds section mapping by matching element IDs
against `CroSec.elemIds` patterns (supports exact match and regex).

Element length is computed as the straight-line distance between start and end
nodes: `|pos(n1) - pos(n0)| × M_TO_MM`.

Confirmed from K3D API: `element.node_inds` → `IReadOnlyList<int>`.

#### `extract_section_properties(crosec)`

Takes a **single** CroSec object. Calls `calculateProperties()` then reads all
available attributes. Returns a plain dict.

Recommended usage: extract all sections once, cache in a list, index by
`elem_info['sec_index']` at check time.

#### `extract_material(crosec)`

Reads `crosec.material` (FemMaterial). Calls `E(0)`, `G12()`, `fy(0)`, `fu(0)`,
`nue12()`, `gamma()`. Returns dict with values in MPa.

---

## Module: `code_checker.py`

### GB50017 equation references

| Check | Clause | Formula |
|---|---|---|
| Axial stress | §7.1.1 | σ = N / A |
| Bending stress | §6.1.1 | σ = M / (γ·W) |
| Shear stress | §6.1.3 | τ = V·S / (I·t) |
| Combined axial+bending | §8.2.1 | σ = σ_N + σ_My + σ_Mz |
| Flexural buckling | §7.2.1 | σ = N / (φ·A) |
| Combined buckling (y) | §8.2.5 | σ = N/(φ_y·A) + β·My/(γ_y·Wy·(1-0.8·N/N_Ey)) + η·β·Mz/(φ_b·Wz) |
| Combined buckling (z) | §8.2.5 | σ = N/(φ_z·A) + β·Mz/(γ_z·Wz·(1-0.8·N/N_Ez)) + η·β·My/(φ_b·Wy) |

### Buckling curves (Annex D)

| Curve | α₁ | α₂ | α₃ (λ_n ≤ 1.05) | α₃ (λ_n > 1.05) |
|---|---|---|---|---|
| a | 0.41 | 0.986 | 0.152 | 0.152 |
| b | 0.65 | 0.965 | 0.300 | 0.300 |
| c | 0.73 | 0.906 | 0.595 | 0.302 |
| d | 1.35 | 0.868 | 0.915 | 0.432 |

φ formula (λ_n ≤ 0.215): φ = 1 − α₁·λ_n²
φ formula (λ_n > 0.215): φ = (t − √(t² − 4λ_n²)) / (2λ_n²)  where t = α₂ + α₃·λ_n + λ_n²

### Section classification (Table 3.2)

**I-section flange** (outstand element, free edge): b' = (b_f − t_w) / 2

| Class | Limit | γ |
|---|---|---|
| S1 | b'/t_f ≤ 9ε_k | 1.05 |
| S2 | b'/t_f ≤ 11ε_k | 1.05 |
| S3 | b'/t_f ≤ 13ε_k | 1.0 |
| S4 | b'/t_f ≤ 15ε_k | 1.0 |
| S5 | b'/t_f > 15ε_k | — |

where ε_k = √(235/fy)

**I-section web** (internal element, bending): h₀ = height − t_f_top − t_f_bot

| Class | Limit |
|---|---|
| S1 | h₀/t_w ≤ 33ε_k |
| S2 | h₀/t_w ≤ 38ε_k |
| S3 | h₀/t_w ≤ 42ε_k |
| S4 | h₀/t_w ≤ 45ε_k |

**Buckling curve assignment** (Table D.0.1, hot-rolled I, t_f ≤ 40mm):
- Strong axis (y): a if b/h ≤ 0.8, else b
- Weak axis (z): b

### Return dict keys

`check_steel_element()` returns a dict with these keys:

| Key | Clause | Passes if ≤ 1.0 |
|---|---|---|
| `σ_N` | §7.1.1 | Axial strength |
| `σ_My` | §6.1.1 | Strong-axis bending |
| `σ_Mz` | §6.1.1 | Weak-axis bending |
| `σ_Myz` | §6.1.1 | Combined biaxial bending |
| `τ_Vy` | §6.1.3 | Shear, strong-axis |
| `τ_Vz` | §6.1.3 | Shear, weak-axis |
| `σ_NMyz` | §8.2.1 | Axial + biaxial bending |
| `σ_Ny_buckling` | §7.2.1 | Flexural buckling, y |
| `σ_Nz_buckling` | §7.2.1 | Flexural buckling, z |
| `σ_NMyz_buckling` | §8.2.5 | Combined buckling, y-dominant |
| `σ_NMzy_buckling` | §8.2.5 | Combined buckling, z-dominant |
| `λ_y` | — | Slenderness ratio, strong axis |
| `λ_z` | — | Slenderness ratio, weak axis |
| `class_overall` | §3.2 | Section class 1–5 |
| `warning` | — | Non-empty if slenderness exceeds limit |

### Usage example (Grasshopper Python component)

```python
import sys
sys.path.append(r"F:\00 PRODUCTION\0001_RD\2026_karamba3d_steel check_chn\codechecker_gb")

from System.Collections.Generic import List
from System import String
from karamba_helper import *
from code_checker import *

model = Model_in.Clone()

# --- setup: extract once, cache ---
all_sec  = [extract_section_properties(sec) for sec in model.crosecs]
all_mat  = [extract_material(sec) for sec in model.crosecs]
elem_inf = extract_element_info(model)
sub_lc   = expand_load_combinations(model, ['ULS'])
lc_names = [n for n, _ in sub_lc]

elem_ids = List[String]([el['id'] for el in elem_inf])
forces   = extract_element_forces(model, elem_ids, lc_names, n_positions=5)

# --- per-element check (at most stressed position) ---
for ei, elem in enumerate(elem_inf):
    si = elem['sec_index']
    sec = all_sec[si]
    mat = all_mat[si]
    L   = elem['length']  # or effective length

    for lc_name, _ in sub_lc:
        f_per_pos = forces[lc_name][ei]
        # find governing position (max utilization → focus on combined buckling)
        worst = max(f_per_pos,
                    key=lambda f: check_steel_element(sec, mat, L, L, f)['σ_NMyz_buckling'])
        result = check_steel_element(sec, mat, L, L, worst)
        max_ur = max(v for k, v in result.items() if k.startswith('σ_') or k.startswith('τ_'))
        print(f"  {elem['id']} @ {lc_name}:  max UR = {max_ur:.3f}")
```

---

## Testing

Scripts in `raw/` are for interactive testing in Grasshopper:

| Script | What it tests |
|---|---|
| `karamba_extract element loads.py` | BeamForces.solve() API, LCC expansion |
| `karamba_extract loads.py` | Alternative force extraction approach |
| `karamba_sec_properties.py` | extract_section_properties() prototype |
| `check props.py` | Full section property dump with units |
| `steelcheck.py` | Reference GB50017 implementation (pandas-based) |

---

## Scope / out of scope

**In scope (v0.1):**
- I-sections, box/RHS sections, CHS
- Hot-rolled sections (buckling curves a/b)
- GB50017 §6.1.1, §6.1.3, §7.1.1, §7.2.1, §8.2.1, §8.2.5
- Utilization ratios with configurable γ_RE

**Out of scope (future):**
- Welded I-section buckling curves (needs `product` attribute mapping)
- Full φ_b lateral-torsional buckling calc (§6.2.2)
- Effective section properties for class 4/5 (§5.6)
- Seismic provisions
- Fire design
- Fatigue
- Connection design
