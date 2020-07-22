"""
Continuous Sizing Module

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


class ContinuousSizing:
    """ This class is to be inherited by DER classes
    that want to also define the ability
    to optimally size itself by kW of energy capacity,
    assuming a single unit (n=1)

    """

    def __init__(self, params):
        self.max_rated_power = params['max_rated_power']
        self.min_rated_power = params['min_rated_power']

        self.size_constraints = []
        if not self.rated_power:
            self.n = 1
            self.rated_power = cvx.Variable(integer=True, name='energy rating')
            self.size_constraints += [cvx.NonPos(-self.rated_power)]
            if self.min_rated_power:
                self.size_constraints += [cvx.NonPos(self.min_rated_power - self.rated_power)]
            if self.max_rated_power:
                self.size_constraints += [cvx.NonPos(self.rated_power - self.max_rated_power)]

    def being_sized(self):
        """ checks itself to see if this instance is being sized

        Returns: true if being sized, false if not being sized

        """
        return bool(len(self.size_constraints))

    def constraints(self, mask):
        """ Builds the master constraint list for the subset of timeseries data being optimized.

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set

        Returns:
            A list of constraints that corresponds the battery's physical constraints and its service constraints
        """
        elec = self.variables_dict['elec']
        on = self.variables_dict['on']
        constraint_list = []

        if self.being_sized():
            constraint_list += [cvx.NonPos(elec - cvx.multiply(self.rated_power, on))]

        constraint_list += self.size_constraints

        return constraint_list

    def objective_function(self, mask, annuity_scalar=1):
        # TODO rename this size_objective_function() to avoid confusion --AE
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

    def sizing_summary(self):
        """

        Returns: A dictionary describe this DER's size and capital costs.

        """
        # obtain the size of the battery, these may or may not be optimization variable
        # therefore we check to see if it is by trying to get its value attribute in a try-except statement.
        # If there is an error, then we know that it was user inputted and we just take that value instead.
        try:
            rated_power = self.rated_power.value
        except AttributeError:
            rated_power = self.rated_power

        sizing_results = {
            'DER': self.name,
            'Power Capacity (kW)': rated_power,
            'Capital Cost ($)': self.capital_cost_function[0],
            'Capital Cost ($/kW)': self.capital_cost_function[1]}

        return sizing_results
