import math
import pandas as pd

def calc_alpha(curve_class, lambda_n):
    """Return buckling curve coefficients [α₁, α₂, α₃] per GB50017 Table D.0.5.

    Args:
        curve_class: 'a', 'b', 'c', or 'd'
        lambda_n: normalised slenderness λ_n = λ/π · √(fy/E)

    Returns:
        [α₁, α₂, α₃]
    """
    if curve_class == 'a':
        return [0.41, 0.986, 0.152]
    elif curve_class == 'b':
        return [0.65, 0.965, 0.300]
    elif curve_class == 'c':
        if lambda_n <= 1.05:
            return [0.73, 0.906, 0.595]
        else:
            return [0.73, 1.216, 0.302]
    elif curve_class == 'd':
        if lambda_n <= 1.05:
            return [1.35, 0.868, 0.915]
        else:
            return [1.35, 1.375, 0.432]
    else:
        raise ValueError(f"Unknown buckling curve: '{curve_class}'")


def calc_phi(lambda_n, alpha):
    """Stability reduction factor φ per GB50017 Annex D.

    Args:
        lambda_n: normalised slenderness
        alpha: [α₁, α₂, α₃] from calc_alpha()

    Returns:
        φ (dimensionless, ≤ 1.0)
    """
    a1, a2, a3 = alpha
    if lambda_n <= 0.215:
        return 1.0 - a1 * lambda_n * lambda_n
    else:
        t = a2 + a3 * lambda_n + lambda_n * lambda_n
        phi = (t - math.sqrt(t * t - 4.0 * lambda_n * lambda_n)) / (2.0 * lambda_n * lambda_n)
        return phi


def classify_section(sec_props, fy):
    """Classify a steel section per GB50017 Table 3.5.1, Table 7.2.1 and Table 8.5.1.

    Determines:
    - Buckling class (a/b/c/d) for strong and weak axes
    - Plastic adaptation factors γ_y, γ_z
    - Overall section class (1–5)

    Args:
        sec_props: dict
        fy: yield strength [MPa]

    Returns:
        (curve_y, curve_z, gamma_y, gamma_z, class_overall)
            curve_y, curve_z: 'a','b','c','d'
            gamma_y, gamma_z: 1.05 (plastic) or 1.0 (elastic)
            class_overall: 1–5, higher = more slender
    """
    sec_type = sec_props.get('section_type', '')
    eps = math.sqrt(235.0 / fy)  # ε_k

    # ---- flange classification ----
    # outstand width b' [mm]  (half-flange minus half-web, minus fillet if present)
    bf = max(sec_props.get('uf_width', 0), sec_props.get('lf_width', 0))
    tf = max(sec_props.get('uf_thick', 0), sec_props.get('lf_thick', 0))
    tw = sec_props.get('w_thick', 0)
    h  = sec_props.get('height', 0)

    if 'I' in sec_type or 'Beam' in sec_type:
        # Hot-rolled I-section: b' = (bf - tw - 2r) / 2
        # Welded I-section:     b' = (bf - tw) / 2
        # Conservative: use b' = bf/2
        b_prime = (bf - tw) / 2.0
        if b_prime <= 0:
            b_prime = bf / 2.0
        flange_bt = b_prime / tf if tf > 0 else 0

        # Flange limits (outstand element, free edge) — Table 3.2 item 2
        if flange_bt <= 9 * eps:
            flange_class = 1
        elif flange_bt <= 11 * eps:
            flange_class = 2
        elif flange_bt <= 13 * eps:
            flange_class = 3
        elif flange_bt <= 15 * eps:
            flange_class = 4
        else:
            flange_class = 5

        # Web limits (internal element, bending) — Table 3.2 item 4
        h0 = h - sec_props.get('uf_thick', 0) - sec_props.get('lf_thick', 0)
        if h0 <= 0:
            h0 = h - 2 * tf
        web_ht = h0 / tw if tw > 0 else 0

        if web_ht <= 33 * eps:
            web_class = 1
        elif web_ht <= 38 * eps:
            web_class = 2
        elif web_ht <= 42 * eps:
            web_class = 3
        elif web_ht <= 45 * eps:
            web_class = 4
        else:
            web_class = 5

        overall_class = max(flange_class, web_class)

        # ---- buckling curve assignment (Table D.0.1) ----
        # Assume hot-rolled I/H-section with tf ≤ 40mm as default
        # b/h ratio determines strong-axis curve
        bh_ratio = bf / h if h > 0 else 0
        if overall_class == 4 or overall_class == 5:
            # Slender section — effective width needed, flag curve d (conservative)
            curve_y = 'd'
            curve_z = 'd'
        else:
            # y-y (strong): a if b/h ≤ 0.8, else b
            curve_y = 'a' if bh_ratio <= 0.8 else 'b'
            # z-z (weak): b
            curve_z = 'b'

        # Plastic adaptation factors
        if overall_class <= 2:
            gamma_y, gamma_z = 1.05, 1.05
        else:
            gamma_y, gamma_z = 1.0, 1.0

    elif 'Box' in sec_type or 'RHS' in sec_type:
        # For box/RHS, use different flange/web limits
        # Flange: internal element (Table 3.2 item 1)
        b0 = bf - 2 * tw
        flange_bt = b0 / tf if tf > 0 else 0
        if flange_bt <= 30 * eps:
            flange_class = 1
        elif flange_bt <= 35 * eps:
            flange_class = 2
        elif flange_bt <= 42 * eps:
            flange_class = 3
        elif flange_bt <= 45 * eps:
            flange_class = 4
        else:
            flange_class = 5

        # Web — same as I-section for simplicity
        h0 = h - sec_props.get('uf_thick', 0) - sec_props.get('lf_thick', 0)
        web_ht = h0 / tw if tw > 0 else 0
        if web_ht <= 33 * eps:
            web_class = 1
        elif web_ht <= 38 * eps:
            web_class = 2
        elif web_ht <= 42 * eps:
            web_class = 3
        elif web_ht <= 45 * eps:
            web_class = 4
        else:
            web_class = 5

        overall_class = max(flange_class, web_class)
        curve_y = 'a'  # RHS: both axes class a (hot-rolled)
        curve_z = 'a'
        gamma_y, gamma_z = (1.05, 1.05) if overall_class <= 2 else (1.0, 1.0)

    elif 'Circle' in sec_type or 'CHS' in sec_type:
        # CHS: diameter-to-thickness ratio (Table 3.2 item 8)
        D = h  # height = outer diameter for CHS
        t = tw if tw > 0 else tf  # wall thickness
        dt_ratio = D / t if t > 0 else 0
        if dt_ratio <= 60 * eps * eps:
            overall_class = 1
        elif dt_ratio <= 70 * eps * eps:
            overall_class = 2
        elif dt_ratio <= 90 * eps * eps:
            overall_class = 3
        elif dt_ratio <= 100 * eps * eps:
            overall_class = 4
        else:
            overall_class = 5
        curve_y = 'a'
        curve_z = 'a'
        gamma_y, gamma_z = (1.05, 1.05) if overall_class <= 2 else (1.0, 1.0)

    else:
        # Unknown section type — conservative defaults
        overall_class = 3
        curve_y, curve_z = 'c', 'c'
        gamma_y, gamma_z = 1.0, 1.0

    if overall_class >= 4:
        # Flag — slender section may need effective width calculation
        pass

    return curve_y, curve_z, gamma_y, gamma_z, overall_class


def calc_flexural_slenderness(len, i):
    return len / i if i > 0 else 0.0


def calc_torsional_slenderness(len, i):
    return calc_flexural_slenderness(len, i)  # placeholder


def calc_slenderness(sec_props, len_y, len_z, len_lt):
    sec_type = sec_props['section_type']
    iy = sec_props['iy']

    # Strong-axis: always simple flexural buckling
    lambda_y = calc_flexural_slenderness(len_y, iy)

    # Weak-axis: flexural-torsional buckling for open sections
    if 'I' in sec_type or 'Beam' in sec_type or 'T' in sec_type:
        lambda_z = calc_torsional_slenderness(sec_props, len_z)
    else:
        lambda_z = calc_flexural_slenderness(len_z, sec_props['iz'])

    # Lateral-torsional buckling (LTB)
    lambda_lt = calc_flexural_slenderness(len_lt, sec_props['iz'])

    return lambda_y, lambda_z, lambda_lt


def check_steel_element(sec_props, mat, eff_len, force,
                        gamma_re = 1.0, slender_limit=150):
    """Run all GB50017-2017 steel checks for one force state on one element.

    Args:
        sec_props:  dict from karamba_helper.extract_section_properties()
        mat_props:  dict from karamba_helper.extract_material()
        eff_len:    effective buckling length 
                    dict {'bklY':mm, 'bklZ':mm, 'bklLT':mm}
        force:      dict {'N':kN, 'Vy':kN, 'Vz':kN, 'Mx':kN·m, 'My':kN·m, 'Mz':kN·m}
        gamma_re:   seismic resistance factor (default 1.0)
        slender_limit: slenderness limit (default 150 per GB50017)

    Returns:
        dict::

            {'σ_N':              0.0,   # axial strength         §7.1.1
             'σ_My':             0.0,   # bending, strong axis   §6.1.1
             'σ_Mz':             0.0,   # bending, weak axis     §6.1.1
             'σ_Myz':            0.0,   # combined bending       §6.1.1
             'τ_Vy':             0.0,   # shear, strong-axis     §6.1.3
             'τ_Vz':             0.0,   # shear, weak-axis       §6.1.3
             'σ_NMyz':           0.0,   # axial + bending        §8.2.1
             'σ_Ny_buckling':    0.0,   # flexural buckling, y   §7.2.1
             'σ_Nz_buckling':    0.0,   # flexural buckling, z   §7.2.1
             'σ_NMyz_buckling':  0.0,   # combined buckling, y   §8.2.5
             'σ_NMzy_buckling':  0.0,   # combined buckling, z   §8.2.5
             'λ_y':              0.0,   # slenderness ratio, y
             'λ_z':              0.0,   # slenderness ratio, z
             'class_overall':    1,     # section class 1-5
             'warning':          ''}    # non-empty if slenderness > limit
    """
    # ---- unpack material ----
    E, fy, f, fv = (mat['E'], mat['fy'], mat['f'], mat['fv'])

    # ---- unpack section properties ----
    sec_type = sec_props['section_type']
    A, Iyy, Izz = (sec_props['A'], sec_props['Iyy'], sec_props['Izz'])
    Sy, Sz, ty, tz = (sec_props['Ay'], sec_props['Az'], sec_props['lf_thick'], sec_props['w_thick'])
    # TODO: check Wely_z_pos, Wely_z_neg, Welz_y_pos, Welz_y_neg for asymmetric section
    Wy = max(sec_props['Wely_z_pos'], sec_props['Wely_z_neg'])
    Wz = max(sec_props['Welz_y_pos'], sec_props['Welz_y_neg'])

    # ---- classify section & compute shear geometry ----
    curve_y, curve_z, gamma_y, gamma_z, overall_class = classify_section(sec_props, fy)    

    # ---- unpack & convert forces: kN → N,  kN·m → N·mm ----
    Fx, Vy, Vz = (force['N'] * 1e3, force['Vy'] * 1e3, force['Vz'] * 1e3)
    Mx, My, Mz = (force['Mx'] * 1e6, force['My'] * 1e6, force['Mz'] * 1e6)

    # ---- slenderness ----
    len_y, len_z, len_lt = (eff_len['bklY'], eff_len['bklZ'], eff_len['bklLT'])
    lambda_y, lambda_z, lambda_lt = calc_slenderness(sec_props, len_y, len_z, len_lt)
    warning = ''
    if lambda_y > slender_limit:
        warning = f'λ_y={lambda_y:.0f} > {slender_limit}'
    if lambda_z > slender_limit:
        if warning:
            warning += '; '
        warning += f'λ_z={lambda_z:.0f} > {slender_limit}'

    #  STRENGTH
    # ---- N  §7.1.1  axial stress ----
    sigma_N = abs(Fx) / A if A > 0 else 0

    # ---- My, Mz  §6.1.1  bending stress ----
    sigma_My = abs(My) / (gamma_y * Wy) if Wy > 0 else 0
    sigma_Mz = abs(Mz) / (gamma_z * Wz) if Wz > 0 else 0

    # ---- Myz  §6.1.1  combined biaxial bending stress ----
    if 'Circle' in sec_type:
        # CHS: vector resultant moment
        sigma_Myz = math.sqrt(My * My + Mz * Mz) / (gamma_y * Iyy) if Iyy > 0 else 0
    else:
        # I-section / RHS: stress summation
        sigma_Myz = sigma_My + sigma_Mz

    # ---- Vy, Vz  §6.1.3  shear stress ----
    tau_Vy = Vz * Sy / (Iyy * ty) if Iyy > 0 and ty > 0 else 0
    tau_Vz = Vy * Sz / (Izz * tz) if Izz > 0 and tz > 0 else 0

    # ---- N + My + Mz  §8.2.1  combined axial + bending ----
    sigma_NM = sigma_N + sigma_Myz

    #  STABILITY
    # Normalised slenderness
    lambda_n_y = (lambda_y / math.pi) * math.sqrt(fy / E) if E > 0 else 0
    lambda_n_z = (lambda_z / math.pi) * math.sqrt(fy / E) if E > 0 else 0

    # Buckling reduction factor φ
    phi_y = calc_phi(lambda_n_y, calc_alpha(curve_y, lambda_n_y))
    phi_z = calc_phi(lambda_n_z, calc_alpha(curve_z, lambda_n_z))

    # ---- N buckling  §7.2.1  flexural buckling ----
    sigma_Ny_buckling = abs(Fx) / (phi_y * A) if phi_y > 0 and A > 0 else 0
    sigma_Nz_buckling = abs(Fx) / (phi_z * A) if phi_z > 0 and A > 0 else 0

    # ---- N + My + Mz buckling  §8.2.5  combined buckling ----
    beta  = 1.0   # equivalent moment factor (conservative)
    eta   = 0.7 if 'Box' in sec_type or 'Circle' in sec_type else 1.0
    phi_b = 1.0   # LTB factor — full calculation (§6.2.2) TODO

    N_Ey = math.pi * math.pi * E * A / (1.1 * lambda_y * lambda_y) if lambda_y > 0 else float('inf')
    N_Ez = math.pi * math.pi * E * A / (1.1 * lambda_z * lambda_z) if lambda_z > 0 else float('inf')

    # y-dominant buckling  (My main)
    denom_y = 1.0 - 0.8 * abs(Fx) / N_Ey if N_Ey > 0 else 0
    term_y1 = abs(Fx) / (phi_y * A) if phi_y > 0 and A > 0 else 0
    term_y2 = beta * abs(My) / (gamma_y * Wy * denom_y) if Wy > 0 and denom_y > 0 else 0
    term_y3 = eta * beta * abs(Mz) / (phi_b * Wz) if Wz > 0 else 0
    sigma_NMy_buckling = term_y1 + term_y2 + term_y3

    # z-dominant buckling  (Mz main)
    denom_z = 1.0 - 0.8 * abs(Fx) / N_Ez if N_Ez > 0 else 0
    term_z1 = abs(Fx) / (phi_z * A) if phi_z > 0 and A > 0 else 0
    term_z2 = beta * abs(Mz) / (gamma_z * Wz * denom_z) if Wz > 0 and denom_z > 0 else 0
    term_z3 = eta * beta * abs(My) / (phi_b * Wy) if Wy > 0 else 0
    sigma_NMz_buckling = term_z1 + term_z2 + term_z3

    #  UTILIZATION (stress / design strength / γ_RE)
    utilization = pd.Series({
        'σ_N':              sigma_N / f,
        'σ_My':             sigma_My / f,
        'σ_Mz':             sigma_Mz / f,
        'σ_Myz':            sigma_Myz / f,
        'τ_Vy':             tau_Vy / fv,
        'τ_Vz':             tau_Vz / fv,
        'σ_NMyz':           sigma_NM / f,
        'σ_Ny_buckling':    sigma_Ny_buckling / f,
        'σ_Nz_buckling':    sigma_Nz_buckling / f,
        'σ_NMyz_buckling':  sigma_NMy_buckling / f,
        'σ_NMzy_buckling':  sigma_NMz_buckling / f})/gamma_re

    return utilization