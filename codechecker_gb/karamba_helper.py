# -*- coding: utf-8 -*-
"""
Karamba3D helper utilities for GB50017 steel design checks.

Extracts forces, element info, section properties, and materials from a
Karamba3D model.  All output is in GB50017 working units (mm, N, MPa) except
extract_element_forces() which returns native Karamba units (kN, kN·m).

Usage pattern (cache sections once, reuse per element):
    all_sec = [extract_section_properties(sec) for sec in model.crosecs]
    all_mat = [extract_material(sec)     for sec in model.crosecs]
    elem_info  = extract_element_info(model)
    sub_lcs    = expand_load_combinations(model, ['ULS'])
    forces_all = extract_element_forces(model, elem_ids, [n for n,_ in sub_lcs])

    for ei, elem in enumerate(elem_info):
        si   = elem['sec_index']
        sec  = all_sec[si]   # cached lookup
        mat  = all_mat[si]
        for lc_name, _ in sub_lcs:
            f = forces_all[lc_name][ei]
            # … run code_checker functions …
"""

# ============================================================================
#  Unit conversion constants  —  Karamba internal → GB50017 working units
# ============================================================================
# Karamba stores everything in m-based SI:
#   m, m², m⁴, m³, m⁶,  kN,  kN·m,  kN/m²
# GB50017 works in mm-based units:
#   mm, mm², mm⁴, mm³, mm⁶,  N,   N·mm,  MPa (N/mm²)

M_TO_MM      = 1e3       # m  → mm
M2_TO_MM2    = 1e6       # m² → mm²
M3_TO_MM3    = 1e9       # m³ → mm³
M4_TO_MM4    = 1e12      # m⁴ → mm⁴
M6_TO_MM6    = 1e18      # m⁶ → mm⁶
KN_TO_N      = 1e3       # kN → N
KNM_TO_NMM   = 1e6       # kN·m → N·mm
KN_M2_TO_MPA = 1e-3      # kN/m² → MPa (N/mm²)

# ============================================================================
#  Imports (Karamba .NET interop)
# ============================================================================
import math
import re

import Karamba.Models
import Karamba.Loads
import Karamba.Results
import Karamba.CrossSections
from System.Collections.Generic import List
from System import String


# ============================================================================
#  Load combination expansion
# ============================================================================

def expand_load_combinations(model, comb_names):
    """Expand Load-Case-Combinator group names into their sub-load-cases.

    For each combination group name (e.g. 'ULS'), queries the model's
    lcActivation and returns the flat list of sub-combinations with their
    per-load-case factors.

    Args:
        model: Karamba model (clone before passing if needed).
        comb_names: list of combination group name strings.

    Returns:
        list of (lc_name, factors_dict) where lc_name is a string like
        'ULS/0' and factors_dict maps source load-case names to factors,
        e.g. {'G': 1.35, 'Q': 1.5}.
    """
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
#  Element info  (id, type, length, section index)
# ============================================================================

def extract_element_info(model):
    """Return identity, geometry, and section mapping for every element.

    Section index (sec_index) is determined by matching element IDs against
    the elemIds patterns stored on each CroSec object.

    Returns:
        list of dicts::

            {
                'id':         str,       # element identifier
                'type':       str,       # e.g. 'Beam3D', 'Truss3D'
                'length':     float,     # [mm]  straight-line node-to-node
                'sec_index':  int,       # 0-based index into model.crosecs
                'node_start': int,       # start node index
                'node_end':   int,       # end node index
            }
    """
    nodes = model.Nodes()

    # ---- element → section lookup via CroSec.elemIds (exact or regex) ----
    crosec_elem_map = {}   # elem_id → sec_index
    for si, sec in enumerate(model.crosecs):
        if not hasattr(sec, 'elemIds') or sec.elemIds is None:
            continue
        for pattern in sec.elemIds:
            compiled = re.compile(pattern)
            for el in model.Elements():
                if compiled.match(el.id):
                    crosec_elem_map[el.id] = si

    # ---- build info for each element ----
    info_list = []
    for el in model.Elements():
        # length from node positions
        try:
            n0_idx = el.node_inds[0]
            n1_idx = el.node_inds[1]
            n0 = nodes[n0_idx]
            n1 = nodes[n1_idx]
            dx = n1.pos.X - n0.pos.X
            dy = n1.pos.Y - n0.pos.Y
            dz = n1.pos.Z - n0.pos.Z
            length = math.sqrt(dx*dx + dy*dy + dz*dz) * M_TO_MM
        except:
            length = 0.0

        info_list.append({
            'id':         el.id,
            'type':       type(el).__name__,
            'length':     length,
            'sec_index':  crosec_elem_map.get(el.id, -1),
            'node_start': getattr(el, 'node_inds', [None, None])[0],
            'node_end':   getattr(el, 'node_inds', [None, None])[1] if (
                          getattr(el, 'node_inds', None) and len(el.node_inds) > 1
                          ) else None,
        })

    return info_list


# ============================================================================
#  Section properties  (single CroSec → dict, units = mm / mm² / mm⁴ / mm³)
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
    crosec.calculateProperties()

    props = {}

    # ---- identity ----
    for attr in ('name', 'family', 'familyID', 'guid', 'country_',
                 'user_defined', 'IsValid', 'isPlausible', 'product',
                 'alpha_y', 'alpha_z', 'alpha_lt'):
        if hasattr(crosec, attr):
            props[attr] = getattr(crosec, attr)

    # ---- geometry [mm] ----
    for attr in ('lf_width', 'uf_width', 'lf_thick', 'uf_thick',
                 'w_thick', 'fillet_r', 'fillet_r1'):
        if hasattr(crosec, attr):
            val = getattr(crosec, attr)
            if isinstance(val, (int, float)):
                props[attr] = val * M_TO_MM

    # height stored as _height on some section types
    for attr in ('_height', 'height'):
        if hasattr(crosec, attr):
            val = getattr(crosec, attr)
            if isinstance(val, (int, float)):
                props['height'] = val * M_TO_MM
                break

    # centroid / shear centre [mm]
    for attr in ('zs', 'zm', 'zg'):
        if hasattr(crosec, attr):
            props[attr] = getattr(crosec, attr) * M_TO_MM

    # ---- area & shear areas [mm²] ----
    for attr in ('A', 'Ay', 'Az'):
        if hasattr(crosec, attr):
            props[attr] = getattr(crosec, attr) * M2_TO_MM2

    # ---- moments of inertia [mm⁴] ----
    for attr in ('Iyy', 'Izz', 'Ipp'):
        if hasattr(crosec, attr):
            props[attr] = getattr(crosec, attr) * M4_TO_MM4

    # ---- warping constant [mm⁶] ----
    if hasattr(crosec, 'Cw'):
        props['Cw'] = crosec.Cw * M6_TO_MM6

    # ---- radii of gyration [mm] ----
    for attr in ('iy', 'iz'):
        if hasattr(crosec, attr):
            props[attr] = getattr(crosec, attr) * M_TO_MM

    # ---- elastic section moduli [mm³] ----
    for attr in ('Wely_z_pos', 'Wely_z_neg', 'Welz_y_pos', 'Welz_y_neg'):
        if hasattr(crosec, attr):
            props[attr] = getattr(crosec, attr) * M3_TO_MM3

    # ---- plastic section moduli [mm³] ----
    for attr in ('Wply', 'Wplz', 'Wt'):
        if hasattr(crosec, attr):
            props[attr] = getattr(crosec, attr) * M3_TO_MM3

    # ---- eccentricity ----
    if hasattr(crosec, 'ecce_loc'):
        props['ecce_loc'] = crosec.ecce_loc * M_TO_MM

    # ---- material reference (raw object, not processed) ----
    props['material'] = crosec.material if hasattr(crosec, 'material') else None
    props['material_name'] = props['material'].name if (
        props['material'] and hasattr(props['material'], 'name')
    ) else ''

    # ---- CroSec type ----
    props['section_type'] = type(crosec).__name__

    return props


# ============================================================================
#  Material properties  (single CroSec → dict, stress in MPa)
# ============================================================================

def extract_material(crosec):
    """Read material properties from a CroSec's attached FemMaterial.

    Args:
        crosec: a CroSec object (with an attached .material).

    Returns:
        dict::

            {
                'name':   str,      # material name
                'family': str,      # 'Steel', 'Concrete', …
                'E':      float,    # Young's modulus              [MPa]
                'G':      float,    # shear modulus                [MPa]
                'fy':     float,    # yield strength               [MPa]
                'fu':     float,    # ultimate tensile strength    [MPa]   (if available)
                'nue':    float,    # Poisson's ratio              [-]
                'gamma':  float,    # specific weight              [kN/m³]
            }
    """
    mat = crosec.material if hasattr(crosec, 'material') else None
    if mat is None:
        return {}

    props = {
        'name':   mat.name    if hasattr(mat, 'name')   else '',
        'family': mat.family  if hasattr(mat, 'family') else '',
    }
    try:
        props['E']     = mat.E(0)     * KN_M2_TO_MPA
        props['G']     = mat.G12()    * KN_M2_TO_MPA
        props['fy']    = mat.fy(0)    * KN_M2_TO_MPA
        props['fu']    = mat.fu(0)    * KN_M2_TO_MPA if hasattr(mat, 'fu') else 0.0
        props['nue']   = mat.nue12()
        props['gamma'] = mat.gamma()   # kN/m³, native — no conversion
    except:
        pass

    return props
