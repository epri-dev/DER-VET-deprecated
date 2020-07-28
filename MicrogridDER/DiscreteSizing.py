"""
Discrete Sizing Module

"""

__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani', 'Micah Botkin-Levy', 'Yekta Yazar']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Evan Giarta', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'egiarta@epri.com', 'mevans@epri.com']
__version__ = 'beta'

import numpy as np
import cvxpy as cvx


class DiscreteSizing:
    """ This class is to be inherited by DER classes (Rotating Generators)
    that want to also define the ability
    to optimally size itself in discrete (integer) numbers of generators

    """

    def __init__(self, params):
        self.n_min = params['n_min']  # generators
        self.n_max = params['n_max']  # generators
        if self.being_sized():
            self.n = cvx.Variable(integer=True, name='generators')
        else:
            self.n = self.n_max

    def being_sized(self):
        """ checks itself to see if this instance is being sized

        Returns: true if being sized, false if not being sized

        """
        return self.n_min != self.n_max

    def constraints(self, mask):
        # TODO rename this size_constraint() to avoid confusion --AE
        """ Builds the master constraint list for the subset of timeseries data being optimized.

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set

        Returns:
            A list of constraints that corresponds the battery's physical constraints and its service constraints
        """
        constraint_list = []

        if self.being_sized():

            constraint_list += [cvx.NonPos(self.n_min - self.n)]
            constraint_list += [cvx.NonPos(self.n - self.n_max)]

        return constraint_list

    def objective_function(self, mask, annuity_scalar=1):
        """ Generates the objective function related to a technology. Default includes O&M which can be 0

        Args:
            mask (Series): Series of booleans used, the same length as case.power_kw
            annuity_scalar (float): a scalar value to be multiplied by any yearly cost or benefit that helps capture the cost/benefit over
                        the entire project lifetime (only to be set iff sizing)

        Returns:
            self.costs (Dict): Dict of objective costs
        """
        costs = {}
        if self.being_sized():
            costs[self.name + '_ccost'] = self.get_capex()

        return costs

