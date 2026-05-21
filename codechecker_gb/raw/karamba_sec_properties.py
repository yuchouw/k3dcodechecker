# --- general section property extractor -----------------------------------------
#   returns [(name, type, props_dict), ...] for all CroSec in model.crosecs
#   props_dict keys are in SI base units (m, m², m⁴, m³, m⁶)
# --------------------------------------------------------------------------------
import Karamba.Models
import Karamba.CrossSections

model = Model_in.Clone()


def extract_section_properties(model):
    """Return list of (name, type, props) for every cross-section in the model."""
    result = []

    for sec in model.crosecs:
        sec.calculateProperties()

        name = sec.name if hasattr(sec, 'name') else ""
        typ  = type(sec).__name__

        props = {}

        # --- geometry (present on most CroSec subclasses) -----------------------
        for attr in ('_height', 'lf_width', 'lf_thick', 'uf_width', 'uf_thick',
                     'w_thick', 'fillet_r', 'zs', 'zm'):
            if hasattr(sec, attr):
                props[attr.lstrip('_')] = getattr(sec, attr)

        # --- area & shear -------------------------------------------------------
        for attr in ('A', 'Ay', 'Az'):
            if hasattr(sec, attr):
                props[attr] = getattr(sec, attr)

        # --- moments of inertia -------------------------------------------------
        for attr in ('Iyy', 'Izz', 'Ipp', 'Cw'):
            if hasattr(sec, attr):
                props[attr] = getattr(sec, attr)

        # --- radii of gyration --------------------------------------------------
        for attr in ('iy', 'iz'):
            if hasattr(sec, attr):
                props[attr] = getattr(sec, attr)

        # --- elastic section moduli ---------------------------------------------
        for attr in ('Wely_z_pos', 'Wely_z_neg', 'Welz_y_pos', 'Welz_y_neg'):
            if hasattr(sec, attr):
                props[attr] = getattr(sec, attr)

        # --- plastic section moduli ---------------------------------------------
        for attr in ('Wply', 'Wplz', 'Wt'):
            if hasattr(sec, attr):
                props[attr] = getattr(sec, attr)

        # --- material -----------------------------------------------------------
        mat = sec.material if hasattr(sec, 'material') else None
        if mat is not None:
            props['mat_name']   = mat.name if hasattr(mat, 'name') else ""
            props['mat_family'] = mat.family if hasattr(mat, 'family') else ""
            try:
                props['E']  = mat.E(0)       # kN/cm²
                props['G']  = mat.G12()      # kN/cm²
                props['fy'] = mat.fy(0)      # kN/cm²
                props['fu'] = mat.fu(0) if hasattr(mat, 'fu') else 0.0
                props['nue'] = mat.nue12()
                props['gamma'] = mat.gamma()  # kN/m³
            except:
                pass

        result.append((name, typ, props))

    return result


# --- run & print ----------------------------------------------------------------
props_list = extract_section_properties(model)

print(f"Total cross-sections: {len(props_list)}\n")

for name, typ, props in props_list:
    print(f"{typ}  '{name}'")
    for k, v in sorted(props.items()):
        if isinstance(v, float):
            print(f"  {k:18s} = {v:.8e}")
        else:
            print(f"  {k:18s} = {v}")
    print()

print("Done — extract_section_properties() ready.")
