# Changelog

## [0.1.0] — 2026-05-21

### Added

- `karamba_helper.py` — data extraction layer
  - `expand_load_combinations()` — expand Load-Case-Combinator groups to sub-LCs
  - `extract_element_forces()` — beam forces/moments via `BeamForces.solve()`
  - `extract_element_info()` — element id, type, length, section index
  - `extract_section_properties()` — full section geometry + moduli from CroSec
  - `extract_material()` — E, fy, fu, G from attached FemMaterial
  - Unit conversion constants: m→mm, m²→mm², m⁴→mm⁴, m³→mm³, m⁶→mm⁶, kN→N, kN·m→N·mm, kN/m²→MPa

- `code_checker.py` — GB50017-2017 steel design checks
  - `calc_alpha()` — buckling curve coefficients a/b/c/d (Annex D)
  - `calc_phi()` — stability reduction factor φ
  - `classify_section()` — Table 3.2 section classification (1–5) + buckling curve + γ factors
  - `compute_S_and_t()` — first moment of area S and shear thickness t for I/Box/CHS
  - `check_steel_element()` — main entry: 11 utilization checks per force state

### To-do

- [ ] LTB factor `φ_b` full calculation (GB50017 §6.2.2) — currently defaults to 1.0
- [ ] Welded I-section buckling curve assignment (needs `product` attribute from Karamba)
- [ ] Axial compression capacity `f` vs `fy` distinction (currently equal)
- [ ] Web classification under pure compression (currently bending limits only)
- [ ] Effective section properties for class 4/5 slender sections
- [ ] Verify CHS combined bending formula: `sqrt(My²+Mz²) / Iyy` vs `/ Wy`
- [ ] `el.node_inds` attribute access pattern confirmed from K3D API — verify at runtime
