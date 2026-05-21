# --- illustrate ALL cross-section properties in model ---------------------------
#   based on Karamba3D 3.1.4 API: CroSec_Beam → CroSec_Box / CroSec_I / CroSec_Circle
#   properties inherited from CroSec_Beam are available on all section types
#   units: length→mm, stress→MPa  (Karamba stores m, kN/cm² internally)
# --------------------------------------------------------------------------------
import Karamba.Models
import Karamba.CrossSections

model = Model_in

# conversion constants (Karamba internal → display)
M_TO_MM   = 1e3        # m → mm
M2_TO_MM2 = 1e6        # m² → mm²
M3_TO_MM3 = 1e9        # m³ → mm³
M4_TO_MM4 = 1e12       # m⁴ → mm⁴
M6_TO_MM6 = 1e18       # m⁶ → mm⁶
KNM2_TO_MPA  = 1e-3      # kN/m² → MPa (doc says kN/cm² but actual output is kN/m²)


# ===== COMPLETE PROPERTY REFERENCE (CroSec_Beam base class) =====================
#   Property       Field (backing)    Unit     Description
#   ─────────────  ─────────────────  ───────  ───────────────────────────────────
#   A              A_                 mm²      cross-sectional area
#   Ay             Ay_                mm²      shear area, local y-direction (horiz)
#   Az             Az_                mm²      shear area, local z-direction (vert)
#   Iyy            Iyy_               mm⁴      moment of inertia about local Y-axis
#   Izz            Izz_               mm⁴      moment of inertia about local Z-axis
#   Ipp            Ipp_               mm⁴      torsional moment of inertia (St.Venant)
#   Cw             Cw_                mm⁶      warping constant (2nd-order)
#   iy             iy_                mm       radius of gyration about y-axis
#   iz             iz_                mm       radius of gyration about z-axis
#   Wely_z_pos     Wely_z_pos_        mm³      elastic modulus y, lower fibre (+My→tension)
#   Wely_z_neg     Wely_z_neg_        mm³      elastic modulus y, upper fibre (+My→compression)
#   Welz_y_pos     Welz_y_pos_        mm³      elastic modulus z, right fibre (+Mz→tension)
#   Welz_y_neg     Welz_y_neg_        mm³      elastic modulus z, left fibre (+Mz→compression)
#   Wply           Wply_              mm³      plastic resistance moment about y-axis
#   Wplz           Wplz_              mm³      plastic resistance moment about z-axis
#   Wt             Wt_                mm³      torsional resistance moment
#   zs             Zs                 mm       COG distance from upper boundary
#   zm             —                  mm       shear centre distance from upper boundary
#   zg             Zg                 mm       load-to-shear-centre distance (default=zs)
#   alpha_y        alpha_y_           —        EC3 imperfection factor, y-direction
#   alpha_z        alpha_z_           —        EC3 imperfection factor, z-direction
#   alpha_lt       alpha_lt_          —        EC3 imperfection factor, lateral-torsional
#   product        —                  —        production type (defines alpha defaults)
#   name           —                  —        section name within family
#   family         —                  —        family group ("IPE","HEA","RHS",…)
#   familyID       —                  —        unique family identifier
#   guid           —                  —        GUID
#   country_       —                  —        country code where section is in use
#   user_defined   —                  —        True if user-defined section
#   color          —                  —        user-defined colour
#   material       —                  —        attached FemMaterial object
#   materialName   —                  —        material name string
#   dims           —                  —        section dimensions
#   nDims          —                  —        number of dimension parameters
#   nProps         —                  —        number of property parameters
#   IsValid        —                  —        True if cross-section is valid (A>0)
#   isPlausible    —                  —        True if cross-section is plausible
#   ecce_loc       eccent_            —        local eccentricity
#   hasEccent      —                  —        True if eccentricity defined
#   elemIds        elem_ids_          —        element IDs / regex this section is assigned to
#   fe_ind_        —                  —        FE model identification number
#   exteriorPerimeter —               mm        perimeter (CroSec_Box/CroSec_I override)

# ===== CroSec_Box / CroSec_I ONLY: geometry dimensions ==========================
#   Property       Field (backing)    Unit     Description
#   ─────────────  ─────────────────  ───────  ───────────────────────────────────
#   height         _height_           mm        overall depth
#   lf_width       lf_width_          mm        lower flange width
#   uf_width       uf_width_          mm        upper flange width
#   lf_thick       lf_thick_          mm        lower flange thickness
#   uf_thick       uf_thick_          mm        upper flange thickness
#   w_thick        w_thick_           mm        web thickness
#   fillet_r       fillet_r_          mm        inner fillet radius
#   fillet_r1      fillet_r1_         mm        outer fillet radius (I-section only)

# ===== FemMaterial METHODS (call with () ) ======================================
#   E(0)     → Young's modulus  [kN/m²]       G12() → shear modulus [kN/m²]
#   fy(0)    → yield strength   [kN/m²]       fu(0) → ultimate strength [kN/m²]
#   fc(0)    → compr. strength  [kN/m²]       ft(0) → tensile strength [kN/m²]
#   nue12()  → Poisson's ratio  [-]           gamma() → specific weight [kN/m³]
#   ⚠ doc says kN/cm² but actual runtime output is kN/m² → ×1e-3 for MPa


# === iterate all cross-sections in model ========================================

print("=" * 72)
print("CROSS-SECTION PROPERTIES — COMPLETE DUMP  (mm, MPa)")
print("=" * 72)

for idx, sec in enumerate(model.crosecs):
    typ = type(sec).__name__
    sec.calculateProperties()
    mat = sec.material if hasattr(sec, 'material') else None

    print(f"\n{'─'*72}")
    print(f"[{idx}]  {typ}  name='{sec.name}'  family='{sec.family if hasattr(sec,'family') else '?'}'")
    print(f"{'─'*72}")

    # --- identity ---
    print(f"\n  ── IDENTITY ──")
    for attr in ('name','family','familyID','guid','country_','user_defined',
                 'IsValid','isPlausible','nDims','nProps','fe_ind_'):
        if hasattr(sec, attr):
            print(f"  {attr:20s} = {getattr(sec, attr)}")

    # --- geometry dimensions [mm] (CroSec_Box / CroSec_I only) ---
    geo_attrs = []
    for attr in ('height','_height','lf_width','uf_width','lf_thick','uf_thick',
                 'w_thick','fillet_r','fillet_r1','exteriorPerimeter'):
        if hasattr(sec, attr):
            v = getattr(sec, attr) * M_TO_MM
            geo_attrs.append((attr, v))
    if geo_attrs:
        print(f"\n  ── GEOMETRY [mm] ──")
        for k, v in geo_attrs:
            print(f"  {k:20s} = {v:.1f}")

    # --- section properties ---
    print(f"\n  ── SECTION PROPERTIES ──")

    # area & shear [mm²]
    for attr in ('A','Ay','Az'):
        if hasattr(sec, attr):
            print(f"  {attr:20s} = {getattr(sec, attr) * M2_TO_MM2:12.0f}  mm²")

    # moments of inertia [mm⁴]
    for attr in ('Iyy','Izz','Ipp'):
        if hasattr(sec, attr):
            print(f"  {attr:20s} = {getattr(sec, attr) * M4_TO_MM4:12.0f}  mm⁴")

    # warping constant [mm⁶]
    if hasattr(sec, 'Cw'):
        print(f"  {'Cw':20s} = {sec.Cw * M6_TO_MM6:12.4e}  mm⁶")

    # radii of gyration [mm]
    for attr in ('iy','iz'):
        if hasattr(sec, attr):
            print(f"  {attr:20s} = {getattr(sec, attr) * M_TO_MM:12.1f}  mm")

    # elastic moduli [mm³]
    print(f"\n  ── ELASTIC SECTION MODULI [mm³] ──")
    for attr in ('Wely_z_pos','Wely_z_neg','Welz_y_pos','Welz_y_neg'):
        if hasattr(sec, attr):
            print(f"  {attr:20s} = {getattr(sec, attr) * M3_TO_MM3:12.0f}")

    # plastic moduli [mm³]
    print(f"\n  ── PLASTIC SECTION MODULI [mm³] ──")
    for attr in ('Wply','Wplz','Wt'):
        if hasattr(sec, attr):
            print(f"  {attr:20s} = {getattr(sec, attr) * M3_TO_MM3:12.0f}")

    # --- centroid / shear centre [mm] ---
    print(f"\n  ── CENTROID & SHEAR [mm] ──")
    for attr in ('zs','zm','zg'):
        if hasattr(sec, attr):
            print(f"  {attr:20s} = {getattr(sec, attr) * M_TO_MM:12.1f}")

    # --- buckling imperfection factors ---
    print(f"\n  ── BUCKLING (EC3) ──")
    for attr in ('alpha_y','alpha_z','alpha_lt','product'):
        if hasattr(sec, attr):
            print(f"  {attr:20s} = {getattr(sec, attr)}")

    # --- eccentricity [mm] ---
    print(f"\n  ── ECCENTRICITY [mm] ──")
    for attr in ('ecce_loc','hasEccent','elemIds'):
        if hasattr(sec, attr):
            v = getattr(sec, attr)
            if attr == 'hasEccent':
                print(f"  {attr:20s} = {v}")
            elif isinstance(v, (int, float)):
                print(f"  {attr:20s} = {v * M_TO_MM:12.1f}")
            else:
                print(f"  {attr:20s} = {v}")

    # --- material [MPa] ---
    if mat is not None:
        print(f"\n  ── MATERIAL [MPa] ──")
        print(f"  {'name':20s} = {mat.name if hasattr(mat,'name') else '?'}")
        print(f"  {'family':20s} = {mat.family if hasattr(mat,'family') else '?'}")
        try:
            print(f"  {'E(0)':20s} = {mat.E(0) * KNM2_TO_MPA:.0f}  MPa")
            print(f"  {'G12()':20s} = {mat.G12() * KNM2_TO_MPA:.0f}  MPa")
            print(f"  {'fy(0)':20s} = {mat.fy(0) * KNM2_TO_MPA:.0f}  MPa")
            if hasattr(mat, 'fu'):
                print(f"  {'fu(0)':20s} = {mat.fu(0) * KNM2_TO_MPA:.0f}  MPa")
            if hasattr(mat, 'fc'):
                print(f"  {'fc(0)':20s} = {mat.fc(0) * KNM2_TO_MPA:.0f}  MPa")
            if hasattr(mat, 'ft'):
                print(f"  {'ft(0)':20s} = {mat.ft(0) * KNM2_TO_MPA:.0f}  MPa")
            print(f"  {'nue12()':20s} = {mat.nue12():.3f}")
            print(f"  {'gamma()':20s} = {mat.gamma():.2f}  kN/m³")
        except Exception as e:
            print(f"  (material method error: {e})")

print(f"\n{'='*72}")
print("Done — all section properties illustrated  (mm, MPa).")
