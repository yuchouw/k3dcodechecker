"""
Karamba3D helper utilities for GB50017 steel design checks.

Extracts forces, element info, section properties, and materials from a
Karamba3D model.  All output is in GB50017 working units (mm, N, MPa) except
extract_element_forces() which returns native Karamba units (kN, kN·m).

Usage pattern:
    all_sec     = [extract_section_properties(sec) for sec in model.crosecs]
    all_mat     = extract_materials(model)            # unique list from model.materials
    mat_map     = build_material_index_map(model)     # sec_index → mat_index
    sec_map     = build_section_index_map(model)      # elem_id → sec_index
    sub_lcs     = expand_load_combinations(model, ['ULS'])
    lc_names    = [n for n,_ in sub_lcs]
    forces_all  = extract_element_forces(model, elem_ids, lc_names)

    for ei, el in enumerate(model.Elements()):
        info = extract_element_info(el)               # per-element
        si   = sec_map.get(info['id'], -1)
        sec  = all_sec[si]
        mat  = all_mat[mat_map[si]]
        for lc_name in lc_names:
            f = forces_all[lc_name][ei]
            # … run code_checker functions …
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
#  Element force extraction
# ============================================================================

def extract_element_forces(model, elem_ids, lc_names, n_positions=5):
    """Extract beam forces and moments for a set of elements and load cases.

    Uses Karamba.Results.BeamForces.solve() to query results at evenly
    spaced positions along each element.

    Args:
        model: Karamba model (clone before passing if needed).
        elem_ids: List[String] of element IDs to query.
        lc_names: list of load-case name strings (pre-expanded sub-LCs).
        n_positions: number of result points per element.  Default 5
            produces 6 points (start, 4 interior, end).

    Returns:
        dict keyed by lc_name.  Each value is a per-element list:
            results[lc][ei] = [
                {'N':kN, 'Vy':kN, 'Vz':kN, 'Mx':kN·m, 'My':kN·m, 'Mz':kN·m},
                …
            ]
        where ei is 0-based element index matching the order in elem_ids.
    """
    maxDist = 10000.0   # large → uniform spacing, not distance-limited

    results = {}
    for lc_name in lc_names:
        forces, moments, govLC, govLCInd, eInds = Karamba.Results.BeamForces.solve(
            model, elem_ids, lc_name, maxDist, n_positions
        )

        lc_results = []
        for ei in range(len(forces)):
            pos_list = []
            for pi in range(len(forces[ei])):
                fv = forces[ei][pi][0]   # Vector3, k=0  (single LC query)
                mv = moments[ei][pi][0]
                pos_list.append({
                    'N':  fv.X,   # axial force            [kN]
                    'Vy': fv.Y,   # shear force, local y   [kN]
                    'Vz': fv.Z,   # shear force, local z   [kN]
                    'Mx': mv.X,   # torsion                [kN·m]
                    'My': mv.Y,   # strong-axis bending    [kN·m]
                    'Mz': mv.Z,   # weak-axis bending      [kN·m]
                })
            lc_results.append(pos_list)

        results[lc_name] = lc_results

    return results


# ============================================================================
#  Section index mapping  (elem_id → sec_index via CroSec.elemIds patterns)
# ============================================================================

def build_section_index_map(model):
    """Build a lookup mapping element ID → section index.

    Matches element IDs against the elemIds regex patterns stored on each
    CroSec object.

    Args:
        model: Karamba model.

    Returns:
        dict[str, int] — elem_id → 0-based index into model.crosecs.
        Unmatched elements are absent from the dict (use .get(id, -1)).
    """
    mapping = {}
    for si, sec in enumerate(model.crosecs):
        if not hasattr(sec, 'elemIds') or sec.elemIds is None:
            continue
        for pattern in sec.elemIds:
            compiled = re.compile(pattern)
            for el in model.Elements():
                if compiled.match(el.id):
                    mapping[el.id] = si
    return mapping


def extract_element_info(el):
    bklY = el.buckling_length(BuilderElementStraightLine.BucklingDir.bklY) * M_TO_MM
    bklZ = el.buckling_length(BuilderElementStraightLine.BucklingDir.bklZ) * M_TO_MM
    bklLT = el.buckling_length(BuilderElementStraightLine.BucklingDir.bklLT) * M_TO_MM
    
    return {
        'id':       el.id,
        'bklY':     bklY,
        'bklZ':     bklZ,
        'bklLT':    bklLT
    }


# ============================================================================
#  Section properties  (units = mm / mm² / mm⁴ / mm³)
# ============================================================================

def extract_section_properties(crosec):
    """Read all design-relevant properties from a single Karamba CroSec object.

    Calls crosec.calculateProperties() then extracts geometry, section
    moduli, radii of gyration, warping constant, and material reference.
    All values are converted to GB50017 working units (mm-based).

    Args:
        crosec: a CroSec object from model.crosecs.

    Returns:
        dict with keys described below.  Missing / unavailable keys are
        omitted (use .get() with a default when reading).

    Identity
        name, family, familyID, guid, country_, user_defined, IsValid

    Geometry [mm]
        height, lf_width, uf_width, lf_thick, uf_thick, w_thick,
        fillet_r, fillet_r1, zs, zm, zg

    Section properties [mm², mm⁴, mm³, mm⁶]
        A, Ay, Az,
        Iyy, Izz, Ipp, Cw,
        iy, iz,
        Wely_z_pos, Wely_z_neg, Welz_y_pos, Welz_y_neg,
        Wply, Wplz, Wt

    Material (reference object)
        material   — attached FemMaterial instance (or None)
    """
    props = {}

    for attr in ('name', 'family', 'familyID', 'guid', 'country_',
                 'user_defined', 'IsValid', 'isPlausible', 'product',
                 'alpha_y', 'alpha_z', 'alpha_lt'):
        if hasattr(crosec, attr):
            props[attr] = getattr(crosec, attr)

    for attr in ('lf_width', 'uf_width', 'lf_thick', 'uf_thick',
                 'w_thick', 'fillet_r', 'fillet_r1'):
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

    for attr in ('zs', 'zm', 'zg'):
        if hasattr(crosec, attr):
            props[attr] = getattr(crosec, attr) * M_TO_MM

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

    props['material'] = crosec.material if hasattr(crosec, 'material') else None
    props['material_name'] = props['material'].name if (
        props['material'] and hasattr(props['material'], 'name')
    ) else ''

    props['section_type'] = type(crosec).__name__

    return props

# ============================================================================
#  Material properties  (model.materials → list of dicts, stress in MPa)
# ============================================================================

def extract_material(mat):
    props = {
        'name':   mat.name    if hasattr(mat, 'name')   else '',
        'family': mat.family  if hasattr(mat, 'family') else '',
    }
    try:
        props['E']     = mat.E(0)     * KN_M2_TO_MPA
        props['G']     = mat.G12()    * KN_M2_TO_MPA
        props['fc']    = mat.fc(0)    * KN_M2_TO_MPA
        props['ft']    = mat.ft(0)    * KN_M2_TO_MPA
        props['nue']   = mat.nue12()
        props['gamma'] = mat.gamma()    # kN/mm3
    except:
        pass

    return props

def build_material_index_map(model):
    """Build a lookup mapping section index → material index.

    Matches each CroSec's material against model.materials by .NET object
    identity (id()), so duplicate materials across sections correctly map to
    the same material index.

    Args:
        model: Karamba model.

    Returns:
        list of int, same length as model.crosecs.  Each value is an index
        into model.materials (extract_materials()), or -1 if unmatched.
    """
    if not hasattr(model, 'materials') or model.materials is None:
        return [-1] * len(model.crosecs)

    # Build id → material_index lookup
    mat_id_to_idx = {id(mat): i for i, mat in enumerate(model.materials)}

    mapping = []
    for sec in model.crosecs:
        mat = sec.material if hasattr(sec, 'material') else None
        mapping.append(mat_id_to_idx.get(id(mat), -1) if mat is not None else -1)

    return mapping