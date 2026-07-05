# -*- coding: utf-8 -*-
"""
 Title:  36-intesnity image algorithm for recover Mueller matrix                                                                   
                                                                              
 This algorithm allows to recover the Mueller matrix of a sample based on the 
 36-intensity-images method, and calculates the Diattenuation,Polarizance     
 Depolarization and Angle of polarization of the sample, based on the         
 calculated matrix.                                                            
                                                                              
 If using this code for publishing your results, please kindly cite us:       
 S. Obando-Vasquez, A. Doblas, and C. Trujillo, 
 “Apparatus and method to estimate the Mueller matrix in bright-field microscopy,” 
 Applied Optics, under review (2021).                                                                             
                                                                              
 Authors: Sofia Obando-Vasquez, Ana Doblas and Carlos Trujillo                
 Department of Physical Science                                               
 University EAFIT                                                             
 Medellin, Colombia.                                                           
                                                                               
 Department of Electrical and Computer Engineering                            
 The University of Memphis                                                    
 Memphis, TN 38152, USA.                                                         
                                                                              
 Department of Physical Science                                               
 University EAFIT                                                             
 Medellin, Colombia.                                                          
                                                                              
 Email: sobandov@eafit.edu.co, adoblas@memphis.edu and catrujilla@eafit.edu.co
 version 1.0 (2021)                                                           
                                                                              
 ------------------------------Specifications--------------------------------- 
 Input:                                                                       
     folder = Direction where the 36-intensity-images are stored.              
                                                                              
 Output: 
     Mueller_matrix = Matrix with the 16 elements of the Mueller matrix of the
                      sample.                                                 
     Pseudo_color = Matrix with the Diattenuation, Polarizance and            
                    Depolarizance of the sample.  
     Polarization angle = Angle of polarization. Only accurate if the sample  
                          is a Linear polarizer                               
                                                                              
"""

import importlib.util
import subprocess
import sys

_REQUIRED_PACKAGES = {
    "numpy": "numpy",
    "matplotlib": "matplotlib",
}


def _ensure_dependencies() -> None:
    """Install any of this script's required packages that aren't already
    present, using the same Python interpreter running this script. Falls
    back to --break-system-packages if a plain install is blocked by an
    externally-managed environment (PEP 668, e.g. a uv-managed Python)."""

    missing = [pip_name for module_name, pip_name in _REQUIRED_PACKAGES.items()
               if importlib.util.find_spec(module_name) is None]
    if not missing:
        return

    print(f"Installing missing dependencies: {', '.join(missing)}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
    except subprocess.CalledProcessError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--break-system-packages", *missing]
        )


_ensure_dependencies()

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
import time
import math

# Load images 
#Please change the name of each file with your own.

HH=mpimg.imread('')
HH=HH/255

N=HH.shape[0]
M=HH.shape[1]

x=int(M/2)
y=int(N/2)

HV=mpimg.imread('')
HV=HV/255

VH=mpimg.imread('')
VH=VH/255

VV=mpimg.imread('')
VV=VV/255

PH=mpimg.imread('')
PH=PH/255

PV=mpimg.imread('')
PV=PV/255

MH=mpimg.imread('')
MH=MH/255

MV=mpimg.imread('')
MV=MV/255

RH=mpimg.imread('')
RH=RH/255

RV=mpimg.imread('')
RV=RV/255

LH=mpimg.imread('')
LH=LH/255

LV=mpimg.imread('')
LV=LV/255

HP=mpimg.imread('')
HP=HP/255

HM=mpimg.imread('')
HM=MH/255

VP=mpimg.imread('')
VP=VP/255

VM=mpimg.imread('')
VM=VM/255

PP=mpimg.imread('')
PP=PP/255

PM=mpimg.imread('')
PM=PM/255

MP=mpimg.imread('')
MP=MP/255

MM=mpimg.imread('')
MM=MM/255

RP=mpimg.imread('')
RP=RP/255

RM=mpimg.imread('')
RM=RM/255

LP=mpimg.imread('')
LP=LP/255

LM=mpimg.imread('')
LM=LM/255

HR=mpimg.imread('')
HR=HR/255

HL=mpimg.imread('')
HL=HL/255

VR=mpimg.imread('')
VR=VR/255

VL=mpimg.imread('')
VL=VL/255

PR=mpimg.imread('')
PR=PR/255

PL=mpimg.imread('')
PL=PL/255

MR=mpimg.imread('')
MR=MR/255

ML=mpimg.imread('')
ML=ML/255

LL=mpimg.imread('')
LL=LL/255

RL=mpimg.imread('')
RL=RL/255

LR=mpimg.imread('')
LR=LR/255

RR=mpimg.imread('')
RR=RR/255

print('loaded images')

#%% Calculate the matrix elements

m00=HH+HV+VH+VV
prom=np.mean(m00)
m00=m00/prom
m00=np.single(m00)

m01=HH+HV-VH-VV
m01=m01/prom
m01=np.single(m01)

m02=PH+PV-MH-MV
m02=m02/prom
m02=np.single(m02)

m03=RH+RV-LH-LV
m03=m03/prom
m03=np.single(m03)

m10=HH-HV+VH-VV
m10=m10/prom
m10=np.single(m10)

m11=HH-HV-VH+VV
m11=m11/prom
m11=np.single(m11)

m12=PH-PV-MH+MV
m12=m12/prom
m12=np.single(m12)

m13=RH-RV-LH+LV
m13=m13/prom
m13=np.single(m13)

m20=HP-HM+VP-VM
m20=m20/prom
m20=np.single(m20)

m21=HP-HM-VP+VM
m21=m21/prom
m21=np.single(m21)

m22=PP-PM-MP+MM
m22=m22/prom
m22=np.single(m22)

m23=RP-RM-LP+LM
m23=m23/prom
m23=np.single(m23)

m30=HR-HL+VR-VL
m30=m30/prom
m30=np.single(m30)

m31=HR-HL-VR+VL
m31=m31/prom
m31=np.single(m31)

m32=PR-PL-MR+ML
m32=m32/prom
m32=np.single(m32)

m33=LL-RL-LR+RR
m33=m33/prom
m33=np.single(m33)

print('matrix calculated')


# %% Subplot of the Mueller matrix elements
fig, ax_list = plt.subplots(4, 4)
mlist = [m00, m01, m02, m03,
          m10, m11, m12, m13,
          m20, m21, m22, m23,
          m30, m31, m32, m33]

for ax, m in zip(ax_list.flat, mlist):
    im = ax.imshow(m,  cmap='gray', vmin=-1, vmax=1)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.label_outer()

fig.subplots_adjust(right=0.8)
cbar_ax = fig.add_axes([0.85, 0.15, 0.05, 0.7])
fig.colorbar(im, cax=cbar_ax)
fig.suptitle('Recovered matrix sample polarizer')
plt.show()

# %% Polar de composition

print('polar decomposition starts')

# Mean matrix from the experimental matrix
experimental_mean_matrix=np.array([[np.mean(m00), np.mean(m01), np.mean(m02), np.mean(m03)],\
                        [np.mean(m10), np.mean(m11), np.mean(m12), np.mean(m13)],\
                        [np.mean(m20), np.mean(m21), np.mean(m22), np.mean(m23)],\
                        [np.mean(m30), np.mean(m31), np.mean(m32), np.mean(m33)]])

# Change the size of N for change the size of the subregion from the Mueller
# matrix used for calculate the polarization properties. Those are
# calculated in a region of NxM size.    
N=128
M=N
    
Pseudo_color=np.array(np.zeros((N,M,3)))
MDia=np.zeros([4,4])
MPol=np.zeros([4,4])
MDia[0,0]=1
MPol[0,0]=1

start1 = time.time()
for i in range((N)): 
    for j in  range((M)):

        Current_Mueller=np.array([[m00[i,j], m01[i,j], m02[i,j], m03[i,j]],\
                        [m10[i,j], m11[i,j], m12[i,j], m13[i,j]],\
                        [m20[i,j], m21[i,j], m22[i,j], m23[i,j]],\
                        [m30[i,j], m31[i,j], m32[i,j], m33[i,j]]])
        if m00[i,j]==0:
            m00[i,j]=0.000001
                  
        Normal_mueller= m00[i,j]
        Current_Mueller=Current_Mueller/Normal_mueller

        # DIATENUATION AND IT'S MATRIX
        D_value=np.sqrt(Current_Mueller[0,1]**2+Current_Mueller[0,2]**2+Current_Mueller[0,3]**2)
        if D_value>2:
            Pseudo_color[i,j,0]=0
        else:
            Pseudo_color[i,j,0]=D_value

        D=np.array([[Current_Mueller[0,1]], [Current_Mueller[0,2]], [Current_Mueller[0,3]]])

        # Assignment of the values ​​to the matrix
        MDia[0,1:4]=D.T 
        MDia[1:4,0:1]=D
        
        Identy=np.eye(3)
        D_mod=np.round(np.linalg.norm(D),3)
        
        if D_mod==0: 
            D[0,0]=D[0,0]+0.01 
            D_mod=np.round(np.linalg.norm(D),3)

            
        if D_mod>=1:
            D_mod=0.999
            
        D_uni=(1/D_mod)*D
        Raiz=np.sqrt(1-D_mod**2)
        md=Raiz*Identy+(1-Raiz)*(D_uni @ (D_uni.T))
        
        # Assignment of the values ​​to the matrix
        MDia[1:4,1:4]=md
        
        # Multiply the original mueller matrix by the diattenuation matrix
        M_prim=(Current_Mueller @ np.linalg.pinv(MDia))
        
        # POLARIZANCE AND IT'S MATRIX
       
        P_value=np.sqrt(Current_Mueller[1,0]**2+Current_Mueller[2,0]**2+Current_Mueller[3,0]**2)
        if P_value>2:
            Pseudo_color[i,j,1]=0
        else:
            Pseudo_color[i,j,1]=P_value
        
        Pol_vector= np.array([[Current_Mueller[1,0]], [Current_Mueller[2,0]], [Current_Mueller[3,0]]])
        
        # DEPOLARIZATION
        if Current_Mueller[0,0]==0:
            DP_value=0
        else: 
            DP_value=1-(np.sqrt(((Current_Mueller[1,1]**2+Current_Mueller[2,2]**2+Current_Mueller[3,3]**2+Current_Mueller[0,0]**2)-Current_Mueller[0,0]**2))/(np.sqrt(3)*Current_Mueller[0,0]))
            Pseudo_color[i,j,2]=DP_value
            if DP_value==np.nan:
                Pseudo_color[i,j,2]=0
            if DP_value==np.inf:
                Pseudo_color[i,j,2]=0
            if DP_value==-np.inf:
                Pseudo_color[i,j,2]=0
            if DP_value==-np.nan:
                Pseudo_color[i,j,2]=0

                
end1 = time.time()
print('Time for calculate properties (min): ', (end1 - start1)/60)
print('Mean diatenuation', np.mean(Pseudo_color[:,:,0]))
print('Mean polarizance', np.mean(Pseudo_color[:,:,1]))
print('Mean depolarization', np.mean(Pseudo_color[:,:,2]))
angulo=(1/2)*math.atan2(np.sqrt(experimental_mean_matrix[3,0]**2+experimental_mean_matrix[2,0]**2),experimental_mean_matrix[1,0])
print('Polarization angle', angulo*180/np.pi)

#%% Uncomment if whant to plot each polarization property

# plt.figure()
# plt.imshow(Pseudo_color[:,:,0], cmap='inferno', vmin=0, vmax=0.8)
# plt.title('Diateniacion con rango fijo')
# plt.colorbar()
# plt.show()

# # plt.imsave('Diattenuation.bmp', Pseudo_color[:,:,0], cmap='inferno', vmin=0, vmax=0.8)

# plt.figure()
# plt.imshow(Pseudo_color[:,:,1], cmap='viridis', vmin=0, vmax=0.6)
# plt.title('polarizance')
# plt.colorbar()
# plt.show()

# # plt.imsave('Polarizance.bmp', Pseudo_color[:,:,1], cmap='viridis', vmin=0, vmax=0.6)

# plt.figure()
# plt.imshow(Pseudo_color[:,:,2], cmap='plasma', vmin=0.2, vmax=0.5)
# plt.title('Retardance')
# plt.colorbar()
# plt.show()

# # plt.imsave('Retardance.bmp', Pseudo_color[:,:,2], cmap='plasma', vmin=0.2, vmax=0.5)

# plt.figure()
# plt.imshow(Pseudo_color[:,:,3], cmap='viridis', vmin=0, vmax=0.3)
# plt.title('depolarizance')
# plt.colorbar()
# plt.show()

# # plt.imsave('depolarizance.bmp', Pseudo_color[:,:,3], cmap='viridis', vmin=0, vmax=0.3)

