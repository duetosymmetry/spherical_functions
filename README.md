# Spherical Functions

Python/numba package for evaluating and transforming Wigner's 𝔇
matrices, Wigner's 3-j symbols, and spin-weighted (and scalar)
spherical harmonics.  These functions are evaluated directly in terms
of quaternions, as well as in the more standard forms of spherical
coordinates and Euler angles.<sup>[1](#1-euler-angles-are-awful)</sup>

The conventions for this package are described in detail on
[this page](http://moble.github.io/spherical_functions/).

## Dependencies

The only true requirements for this code are `python` and `numpy`, as
well as my accompanying
[`quaternion`](https://github.com/moble/numpy_quaternion) package
(installation for the latter is shown below).

However, this package can automatically use
[`numba`](http://numba.pydata.org/), which uses
[LLVM](http://llvm.org/) to compile python code to machine code,
accelerating most numerical functions by factors of anywhere from 2
to 2000.  It is *possible* to run the code without `numba`, but the
most important functions are roughly 10 times slower without it.

The only drawback of `numba` is that it is nontrivial to install on
its own.  Fortunately, the best python installer,
[`anaconda`](http://continuum.io/downloads), makes it trivial.  Just
install the main `anaconda` package.

If you prefer the smaller download size of
[`miniconda`](http://conda.pydata.org/miniconda.html) (which comes
with no extras beyond python), you'll also have to run this command:

```sh
conda install pip numpy numba
```


## Installation

Installation of this package and the `quaternion` package is simple:

```sh
pip install git+git://github.com/moble/numpy_quaternions@master
pip install git+git://github.com/moble/spherical_functions@master
```

If you refuse to use anaconda, you might want to use `pip install
--user ...` in each case, to install inside your home directory
without root privileges.  (Anaconda does this by default anyway.)


## Usage

First, we show a very simple example of usage with Euler angles,
though it breaks my heart to do
so:<sup>[1](#euler-angles-are-awful)</sup>

```python
>>> import spherical_functions as sp
>>> alpha, beta, gamma = 0.1, 0.2, 0.3
>>> ell,mp,m = 3,2,1
>>> sp.wignerD(alpha, beta, gamma, ell, mp, m)

```

Of course, it's always better to use unit quaternions to describe
rotations:

```python
>>> import numpy as np
>>> import quaternion
>>> R = np.quaternion(1,2,3,4).normalized()
>>> ell,mp,m = 3,2,1
>>> sp.wignerD(R, ell, mp, m)

```

If you need to calculate values of the 𝔇<sup>(ℓ)</sup> matrix elements
for many values of (ℓ, m', m), it is more efficient to do so all at
once.  The following calculates all modes for ℓ from 2 to 8
(inclusive):

```python
>>> indices = np.array([[ell,mp,m] for ell in range(2,9)
... for mp in range(-ell, ell+1) for m in range(-ell, ell+1)])
>>> sp.wignerD(R, indices)

```

Finally, if you really need to put the pedal to the metal, and are
willing to guarantee that the input arguments are correct, you can use
a special hidden form of the function:

```python
>>> sp._wignerD(R.a, R.b, indices, elements)

```

Here, `R.a` and `R.b` are the two complex parts of the quaternion
defined on [this page](http://moble.github.io/spherical_functions/)
(though the user need not care about that).  The `indices` variable is
assumed to be a two-dimensional array of integers, where the second
dimension has size three, representing the (ℓ, m', m) indices.  This
avoids certain somewhat slower pure-python operations involving
argument checking, reshaping, etc.  The `elements` variable must be a
one-dimensional array of complex numbers (can be uninitialized), which
will be replaced with the corresponding values on return.  Again,
however, there is no input dimension checking here, so if you give bad
inputs, behavior could range from silently wrong to exceptions to
segmentation faults.  Caveat emptor.


## Acknowledgments

I very much appreciate Barry Wardell's help in sorting out the
relationships between my conventions and those of other people and
software packages (especially Mathematica's crazy conventions).

This work was supported in part by the Sherman Fairchild Foundation
and by NSF Grants No. PHY-1306125 and AST-1333129.


<br/><br/>
###### <sup>1</sup> Euler angles are awful

Euler angles are pretty much
[the worst things ever](http://moble.github.io/spherical_functions/#1-euler-angles)
and it makes me feel bad even supporting them.  Quaternions are
faster, more accurate, basically free of singularities, more
intuitive, and generally easier to understand.  You can work entirely
without Euler angles (I certainly do).  You absolutely never need
them.  But if you're so old fashioned that you really can't give them
up, they are fully supported.