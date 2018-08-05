#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  4 10:52:17 2018

@author: tommy
"""
import pytest
from scipy.spatial import cKDTree
import numbers
import numpy as np
import time
from KDEpy.BaseKDE import BaseKDE

   
class TreeKDE(BaseKDE):
    """
    This class implements a tree-based computation of a kernel density 
    estimate. It works by segmenting the space recursively into smaller parts. 
    This makes computing a kernel density estimate at a location easier, since 
    we are able to query the tree structure for nearby points instead of having 
    to evaluate the kernel function on all data points. For kernels without 
    finite support, their support is approximated.
    
    Parameters
    ----------
    kernel : str
        The kernel function. See cls._available_kernels.keys() for choices.
    bw : float, str or array-like
        Bandwidth or bandwidth selection method. If a float is passed, it
        is the standard deviation of the kernel. If a string it passed, it
        is the bandwidth selection method, see cls._bw_methods.keys() for
        choices. If an array-like it passed, it is the bandwidth of each
        point.
    norm : float
        The p-norm used to compute the distances in higher dimensions.
        
    Examples
    --------
    >>> data = np.random.randn(2**10)
    >>> # Automatic bw selection using Improved Sheather Jones
    >>> x, y = TreeKDE(bw='ISJ').fit(data).evaluate()
    >>> # Explicit choice of kernel and bw (standard deviation of kernel)
    >>> x, y = TreeKDE(kernel='triweight', bw=0.5).fit(data).evaluate()
    >>> weights = data + 10
    >>> # Using a grid and weights for the data
    >>> y = TreeKDE(kernel='epa', bw=0.5).fit(data, weights).evaluate(x)
    
    References
    ----------
    - Friedman, Jerome H., Jon Louis Bentley, and Raphael Ari Finkel. 
      An Algorithm for Finding Best Matches in Logarithmic Expected Time.
      ACM Trans. Math. Softw. 3, no. 3 (September 1977): 209–226. 
      https://doi.org/10.1145/355744.355745.
    - Maneewongvatana, Songrit, and David M. Mount. 
      It’s Okay to Be Skinny, If Your Friends Are Fat.
      In Center for Geometric Computing 4th Annual Workshop on Computational 
      Geometry, 2:1–8, 1999.
    - Silverman, B. W. Density Estimation for Statistics and Data Analysis. 
      Boca Raton: Chapman and Hall, 1986. Page 99 for reference to kd-tree.
    - Scipy implementation, at ``scipy.spatial.KDTree``.
    """
    
    def __init__(self, kernel='gaussian', bw=1, norm=2.):
        super().__init__(kernel, bw)
        self.norm = norm
    
    def fit(self, data, weights=None):
        """
        Fit the KDE to the data. This validates the data and stores it. 
        Computations are performed upon evaluation on a grid.
    
        Parameters
        ----------
        data: array-like
            The data points.
        weights: array-like
            One weight per data point. Must have same shape as the data.
            
        Returns
        -------
        self
            Returns the instance.
            
        Examples
        --------
        >>> data = [1, 3, 4, 7]
        >>> weights = [3, 4, 2, 1]
        >>> kde = TreeKDE().fit(data, weights=None)
        >>> kde = TreeKDE().fit(data, weights=weights)
        >>> x, y = kde()
        """
        # Sets self.data
        super().fit(data)
        
        # If weights were passed
        if weights is not None:
            if not len(weights) == len(data):
                raise ValueError('Length of data and weights must match.')
            else:
                weights = self._process_sequence(weights)
                self.weights = np.asfarray(weights)
        else:
            self.weights = np.ones_like(self.data)
            
        self.weights = self.weights / np.sum(self.weights)
            
        return self
    
    def evaluate(self, grid_points=None, eps=10e-4):
        """
        Evaluate on the grid points.
        
        Parameters
        ----------
        grid_points: array-like or None
            A 1D grid (mesh) to evaluate on. If None, a grid will be 
            automatically created.
        eps: float
            The maximal total error in absolute terms when estimating the 
            effective support of a kernel which has infinite support. Setting
            this too high will produced a jagged estimate.
            
        Returns
        -------
        y: array-like
            If a grid is supplied, `y` is returned. If no grid is supplied,
            a tuple (`x`, `y`) is returned.
            
        Examples
        --------
        >>> kde = TreeKDE().fit([1, 3, 4, 7])
        >>> # Two ways to evaluate, either with a grid or without
        >>> x, y = kde.evaluate()
        >>> # kde.evaluate() is equivalent to kde()
        >>> y = kde(grid_points=np.linspace(0, 10, num=2**10))
        """
        
        # This method sets self.grid points and verifies it
        super().evaluate(grid_points)
        
        # Return the array converted to a float type
        grid_points = np.asfarray(self.grid_points)
        
        # Create zeros on the grid points
        evaluated = np.zeros_like(grid_points)
        
        # For every data point, compute the kernel and add to the grid
        bw = self.bw
        if isinstance(bw, numbers.Number):
            bw = np.asfarray(np.ones_like(self.data) * bw)
        elif callable(bw):
            bw = np.asfarray(np.ones_like(self.data) * bw(self.data))
        else:
            bw = self._process_sequence(bw)
        maximal_bw = np.max(self.bw)

        # Initialize the tree structure for fast lookups of neighbors
        tree = cKDTree(self.data)
        
        # Compute the kernel radius
        maximal_bw = np.max(bw)
        if not eps > 0:
            raise ValueError('eps must be > 0.')
        kernel_radius = self.kernel.practical_support(maximal_bw, eps)
            
        # Since we iterate through grid points, we need the maximum bw to
        # ensure that we get data points that are close enough
        obs, dims = self.data.shape
        for i, grid_point in enumerate(grid_points):

            # Query for data points that are close to this grid point
            indices = tree.query_ball_point(x=grid_point, 
                                            r=kernel_radius,  # * maximal_bw, 
                                            p=self.norm, 
                                            # TODO: Is this epsilon value ok?
                                            eps=eps * np.sqrt(obs))

            # Use broadcasting to find x-values (distances)
            x_values = grid_point - self.data[indices]
            kernel_estimates = self.kernel(x_values, bw=bw[indices])
            weights_subset = self.weights[indices]
            
            assert kernel_estimates.shape == weights_subset.shape
            assert kernel_estimates.shape == bw[indices].shape

            # Unpack the (n, 1) arrays to (n,) and compute the doc product
            evaluated[i] += np.dot(kernel_estimates.ravel(), 
                                   weights_subset.ravel())
            
        return self._evalate_return_logic(evaluated, grid_points)


if __name__ == "__main__":
    # --durations=10  <- May be used to show potentially slow tests
    pytest.main(args=['.', '--doctest-modules', '-v'])
    pass

if __name__ == '__main__':
    
    import matplotlib.pyplot as plt
    from KDEpy.NaiveKDE import NaiveKDE
    
    # Comparing tree and naive
    # -----------------------------------------
    data = [3, 3.5, 4, 6, 8]
    kernel = 'triweight'
    bw = [3, 0.3, 1, 0.3, 2]
    weights = [1, 1, 1, 1, 1]
    
    plt.figure(figsize=(10, 4))
    plt.title('Basic example of the naive KDE')
    
    plt.subplot(1, 2, 1)
    kde = NaiveKDE(kernel=kernel, bw=bw)
    kde.fit(data, weights)
    x = np.linspace(0, 10, num=1024)
    for d, b in zip(data, bw):
        k = NaiveKDE(kernel=kernel, bw=b).fit([d]).evaluate(x) / len(data)
        plt.plot(x, k, color='k', ls='--')
        
    y = kde.evaluate(x)
    plt.plot(x, y)
    plt.scatter(data, np.zeros_like(data))
    
    plt.subplot(1, 2, 2)
    kde = TreeKDE(kernel=kernel, bw=bw)
    kde.fit(data, weights)
    x = np.linspace(0, 10, num=1024)
    for d, b in zip(data, bw):
        k = NaiveKDE(kernel=kernel, bw=b).fit([d]).evaluate(x) / len(data)
        plt.plot(x, k, color='k', ls='--')
        
    y = kde.evaluate(x)
    plt.plot(x, y)
    plt.scatter(data, np.zeros_like(data))
    plt.show()

    # Comparing tree and naive
    # -----------------------------------------
    data = [3, 3.5, 4, 6, 8]
    data = np.array(data)
    data = list(np.random.random(5))
    kernel = 'triweight'
    bw = [3, 0.3, 1, 0.3, 2]
    weights = [1, 2, 3, 4, 5]
    np.random.seed(123)
    n = 120
    data = np.random.gamma(5, scale=2.5, size=n) * 10
    bw = np.random.random(n) + 5 + 1
    weights = np.random.random(n) / 1 + 1
    
    plt.figure(figsize=(10, 4))
    plt.title('Basic example of the naive KDE')
    
    plt.subplot(1, 2, 1)
    kde = NaiveKDE(kernel=kernel, bw=bw)
    kde.fit(data, weights)
    x = np.linspace(-4, 360, num=1024)
    for d, b in zip(data, bw):
        break
        k = NaiveKDE(kernel=kernel, bw=b).fit([d]).evaluate(x) / len(data)
        plt.plot(x, k, color='k', ls='--')
        
    st = time.perf_counter()
    y = kde.evaluate(x)
    print(time.perf_counter() - st)
    plt.plot(x, y)
    plt.scatter(data, np.zeros_like(data))
    
    plt.subplot(1, 2, 2)
    kde = TreeKDE(kernel=kernel, bw=bw)
    kde.fit(data, weights)
    x = np.linspace(-4, 360, num=1024)
    for d, b in zip(data, bw):
        break
        k = NaiveKDE(kernel=kernel, bw=b).fit([d]).evaluate(x) / len(data)
        plt.plot(x, k, color='k', ls='--')
        
    st = time.perf_counter()
    y = kde.evaluate(x)
    print(time.perf_counter() - st)
    plt.plot(x, y)
    plt.scatter(data, np.zeros_like(data))

    plt.show()
    
    # Comparing tree and naive
    # -----------------------------------------
    kernel = 'gaussian'
    data = np.sqrt(np.arange(5) + 1)
    # data = np.ones(100)
    bw = np.ones_like(data)
    weights = None
    eps = 0.0001

    plt.figure(figsize=(10, 4))
    plt.title('Basic example of the naive KDE')
    
    plt.subplot(1, 2, 1)
    kde = NaiveKDE(kernel=kernel, bw=bw)
    kde.fit(data, weights)
    x = np.linspace(-4, 4, num=1024)
    for d, b in zip(data, bw):
        break
        k = NaiveKDE(kernel=kernel, bw=b).fit([d]).evaluate(x) / len(data)
        plt.plot(x, k, color='k', ls='--')
        
    st = time.perf_counter()
    x, y = kde.evaluate()
    print(time.perf_counter() - st)
    plt.plot(x, y)
    plt.scatter(data, np.zeros_like(data))
    
    plt.subplot(1, 2, 2)
    kde = TreeKDE(kernel=kernel, bw=bw)
    kde.fit(data, weights)
    x = np.linspace(-4, 4, num=1024)
    for d, b in zip(data, bw):
        break
        k = (NaiveKDE(kernel=kernel, bw=b).fit([d])
             .evaluate(x, eps=eps) / len(data))
        plt.plot(x, k, color='k', ls='--')
        
    st = time.perf_counter()
    x, y = kde.evaluate(eps=eps)
    print(time.perf_counter() - st)
    plt.plot(x, y)
    plt.plot([min(data) - 1, max(data) + 1], [eps, eps])
    plt.scatter(data, np.zeros_like(data))

    plt.show()
    
    
