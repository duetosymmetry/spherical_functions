import numpy as np
from functools import lru_cache
from scipy.special import factorial
from numba import njit
import spherical_functions as sf

"""Algorithm for computing H, as given by arxiv:1403.7698:

Symmetry relations:
H^{m', m}_n(\beta) = H^{m, m'}_n(\beta)
H^{m', m}_n(\beta) = H^{-m', -m}_n(\beta)
H^{m', m}_n(\beta) = (-1)^{n+m+m'} H^{-m', m}_n(\pi - \beta)
H^{m', m}_n(\beta) = (-1)^{m+m'} H^{m', m}_n(-\beta)

1: If n=0 set H_{0}^{0,0}=1.

2: Compute values H^{0,m}_{n}(β)for m=0,...,n and H^{0,m}_{n+1}(β) for m=0,...,n+1 using Eq. (32):
     H^{0,m}_{n}(β) = (-1)^m \sqrt{(n-|m|)!/(n+|m|)!} P^{|m|}_{n}(cos β)

3: Use relation (41) to compute H^{1,m}_{n}(β) for m=1,...,n.  Using symmetry and shift of the
   indices this relation can be written as
     b^{0}_{n+1} H^{1,m}_{n} = \frac{b^{−m−1}_{n+1} (1−cosβ)}{2} H^{0,m+1}_{n+1}
                             − \frac{b^{m−1}_{n+1}  (1+cosβ)}{2} H^{0,m−1}_{n+1}
                             − a^{m}_{n} sinβ H^{0,m}_{n+1}

4: Recursively compute H^{m′+1,m}_{n}(β) for m′=1,...,n−1, m=m′,...,n using relation (50) resolved
   with respect to H^{m′+1,m}_{n}:
     d^{m′}_{n} H^{m′+1,m}_{n} = d^{m′−1}_{n} H^{m′−1,m}_{n}
                               − d^{m−1}_{n} H^{m′,m−1}_{n}
                               + d^{m}_{n} H^{m′,m+1}_{n}
   (where the last term drops out for m=n).

5. Recursively compute H^{m′−1,m}_{n}(β) for m′=−1,...,−n+1, m=−m′,...,n using relation (50)
   resolved with respect to H^{m′−1,m}_{n}:
     d^{m′−1}_{n} H^{m′−1,m}_{n} = d^{m′}_{n} H^{m′+1,m}_{n}
                                 + d^{m−1}_{n} H^{m′,m−1}_{n}
                                 − d^{m}_{n} H^{m′,m+1}_{n}
   (where the last term drops out for m=n).

6: Apply the first and the second symmetry relations above to obtain all other values H^{m′,m}_{n}
   outside the computational triangle m=0,...,n, m′=−m,...,m.

"""


@njit
def sign(m):
    if m >= 0:
        return 1
    else:
        return -1


@njit
def nm_index(n, m):
    """Return flat index into arrray of [n, m] pairs.
    
    Assumes array is ordered as [[n, m] for n in range(n_max+1) for m in range(-n, n+1)]

    """
    return m + n * (n + 1)


@njit
def nabsm_index(n, absm):
    """Return flat index into arrray of [n, abs(m)] pairs
    
    Assumes array is ordered as [[n, m] for n in range(n_max+1) for m in range(n+1)]

    """
    return absm + (n * (n + 1)) // 2


@njit
def nmpm_index(n, mp, m):
    """Return flat index into arrray of [n, mp, m]
    
    Assumes array is ordered as [[n, mp, m] for n in range(n_max+1) for mp in range(-n, n+1) for m in range(-n, n+1)]

    """
    return (((4 * n + 6) * n + 6 * mp + 5) * n + 3 * (m + mp)) // 3


@njit
def _step_1(Hnmpm):
    """If n=0 set H_{0}^{0,0}=1."""
    Hnmpm[0, :] = 1.0
    # print('step 1', np.all(np.isfinite(Hnmpm[0, ...])))


#@njit
def _step_2(sqrt_factorial_ratio, absm, n_max, Hnmpm, cosβ):
    """Compute values H^{0,m}_{n}(β)for m=0,...,n and H^{0,m}_{n+1}(β) for m=0,...,n+1 using Eq. (32):
        H^{0,m}_{n}(β) = (-1)^m \sqrt{(n-|m|)! / (n+|m|)!} P^{|m|}_{n}(cos β)

    NOTE: Though not specified in arxiv:1403.7698, there is not enough information for step 4 unless we
    also use symmetry to set H^{1,0}_{n} here.  Similarly, step 5 needs additional information, which
    depends on setting H^{0, -1}_{n} from its symmetric equivalent H^{0, 1}_{n} in this step.

    """
    from scipy.special import lpmv
    sqrt_factorial_ratio = sqrt_factorial_ratio.reshape(sqrt_factorial_ratio.shape + (1,)*(Hnmpm.ndim-1))
    absm = absm.reshape(absm.shape + (1,)*(Hnmpm.ndim-1))
    for n in range(1, n_max+2):
        nmpm_slice = slice(nmpm_index(n, 0, 0), nmpm_index(n, 0, n)+1)
        nabsm_slice = slice(nabsm_index(n, 0), nabsm_index(n, n)+1)
        Hnmpm[nmpm_slice, :] = sqrt_factorial_ratio[nabsm_slice] * lpmv(absm[nabsm_slice], n, cosβ)
        Hnmpm[nmpm_index(n, 1, 0), :] = Hnmpm[nmpm_index(n, 0, 1)]
        Hnmpm[nmpm_index(n, 0, -1), :] = Hnmpm[nmpm_index(n, 0, 1)]
        # print('step 2, n =', n, np.all(np.isfinite(Hnmpm[nmpm_slice, :])))


@njit
def _step_3(a, b, n_max, Hnmpm, cosβ, sinβ):
    """Use relation (41) to compute H^{1,m}_{n}(β) for m=1,...,n.  Using symmetry and shift of the
    indices this relation can be written as
        b^{0}_{n+1} H^{1, m}_{n} =   \frac{b^{−m−1}_{n+1} (1−cosβ)}{2} H^{0, m+1}_{n+1}
                                   − \frac{b^{ m−1}_{n+1} (1+cosβ)}{2} H^{0, m−1}_{n+1}
                                   − a^{m}_{n} sinβ H^{0, m}_{n+1}
    """
    # a = self.a.reshape(self.a.shape + (1,)*(Hnmpm.ndim-1))
    for n in range(1, n_max+1):
        nmpm_slice1 = slice(nmpm_index(n, 1, 1), nmpm_index(n, 1, n)+1)
        nmpm_slice2 = slice(nmpm_index(n+1, 0, 2), nmpm_index(n+1, 0, n+1)+1)
        nmpm_slice3 = slice(nmpm_index(n+1, 0, 0), nmpm_index(n+1, 0, n-1)+1)
        nmpm_slice4 = slice(nmpm_index(n+1, 0, 1), nmpm_index(n+1, 0, n)+1)
        nm_slice1 = slice(nm_index(n+1, 0), nm_index(n+1, 0)+1)
        nm_slice2 = slice(nm_index(n+1, -2), nm_index(n+1, -n-1)-1, -1)
        nm_slice3 = slice(nm_index(n+1, 0), nm_index(n+1, n-1)+1)
        nm_slice4 = slice(nabsm_index(n, 1), nabsm_index(n, n)+1)
        for j in range(Hnmpm.shape[1]):
            Hnmpm[nmpm_slice1, j] = (1 / b[nm_slice1]) * (
                0.5 * (
                      b[nm_slice2] * (1-cosβ[j]) * Hnmpm[nmpm_slice2, j]
                    - b[nm_slice3] * (1+cosβ[j]) * Hnmpm[nmpm_slice3, j]
                )
                - a[nm_slice4] * sinβ[j] * Hnmpm[nmpm_slice4, j]
            )
        # print('step 3, n =', n, np.all(np.isfinite(Hnmpm[nmpm_slice1, :])))


@njit
def _step_4(d, n_max, Hnmpm):
    """Recursively compute H^{m'+1, m}_{n}(β) for m'=1,...,n−1, m=m',...,n using relation (50) resolved
    with respect to H^{m'+1, m}_{n}:
      d^{m'}_{n} H^{m'+1, m}_{n} =   d^{m'−1}_{n} H^{m'−1, m}_{n}
                                   − d^{m−1}_{n} H^{m', m−1}_{n}
                                   + d^{m}_{n} H^{m', m+1}_{n}
    (where the last term drops out for m=n).

    """
    for n in range(2, n_max+1):
        for mp in range(1, n):
            # m = m', ..., n-1
            i1 = nmpm_index(n, mp+1, mp)
            i2 = nmpm_index(n, mp-1, mp)
            i3 = nmpm_index(n, mp, mp-1)
            i4 = nmpm_index(n, mp, mp+1)
            i5 = nm_index(n, mp)
            i6 = nm_index(n, mp-1)
            for i in range(n-mp):
                for j in range(Hnmpm.shape[1]):
                    Hnmpm[i+i1, j] = (1 / d[i5]) * (
                          d[i6] * Hnmpm[i+i2, j]
                        - d[i+i6] * Hnmpm[i+i3, j]
                        + d[i+i5] * Hnmpm[i+i4, j]
                    )
            # m = n
            i = n-mp
            for j in range(Hnmpm.shape[1]):
                Hnmpm[i+i1, j] = (1 / d[i5]) * (
                      d[i6] * Hnmpm[i+i2, j]
                    - d[i+i6] * Hnmpm[i+i3, j]
                )
            # print('step 4, n =', n, ' mp =', mp,
            #       np.all(np.isfinite(Hnmpm[nmpm_slice1, :])),
            #       np.all(np.isfinite(Hnmpm[nmpm_index(n, mp+1, n), :])))


@njit
def _step_5(d, n_max, Hnmpm):
    """Recursively compute H^{m'−1, m}_{n}(β) for m'=−1,...,−n+1, m=−m',...,n using relation (50)
    resolved with respect to H^{m'−1, m}_{n}:
      d^{m'−1}_{n} H^{m'−1, m}_{n} = d^{m'}_{n} H^{m'+1, m}_{n}
                                     + d^{m−1}_{n} H^{m', m−1}_{n}
                                     − d^{m}_{n} H^{m', m+1}_{n}
    (where the last term drops out for m=n).

    NOTE: Although arxiv:1403.7698 specifies the loop over mp to start at -1, I find it necessary to
    start at 0, or there will be missing information.  This also requires setting the (m',m)=(0,-1)
    components before beginning this loop.

    """
    for n in range(0, n_max+1):
        for mp in range(0, -n, -1):
            # m = -m', ..., n-1
            i1 = nmpm_index(n, mp-1, -mp)
            i2 = nmpm_index(n, mp+1, -mp)
            i3 = nmpm_index(n, mp, -mp-1)
            i4 = nmpm_index(n, mp, -mp+1)
            i5 = nm_index(n, mp-1)
            i6 = nm_index(n, mp)
            i7 = nm_index(n, -mp-1)
            i8 = nm_index(n, -mp)
            for i in range(n+mp):
                for j in range(Hnmpm.shape[1]):
                    Hnmpm[i+i1, j] = (1 / d[i5]) * (
                          d[i6] * Hnmpm[i+i2, j]
                        + d[i+i7] * Hnmpm[i+i3, j]
                        - d[i+i8] * Hnmpm[i+i4, j]
                    )
            # m = n
            i = n+mp
            for j in range(Hnmpm.shape[1]):
                Hnmpm[i+i1, j] = (1 / d[i5]) * (
                      d[i6] * Hnmpm[i+i2, j]
                    + d[i+i7] * Hnmpm[i+i3, j]
                )
            # print('step 5, n =', n, ' mp =', mp,
            #       np.all(np.isfinite(Hnmpm[nmpm_slice1, :])),
            #       np.all(np.isfinite(Hnmpm[nmpm_index(n, mp-1, n), :])))


@njit
def _step_6(n_max, Hnmpm):
    """Apply the symmetry relations below to obtain all other values H^{m',m}_{n}
    outside the computational triangle m=0,...,n, m'=−m,...,m:
      H^{m', m}_n(\beta) = H^{m, m'}_n(\beta)
      H^{m', m}_n(\beta) = H^{-m', -m}_n(\beta)
    """
    for n in range(1, n_max+1):
        for mp in range(1, n+1):
            for m in range(max(-mp-1, -n), mp-1):
                for j in range(Hnmpm.shape[1]):
                    Hnmpm[nmpm_index(n, mp, m), j] = Hnmpm[nmpm_index(n, m, mp), j]
        for mp in range(-n, n+1):
            for m in range(-n, -mp-1):
                for j in range(Hnmpm.shape[1]):
                    Hnmpm[nmpm_index(n, mp, m), j] = Hnmpm[nmpm_index(n, -mp, -m), j]


class HCalculator(object):
    def __init__(self, n_max):
        self.n_max = int(n_max)
        if self.n_max < 0:
            raise ValueError('Nonsensical value for n_max = {0}'.format(self.n_max))
        self.nmpm_total_size = sf.LMpM_total_size(0, self.n_max)
        self.nmpm_total_size_plus1 = sf.LMpM_total_size(0, self.n_max+1)
        n = np.array([n for n in range(self.n_max+2) for m in range(-n, n+1)])
        m = np.array([m for n in range(self.n_max+2) for m in range(-n, n+1)])
        absn = np.array([n for n in range(self.n_max+2) for m in range(n+1)])
        absm = np.array([m for n in range(self.n_max+2) for m in range(n+1)])
        self.sqrt_factorial_ratio = (-1)**absm * np.sqrt(
            np.asarray(factorial(absn-absm, exact=True) / factorial(absn+absm, exact=True), dtype=float))
        self.a = np.sqrt((absn+1+absm) * (absn+1-absm) / ((2*absn+1)*(2*absn+3)))
        self.b = np.sqrt((n-m-1) * (n-m) / ((2*n-1)*(2*n+1)))
        self.b[m<0] *= -1
        self.d = 0.5 * np.sqrt((n-m) * (n+m+1))
        self.d[m<0] *= -1
        self.absm = absm
        if not (
            np.all(np.isfinite(self.sqrt_factorial_ratio)) and
            np.all(np.isfinite(self.a)) and
            np.all(np.isfinite(self.b)) and
            np.all(np.isfinite(self.d)) and
            np.all(np.isfinite(self.absm))
        ):
            raise ValueError("Found a non-finite value inside this object")

    def workspace(self, cosβ):
        """Return a new workspace sized for cosβ."""
        return np.zeros((self.nmpm_total_size_plus1,) + cosβ.shape, dtype=float)

    def __call__(self, cosβ, workspace=None):
        cosβ = np.asarray(cosβ, dtype=float)
        if np.max(cosβ) > 1.0 or np.min(cosβ) < -1.0:
            raise ValueError('Nonsensical value for range of cosβ: [{0}, {1}]'.format(np.min(cosβ), np.max(cosβ)))
        cosβshape = cosβ.shape
        Hnmpm = workspace if workspace is not None else self.workspace(cosβ)
        cosβ = cosβ.ravel(order='K')
        sinβ = np.sqrt(1 - cosβ**2)
        Hnmpm = Hnmpm.reshape((-1, int(np.prod(cosβshape))))
        _step_1(Hnmpm)
        _step_2(self.sqrt_factorial_ratio, self.absm, self.n_max, Hnmpm, cosβ)
        _step_3(self.a, self.b, self.n_max, Hnmpm, cosβ, sinβ)
        _step_4(self.d, self.n_max, Hnmpm)
        _step_5(self.d, self.n_max, Hnmpm)
        _step_6(self.n_max, Hnmpm)
        Hnmpm.reshape((-1,)+cosβshape)
        return Hnmpm[:self.nmpm_total_size]  # Remove n_max+1 scratch space
