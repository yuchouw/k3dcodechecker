import numpy as np
import pandas as pd
from math import *

HEADER_UTILIZATION  = ['σ_N [7.1.1]', 'σ_My [6.1.1]', 'σ_Mz [6.1.1]', 'σ_Myz [6.1.1]', 'τ_Vy [6.1.3]', 'τ_Vz [6.1.3]', 'σ_NMyz [8.2.1]', 'σ_Ny_buckling [7.2.1]', 'σ_Nz_buckling [7.2.1]', 'σ_NMyz_buckling [8.2.5]', 'σ_NMzy_buckling [8.2.5]']
HEADER_VIRTUAL_WORK = ['By Force', 'By Moment', 'Total']

def init_option(gamma_re = 0.85, slender_ratio_limit = 150):
    return (gamma_re, slender_ratio_limit)


def mat(Steel_Grade):
    matlib = pd.read_csv(r'GsaCheck\mat.csv', index_col = 0, dtype = {'Name': str, 'E': float, 'f': float, 'fv': float, 'fy': float})
    mat = matlib.loc[Steel_Grade]
    if(len(mat) == 0):
        raise ValueError('The material doesn\'t exist in current library, please define it correctly in material library.')
    else:
        E,f_,fv_,fy_ = mat
    return (E,fy_,f_,fv_)


def calc_alpha(class_,lambda_n):
    if class_ == "a":
        alpha_ = [0.41,0.986,0.152]
    if class_ == "b":
        alpha_ = [0.65,0.965,0.300]
    if class_ == "c":
        if lambda_n <= 1.05:
            alpha_ = [0.73,0.906,0.595]
        else:
            alpha_ = [0.73,1.216,0.302]
    if class_ == "d":
        if lambda_n <= 1.05:
            alpha_ = [1.35,0.868,0.915]
        else:
            alpha_ = [1.35,1.375,0.432]
    return alpha_
    

def calc_phi_steel(lambda_n,alpha):
    if lambda_n <= 0.215:
        phi = 1.- alpha[0]*lambda_n**2
    else:
        phi = 1./2./lambda_n**2*((alpha[1]+alpha[2]*lambda_n+lambda_n**2) - sqrt((alpha[1]+alpha[2]*lambda_n+lambda_n**2)**2-4*lambda_n**2))
    return phi


def design_steel(el_ref, init_option, sec_prop, len_y, len_z, force):
    '''
    input unit
    force       : kN-m
    length      : mm
    section     : mm
    design code : GB 50017-2017
    '''
    gamma_re, slender_ratio_limit = init_option
    
    class_y = sec_prop.class_y; class_z = sec_prop.class_z; gamma_y = sec_prop.gamma_y; gamma_z = sec_prop.gamma_z; 
    mat_ = sec_prop.Material; sec_type = sec_prop['Section Type']; area = sec_prop.Area
    Iyy = sec_prop.Iyy; iy = sec_prop.iy; Wy = sec_prop.Wy; Sy = sec_prop.Sy; ty = sec_prop.ty
    Izz = sec_prop.Izz; iz = sec_prop.iz; Wz = sec_prop.Wz; Sz = sec_prop.Sz; tz = sec_prop.tz
    
    Fx, Vy, Vz, Mx, My, Mz = force
    Fx *= 1.e3; Vy *= 1.e3; Vz *= 1.e3; Mx *= 1.e6; My *= 1.e6; Mz *= 1.e6
    E, fy, f, fv = mat(mat_)
    
    lambda_y = len_y/iy; lambda_z = len_z/iz
    if lambda_y > slender_ratio_limit:
        print (f'Attention: Element {el_ref} with lambda_y >{slender_ratio_limit}!')
    if lambda_z > slender_ratio_limit:
        print (f'Attention: Element {el_ref} with lambda_z >{slender_ratio_limit}!')

    # N (7.1.1)
    sigma_N  = abs(Fx)/area

    # M (6.1.1)
    sigma_My = abs(My)/(gamma_y*Wy)
    sigma_Mz = abs(Mz)/(gamma_z*Wz)
    if(sec_type == 'RHS'):
        sigma_MyMz = sigma_My + sigma_Mz
    elif(sec_type == 'CHS'):
        sigma_MyMz = sqrt(My**2+Mz**2)/Iyy

    # V (6.1.3)
    tau_Vy = Vz*Sy/(Iyy*ty)
    tau_Vz = Vy*Sz/(Izz*tz)

    # N+My+Mz (8.2.1)
    sigma_NM = sigma_N + sigma_MyMz

    # Member buckling : compression (7.2.1)
    lambda_n_y = lambda_y/pi*sqrt(fy/E)
    lambda_n_z = lambda_z/pi*sqrt(fy/E)

    phi_y = calc_phi_steel(lambda_n_y, calc_alpha(class_y,lambda_n_y))
    phi_z = calc_phi_steel(lambda_n_z, calc_alpha(class_z,lambda_n_z))
    if phi_y<0 or phi_z<0:
        print ('Error')

    sigma_Ny_buckling = abs(Fx)/phi_y/area
    sigma_Nz_buckling = abs(Fx)/phi_z/area

    # Member buckling : bending+compression(8.2.5)
    beta  = 1.0     # as a conservative value, TO DO
    eta   = 0.7     # closed section :0.7 , open section: 1.0
    phi_b = 1.0     # closed section :1.0 , open section: TO DO

    N_Ey = pi**2*E*area/(1.1*lambda_y**2)
    N_Ez = pi**2*E*area/(1.1*lambda_z**2)

    sigma_NMy_buckling = abs(Fx)/phi_y/area + beta*abs(My)/gamma_y/Wy/(1-0.8*abs(Fx)/N_Ey) + eta*beta*abs(Mz)/phi_b/Wz
    sigma_NMz_buckling = abs(Fx)/phi_z/area + beta*abs(Mz)/gamma_z/Wz/(1-0.8*abs(Fx)/N_Ez) + eta*beta*abs(My)/phi_b/Wy

    sigma_all   = np.array([sigma_N,    sigma_My,   sigma_Mz,   sigma_MyMz,   tau_Vy,    tau_Vz,    sigma_NM,   sigma_Ny_buckling,   sigma_Nz_buckling,   sigma_NMy_buckling,   sigma_NMz_buckling  ])
    utilization = np.array([sigma_N/f,  sigma_My/f, sigma_Mz/f, sigma_MyMz/f, tau_Vy/fv, tau_Vz/fv, sigma_NM/f, sigma_Ny_buckling/f, sigma_Nz_buckling/f, sigma_NMy_buckling/f, sigma_NMz_buckling/f])*gamma_re

    return utilization


def clc_phi_mullion(mat_, grade, lambda_):
    '''
    definiton by code J12028-2019 Table 13.5.3
    '''
    l = [0,20,40,60,80,90,100,110,120,130,140,150,500]
    E,fy_,f_,fv_ = mat(mat_, grade)
    phi=0
    if grade =='6063T6' or grade =='6061T6':
        lambda_clc = lambda_*sqrt(fy_/240)
        phi = [1.00,0.95,0.82,0.58,0.38,0.31,0.25,0.21,0.18,0.16,0.14,0.12,0.12]
    elif grade == '6063T5':
        lambda_clc = lambda_*sqrt(fy_/240)
        phi = [1.00,0.90,0.73,0.51,0.34,0.28,0.23,0.20,0.17,0.15,0.13,0.11,0.11]
    elif grade == 'Q235':
        lambda_clc = lambda_
        phi = [1.00,0.97,0.90,0.81,0.69,0.62,0.56,0.49,0.44,0.39,0.35,0.31,0.12]
    elif grade == 'Q355':
        lambda_clc = lambda_
        phi = [1.00,0.96,0.88,0.73,0.58,0.5,0.43,0.37,0.32,0.28,0.25,0.21,0.12]
    elif grade == 'Q420':
        lambda_clc = lambda_*sqrt(fy_/235)
        phi = [1.00,0.970,0.899,0.807,0.688,0.621,0.555,0.493,0.437,0.387,0.345,0.308,0.12]
    f = interpolate.interp1d(l, phi)
    phi = f(lambda_clc)
    return phi


def design_mullion(el_ref, mat_, grade, sec_prop, len_, force):
    '''
    input unit
    force       : kN-m
    length      : mm
    section     : mm
    '''
    slender_ratio_limit = 150
    area = sec_prop.Area.iloc[0]; tw = sec_prop.tw.iloc[0]
    Iyy = sec_prop.Ix.iloc[0]; iy = sec_prop.ix.iloc[0]; Wy = sec_prop.Wx.iloc[0]; Sy = sec_prop.Sx.iloc[0]
    Izz = sec_prop.Iy.iloc[0]; iz = sec_prop.iy.iloc[0]; Wz = sec_prop.Wy.iloc[0]; Sz = sec_prop.Sy.iloc[0]
    Fx,Vz,Vy,My,Mz = force
    Fx *= 1e3;My *= 1e6;Mz *= 1e6;Vz *=1e3;Vy *=1e3
    E,fy,f,fv = mat(mat_,grade)
    len_y = len_*1000; len_z = len_*1000

    lambda_y=len_y/iy
    lambda_z=len_z/iz

    if lambda_y > slender_ratio_limit :
        print (f'Attention: Element {el_ref} with lambda {lambda_y} >{slender_ratio_limit}!')

    phi_y = clc_phi_mullion(mat_, grade, lambda_y)
    phi_z = clc_phi_mullion(mat_, grade, lambda_z)

    if (mat_ == 'Aluminum') and ('6061T6' not in grade):
        gamma = 1.0
    else:
        gamma = 1.05

    # 13.5.2 Axial and Bending Strength
    sigma_NM = abs(Fx)/area + abs(My)/(gamma*Wy) + abs(Mz)/(gamma*Wz)
    
    # 13.4.3 Shear Strength
    tau_Vy = Vy*Sz/(Izz*tw)
    tau_Vz = Vz*Sy/(Iyy*tw)

    # 13.5.3 Stability
    if mat_ == 'Steel':
        N_Ey = pi**2*E*area/(1.1*lambda_y**2)
        N_Ez = pi**2*E*area/(1.1*lambda_z**2)
    elif mat_ == 'Aluminum':
        N_Ey = pi**2*E*area/(1.2*lambda_y**2)
        N_Ez = pi**2*E*area/(1.2*lambda_z**2)

    if Fx < 0:
        sigma_NMy_buckling = abs(Fx)/phi_y/area + abs(My)/gamma/Wy/(1-0.8*abs(Fx)/N_Ey)
        sigma_NMz_buckling = abs(Fx)/phi_z/area + abs(Mz)/gamma/Wz/(1-0.8*abs(Fx)/N_Ez)
    else:
        sigma_NMy_buckling = 0
        sigma_NMz_buckling = 0

    return [sigma_NM/f, tau_Vy/fv, tau_Vz/fv, sigma_NMy_buckling/f, sigma_NMz_buckling/f]


def calc_energy (sec, length, Fx, M):
    '''
    input unit
    force       : kN-m
    length      : mm
    section     : mm
    '''
    mat_, sec_type, gamma_x, gamma_y, class_x, class_y, area, Ixx, ix, Wx, Iyy, iy, Wy, y = sec
    My1, My2, Mz1, Mz2 = M
    Fx *= 1e3; My1 *= 1e6; My2 *=1e6; Mz1 *= 1e6; Mz2 *= 1e6
    E,fy,f,fv = mat(mat_)

    V_F  = Fx**2*length/(2*E*area)
    V_My = length/(6*E*Iyy)*(My1**2+My1*My2+My2**2)
    V_Mz = length/(6*E*Iyy)*(Mz1**2+Mz1*Mz2+Mz2**2)
    V_M  = V_My+V_Mz
    V_total = V_F+V_M

    return (V_F, V_M, V_total)