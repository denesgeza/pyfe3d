import sys
sys.path.append('..')

import numpy as np
from scipy.sparse.linalg import eigsh
from scipy.sparse import coo_matrix

from pyfe3d.beamprop import BeamProp
from pyfe3d import Spring, SpringData, SpringProbe
from pyfe3d import BeamC, BeamCData, BeamCProbe, DOF, INT, DOUBLE

def test_nat_freq_cantilever(refinement=1, mtypes=range(2)):
    for mtype in mtypes:
        print('mtype', mtype)
        n = 50*refinement
        L = 3 # total size of the beam along x

        # Material Lastrobe Lescalloy
        E = 203.e9 # Pa
        rho = 7.83e3 # kg/m3

        x = np.zeros(n+1)
        x[0] = -L/100
        x[1:] = np.linspace(0, L, n)
        # path
        y = np.ones_like(x)
        # tapered properties
        b = 0.05 # m
        h = 0.05 # m
        A = h*b
        Izz = b*h**3/12
        Iyy = b**3*h/12

        # getting nodes
        ncoords = np.vstack((x, y, np.zeros_like(x))).T
        nids = 1 + np.arange(ncoords.shape[0])
        nid_pos = dict(zip(nids, np.arange(len(nids))))

        num_elements = len(ncoords) - 1
        print('num_elements', num_elements)

        p = BeamCProbe()
        beamdata = BeamCData()

        springdata = SpringData()
        springprobe = SpringProbe()

        KC0r = np.zeros(springdata.KC0_SPARSE_SIZE*1 + beamdata.KC0_SPARSE_SIZE*(num_elements-1), dtype=INT)
        KC0c = np.zeros(springdata.KC0_SPARSE_SIZE*1 + beamdata.KC0_SPARSE_SIZE*(num_elements-1), dtype=INT)
        KC0v = np.zeros(springdata.KC0_SPARSE_SIZE*1 + beamdata.KC0_SPARSE_SIZE*(num_elements-1), dtype=DOUBLE)
        Mr = np.zeros(beamdata.M_SPARSE_SIZE*num_elements, dtype=INT)
        Mc = np.zeros(beamdata.M_SPARSE_SIZE*num_elements, dtype=INT)
        Mv = np.zeros(beamdata.M_SPARSE_SIZE*num_elements, dtype=DOUBLE)
        N = DOF*(n + 1)
        print('num_DOF', N)

        prop = BeamProp()
        prop.A = A
        prop.E = E
        scf = 5/6.
        prop.G = scf*E/2/(1+0.3)
        prop.Izz = Izz
        prop.Iyy = Iyy
        prop.J = Iyy + Izz
        prop.intrho = rho*A
        prop.intrhoy2 = rho*Izz
        prop.intrhoz2 = rho*Iyy

        ncoords_flatten = ncoords.flatten()

        init_k_KC0 = 0
        init_k_M = 0

        # assemblying spring element
        spring = Spring(springprobe)
        spring.init_k_KC0 = init_k_KC0
        spring.n1 = 0
        spring.n2 = 1
        spring.c1 = 0*DOF
        spring.c2 = 1*DOF
        spring.kxe = spring.kye = spring.kze = 1e9
        spring.krxe = spring.krye = spring.krze = 1e9
        spring.update_rotation_matrix(1, 0, 0, 1, 1, 0)
        spring.update_KC0(KC0r, KC0c, KC0v)
        init_k_KC0 += springdata.KC0_SPARSE_SIZE

        # assemblying beam elements
        n1s = nids[1:-1]
        n2s = nids[2:]
        for n1, n2 in zip(n1s, n2s):
            pos1 = nid_pos[n1]
            pos2 = nid_pos[n2]
            beam = BeamC(p)
            beam.init_k_KC0 = init_k_KC0
            beam.init_k_M = init_k_M
            beam.n1 = n1
            beam.n2 = n2
            beam.c1 = DOF*pos1
            beam.c2 = DOF*pos2
            beam.update_rotation_matrix(1., 1., 0, ncoords_flatten)
            beam.update_probe_xe(ncoords_flatten)
            beam.update_KC0(KC0r, KC0c, KC0v, prop)
            beam.update_M(Mr, Mc, Mv, prop, mtype=mtype)
            init_k_KC0 += beamdata.KC0_SPARSE_SIZE
            init_k_M += beamdata.M_SPARSE_SIZE

        print('elements created')

        KC0 = coo_matrix((KC0v, (KC0r, KC0c)), shape=(N, N)).tocsc()
        M = coo_matrix((Mv, (Mr, Mc)), shape=(N, N)).tocsc()

        print('sparse KC0 and M created')

        # applying boundary conditions
        bk = np.zeros(N, dtype=bool) #array to store known DOFs
        check = np.isclose(x, -L/100)
        # clamping
        bk[0::DOF][check] = True # u
        bk[1::DOF][check] = True # v
        bk[2::DOF][check] = True # w
        bk[3::DOF][check] = True # rx
        bk[4::DOF][check] = True # ry
        bk[5::DOF][check] = True # rz

        bu = ~bk # same as np.logical_not, defining unknown DOFs

        # sub-matrices corresponding to unknown DOFs
        Kuu = KC0[bu, :][:, bu]
        Muu = M[bu, :][:, bu]

        num_eigenvalues = 6
        eigvals, eigvecsu = eigsh(A=Kuu, M=Muu, sigma=-1., which='LM',
                k=num_eigenvalues, tol=1e-4)
        omegan = eigvals**0.5

        eigvec = np.zeros(N)
        eigvec[bu] = eigvecsu[:, 0]
        spring.update_probe_ue(eigvec)

        alpha123 = np.array([1.875, 4.694, 7.885])
        omega123 = alpha123**2*np.sqrt(E*Izz/(rho*A*L**4))
        print('Theoretical omega123', omega123)
        print('Numerical omega123', omegan)
        print()
        assert np.allclose(np.repeat(omega123, 2), omegan, rtol=0.015)

if __name__ == '__main__':
    test_nat_freq_cantilever(refinement=1)
