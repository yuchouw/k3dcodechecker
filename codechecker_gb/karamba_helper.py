"""
Karamba3D helper utilities for GB50017 steel design checks.

Extracts forces, element info, section properties, and materials from a
Karamba3D model.  All output is in GB50017 working units (mm, N, MPa) except
extract_element_forces() which returns native Karamba units (kN, kN·m).
"""

M_TO_MM      = 1e3       # m  → mm
M2_TO_MM2    = 1e6       # m² → mm²
M3_TO_MM3    = 1e9       # m³ → mm³
M4_TO_MM4    = 1e12      # m⁴ → mm⁴
M6_TO_MM6    = 1e18      # m⁶ → mm⁶
KN_TO_N      = 1e3       # kN → N
KNM_TO_NMM   = 1e6       # kN·m → N·mm
KN_M2_TO_MPA = 1e-3      # kN/m² → MPa (N/mm²)

import re
import warnings
from Karamba.Elements import BuilderElementStraightLine


# ============================================================================
#  Load combination expansion
# ============================================================================

def expand_load_combinations(model, comb_names):
    sub_lcs = []
    for cn in comb_names:
        success, lcc = model.lcActivation.TryGetLoadCaseCombination(cn)
        if not success or lcc is None:
            continue
        for sub_lc in lcc.LoadCases:
            facs = {}
            for key in sub_lc.factors.Keys:
                facs[key] = sub_lc.factors[key]
            sub_lcs.append((sub_lc.Name, facs))
    return sub_lcs


# ============================================================================
#  Element info extraction
# ============================================================================

def extract_element_length(el):
    bklY = el.buckling_length(BuilderElementStraightLine.BucklingDir.bklY) * M_TO_MM
    bklZ = el.buckling_length(BuilderElementStraightLine.BucklingDir.bklZ) * M_TO_MM
    bklLT = el.buckling_length(BuilderElementStraightLine.BucklingDir.bklLT) * M_TO_MM
    
    if any(l < 0 for l in (bklY, bklZ, bklLT)):
        warnings.warn(
            f"Element '{el.id}': negative buckling length detected (bklY={bklY:.0f}, "
            f"bklZ={bklZ:.0f}, bklLT={bklLT:.0f}). Karamba auto-calculated these; "
            f"using abs() values."
        )
        bklY, bklZ, bklLT = abs(bklY), abs(bklZ), abs(bklLT)

    return {
        'ind':      el.ind,
        'bklY':     bklY,
        'bklZ':     bklZ,
        'bklLT':    bklLT
    }


# ============================================================================
#  Section properties  (units = mm / mm² / mm⁴ / mm³)
# ============================================================================
def extract_section_properties(crosec):
    props = {}

    props['fe_ind'] = crosec.fe_ind(0)
    props['section_type'] = type(crosec).__name__

    props['material'] = extract_material(crosec.material)

    for attr in ('name', 'family', 'familyID', 'IsValid', 'isPlausible', 'product'):
        if hasattr(crosec, attr):
            props[attr] = getattr(crosec, attr)

    for attr in ('lf_width', 'uf_width', 'lf_thick', 'uf_thick', 'w_thick'):
        if hasattr(crosec, attr):
            val = getattr(crosec, attr)
            if isinstance(val, (int, float)):
                props[attr] = val * M_TO_MM

    for attr in ('_height', 'height'):
        if hasattr(crosec, attr):
            val = getattr(crosec, attr)
            if isinstance(val, (int, float)):
                props['height'] = val * M_TO_MM
                break

    for attr in ('A', 'Ay', 'Az'):
        if hasattr(crosec, attr):
            props[attr] = getattr(crosec, attr) * M2_TO_MM2

    for attr in ('Iyy', 'Izz', 'Ipp'):
        if hasattr(crosec, attr):
            props[attr] = getattr(crosec, attr) * M4_TO_MM4

    if hasattr(crosec, 'Cw'):
        props['Cw'] = crosec.Cw * M6_TO_MM6

    for attr in ('iy', 'iz'):
        if hasattr(crosec, attr):
            props[attr] = getattr(crosec, attr) * M_TO_MM

    for attr in ('Wely_z_pos', 'Wely_z_neg', 'Welz_y_pos', 'Welz_y_neg'):
        if hasattr(crosec, attr):
            props[attr] = getattr(crosec, attr) * M3_TO_MM3

    for attr in ('Wply', 'Wplz', 'Wt'):
        if hasattr(crosec, attr):
            props[attr] = getattr(crosec, attr) * M3_TO_MM3

    if hasattr(crosec, 'ecce_loc'):
        props['ecce_loc'] = crosec.ecce_loc * M_TO_MM

    return props

def extract_material(mat):
    props = {
        'name':   mat.name    if hasattr(mat, 'name')   else '',
        'family': mat.family  if hasattr(mat, 'family') else '',
    }
    try:
        props['E']     = mat.E(0)     * KN_M2_TO_MPA
        props['fc']    = mat.fc(0)    * KN_M2_TO_MPA
        props['ft']    = mat.ft(0)    * KN_M2_TO_MPA
        props['gamma'] = mat.gamma()    # kN/mm3
    except:
        pass

    return props