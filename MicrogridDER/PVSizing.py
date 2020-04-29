"""
PVSizing.py

This Python class contains methods and attributes specific for technology analysis within StorageVet.
"""

__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'mevans@epri.com']
__version__ = 'beta'  # beta version

import cvxpy as cvx
from storagevet.Technology import PVSystem
from MicrogridDER.Sizing import Sizing


class PVSizing(PVSystem.PV, Sizing):
    """ Assumes perfect foresight. Ability to curtail PV generation

    """

    def __init__(self, params):
        """ Initializes a PV class where perfect foresight of generation is assumed.
        It inherits from the technology class. Additionally, it sets the type and physical constraints of the
        technology.

        Args:
            params (dict): Dict of parameters
        """
        # create generic technology object
        PVSystem.PV.__init__(self, params)
        Sizing.__init__(self)

        if not self.rated_capacity:
            self.rated_capacity = cvx.Variable(name='PV rating', integer=True)
            self.size_constraints += [cvx.NonPos(-self.rated_capacity)]

    def constraints(self, mask):
        """ Builds the master constraint list for the subset of timeseries data being optimized.

        Returns:
            A list of constraints that corresponds the battery's physical constraints and its service constraints
        """
        constraints = super().constraints(mask)
        constraints += self.size_constraints
        return constraints

    def objective_function(self, mask, annuity_scalar=1):
        """ Generates the objective function related to a technology. Default includes O&M which can be 0

        Args:
            mask (Series): Series of booleans used, the same length as case.power_kw
            annuity_scalar (float): a scalar value to be multiplied by any yearly cost or benefit that helps capture the cost/benefit over
                    the entire project lifetime (only to be set iff sizing, else alpha should not affect the aobject function)

        Returns:
            self.costs (Dict): Dict of objective costs
        """
        costs = dict()

        if self.being_sized():
            costs.update({self.name + 'capex': self.get_capex})

        return costs

    def sizing_summary(self):
        """

        Returns: A dictionary describe this DER's size and captial costs.

        """
        try:
            rated_capacity = self.rated_capacity.value
        except AttributeError:
            rated_capacity = self.rated_capacity

        sizing_results = {
            'DER': self.name,
            'Power Capacity (kW)': rated_capacity,
            'Capital Cost ($/kW)': self.capital_cost_function[0]}
        return sizing_results
