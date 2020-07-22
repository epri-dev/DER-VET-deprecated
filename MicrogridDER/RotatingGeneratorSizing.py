"""
ICE Sizing class

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
from MicrogridDER.DERExtension import DERExtension
from MicrogridDER.ContinuousSizing import ContinuousSizing
from storagevet.Technology.RotatingGenerator import RotatingGenerator


class RotatingGeneratorSizing(ContinuousSizing, DERExtension, RotatingGenerator):
    """ An rotating generator, with sizing optimization

    """

    def __init__(self, gen_type, params):
        """ Initialize all technology with the following attributes.

        Args:
            params (dict): Dict of parameters for initialization
        """
        RotatingGenerator.__init__(self, gen_type, params)
        DERExtension.__init__(self, params)
        ContinuousSizing.__init__(self, params)

    def constraints(self, mask):
        """ Builds the master constraint list for the subset of timeseries data being optimized.

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set

        Returns:
            A list of constraints that corresponds the generator's physical constraints and its service constraints
        """
        constraint_list = []
        # parent constraints
        parent_constraints = RotatingGenerator.constraints(self, mask)
        # only keep the first constraint from the parent class when sizing
        constraint_list += [parent_constraints[0]]
        if not self.being_sized():
            constraint_list += [parent_constraints[1]]
        # sizing constraints
        constraint_list += ContinuousSizing.constraints(self, mask)

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
        costs = RotatingGenerator.objective_function(self, mask, annuity_scalar)
        costs.update(ContinuousSizing.objective_function(self, mask, annuity_scalar))

        return costs

    def update_for_evaluation(self, input_dict):
        """ Updates price related attributes with those specified in the input_dictionary

        Args:
            input_dict: hold input data, keys are the same as when initialized

        """
        super().update_for_evaluation(input_dict)

        variable_cost = input_dict.get('variable_om_cost')
        if variable_cost is not None:
            self.variable_om = variable_cost

        fixed_om_cost = input_dict.get('fixed_om_cost')
        if variable_cost is not None:
            self.fixed_om = fixed_om_cost
