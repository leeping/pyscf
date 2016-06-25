#!/usr/bin/env python
#
# Author: Qiming Sun <osirpt.sun@gmail.com>
#

import numpy
import pyscf.lib
from pyscf.fci import cistring

def contract_1e(f1e, fcivec, norb, nelec):
    if isinstance(nelec, (int, numpy.integer)):
        nelecb = nelec//2
        neleca = nelec - nelecb
    else:
        neleca, nelecb = nelec
    link_indexa = cistring.gen_linkstr_index(range(norb), neleca)
    link_indexb = cistring.gen_linkstr_index(range(norb), nelecb)
    na = cistring.num_strings(norb, neleca)
    nb = cistring.num_strings(norb, nelecb)
    ci0 = fcivec.reshape(na,nb)
    t1 = numpy.zeros((norb,norb,na,nb))
    for str0, tab in enumerate(link_indexa):
        for a, i, str1, sign in tab:
            t1[a,i,str1] += sign * ci0[str0]
    for str0, tab in enumerate(link_indexb):
        for a, i, str1, sign in tab:
            t1[a,i,:,str1] += sign * ci0[:,str0]
    fcinew = numpy.dot(f1e.reshape(-1), t1.reshape(-1,na*nb))
    return fcinew.reshape(fcivec.shape)


def contract_2e(eri, fcivec, norb, nelec, opt=None):
    if isinstance(nelec, (int, numpy.integer)):
        nelecb = nelec//2
        neleca = nelec - nelecb
    else:
        neleca, nelecb = nelec
    link_indexa = cistring.gen_linkstr_index(range(norb), neleca)
    link_indexb = cistring.gen_linkstr_index(range(norb), nelecb)
    na = cistring.num_strings(norb, neleca)
    nb = cistring.num_strings(norb, nelecb)
    ci0 = fcivec.reshape(na,nb)
    t1 = numpy.zeros((norb,norb,na,nb))
    for str0, tab in enumerate(link_indexa):
        for a, i, str1, sign in tab:
            t1[a,i,str1] += sign * ci0[str0]
    for str0, tab in enumerate(link_indexb):
        for a, i, str1, sign in tab:
            t1[a,i,:,str1] += sign * ci0[:,str0]
    t1 = numpy.dot(eri.reshape(norb*norb,-1), t1.reshape(norb*norb,-1))
    t1 = t1.reshape(norb,norb,na,nb)
    fcinew = numpy.zeros_like(ci0)
    for str0, tab in enumerate(link_indexa):
        for a, i, str1, sign in tab:
            fcinew[str1] += sign * t1[a,i,str0]
    for str0, tab in enumerate(link_indexb):
        for a, i, str1, sign in tab:
            fcinew[:,str1] += sign * t1[a,i,:,str0]
    return fcinew.reshape(fcivec.shape)


def absorb_h1e(h1e, eri, norb, nelec, fac=1):
    '''Modify 2e Hamiltonian to include 1e Hamiltonian contribution.
    '''
    if not isinstance(nelec, (int, numpy.integer)):
        nelec = sum(nelec)
    eri = eri.copy()
    h2e = pyscf.ao2mo.restore(1, eri, norb)
    f1e = h1e - numpy.einsum('jiik->jk', h2e) * .5
    f1e = f1e * (1./(nelec+1e-100))
    for k in range(norb):
        h2e[k,k,:,:] += f1e
        h2e[:,:,k,k] += f1e
    return h2e * fac


def make_hdiag(h1e, g2e, norb, nelec, opt=None):
    if isinstance(nelec, (int, numpy.integer)):
        nelecb = nelec//2
        neleca = nelec - nelecb
    else:
        neleca, nelecb = nelec
    link_indexa = cistring.gen_linkstr_index(range(norb), neleca)
    link_indexb = cistring.gen_linkstr_index(range(norb), nelecb)
    occslista = [tab[:neleca,0] for tab in link_indexa]
    occslistb = [tab[:nelecb,0] for tab in link_indexb]
    g2e = ao2mo.restore(1, g2e, norb)
    diagj = numpy.einsum('iijj->ij',g2e)
    diagk = numpy.einsum('ijji->ij',g2e)
    hdiag = []
    for aocc in occslista:
        for bocc in occslistb:
            e1 = h1e[aocc,aocc].sum() + h1e[bocc,bocc].sum()
            e2 = diagj[aocc][:,aocc].sum() + diagj[aocc][:,bocc].sum() \
               + diagj[bocc][:,aocc].sum() + diagj[bocc][:,bocc].sum() \
               - diagk[aocc][:,aocc].sum() - diagk[bocc][:,bocc].sum()
            hdiag.append(e1 + e2*.5)
    return numpy.array(hdiag)

def kernel(h1e, g2e, norb, nelec):

    h2e = absorb_h1e(h1e, g2e, norb, nelec, .5)

    na = cistring.num_strings(norb, nelec//2)
    ci0 = numpy.zeros((na,na))
    ci0[0,0] = 1

    def hop(c):
        hc = contract_2e(h2e, c, norb, nelec)
        return hc.reshape(-1)
    hdiag = make_hdiag(h1e, g2e, norb, nelec)
    precond = lambda x, e, *args: x/(hdiag-e+1e-4)
    e, c = pyscf.lib.davidson(hop, ci0.reshape(-1), precond)
    return e


# dm_pq = <|p^+ q|>
def make_rdm1(fcivec, norb, nelec, opt=None):
    link_index = gen_linkstr_index(range(norb), nelec//2)
    na = num_strings(norb, nelec//2)
    fcivec = fcivec.reshape(na,na)
    rdm1 = numpy.zeros((norb,norb))
    for str0, tab in enumerate(link_index):
        for a, i, str1, sign in link_index[str0]:
            rdm1[a,i] += sign * numpy.dot(fcivec[str1],fcivec[str0])
    for str0, tab in enumerate(link_index):
        for k in range(na):
            for a, i, str1, sign in link_index[str0]:
                rdm1[a,i] += sign * fcivec[k,str1]*fcivec[k,str0]
    return rdm1

# dm_pq,rs = <|p^+ q r^+ s|>
def make_rdm12(fcivec, norb, nelec, opt=None):
    link_index = gen_linkstr_index(range(norb), nelec//2)
    na = num_strings(norb, nelec//2)
    fcivec = fcivec.reshape(na,na)

    rdm1 = numpy.zeros((norb,norb))
    rdm2 = numpy.zeros((norb,norb,norb,norb))
    for str0, tab in enumerate(link_index):
        t1 = numpy.zeros((na,norb,norb))
        for a, i, str1, sign in link_index[str0]:
            for k in range(na):
                t1[k,i,a] += sign * fcivec[str1,k]

        for k, tab in enumerate(link_index):
            for a, i, str1, sign in tab:
                t1[k,i,a] += sign * fcivec[str0,str1]

        rdm1 += numpy.einsum('m,mij->ij', fcivec[str0], t1)
        # i^+ j|0> => <0|j^+ i, so swap i and j
        rdm2 += numpy.einsum('mij,mkl->jikl', t1, t1)
    return reorder_rdm(rdm1, rdm2)


def reorder_rdm(rdm1, rdm2):
    '''reorder from rdm2(pq,rs) = <E^p_q E^r_s> to rdm2(pq,rs) = <e^{pr}_{qs}>.
    Although the "reoredered rdm2" is still in Mulliken order (rdm2[e1,e1,e2,e2]),
    it is the right 2e DM (dotting it with int2e gives the energy of 2e parts)
    '''
    nmo = rdm1.shape[0]
    if inplace:
        rdm2 = rdm2.reshape(nmo,nmo,nmo,nmo)
    else:
        rdm2 = rdm2.copy().reshape(nmo,nmo,nmo,nmo)
    for k in range(nmo):
        rdm2[:,k,k,:] -= rdm1
    return rdm1, rdm2


if __name__ == '__main__':
    from functools import reduce
    from pyscf import gto
    from pyscf import scf
    from pyscf import ao2mo

    mol = gto.Mole()
    mol.verbose = 0
    mol.output = None
    mol.atom = [
        ['H', ( 1.,-1.    , 0.   )],
        ['H', ( 0.,-1.    ,-1.   )],
        ['H', ( 1.,-0.5   ,-1.   )],
        ['H', ( 0.,-0.    ,-1.   )],
        ['H', ( 1.,-0.5   , 0.   )],
        ['H', ( 0., 1.    , 1.   )],
    ]
    mol.basis = 'sto-3g'
    mol.build()

    m = scf.RHF(mol)
    m.kernel()
    norb = m.mo_coeff.shape[1]
    nelec = mol.nelectron - 2
    h1e = reduce(numpy.dot, (m.mo_coeff.T, m.get_hcore(), m.mo_coeff))
    eri = ao2mo.incore.general(m._eri, (m.mo_coeff,)*4, compact=False)
    eri = eri.reshape(norb,norb,norb,norb)

    e1 = kernel(h1e, eri, norb, nelec)
    print(e1, e1 - -7.9766331504361414)
