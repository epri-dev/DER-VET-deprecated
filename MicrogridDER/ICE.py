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
from storagevet.Technology import InternalCombustionEngine
from MicrogridDER.Sizing import Sizing
from MicrogridDER.DERExtension import DERExtension


class ICE(InternalCombustionEngine.ICE, Sizing, DERExtension):
    """ An ICE generator

    """

    def __init__(self, params):
        """ Initialize all technology with the following attributes.

        Args:
            params (dict): Dict of parameters for initialization
        """
        Sizing.__init__(self)
        DERExtension.__init__(self, params)
        self.n_min = params['n_min']  # generators
        self.n_max = params['n_max']  # generators
        if self.being_sized():
            params['n'] = cvx.Variable(integer=True, name='generators')
        else:
            params['n'] = self.n_max
        # create generic technology object
        InternalCombustionEngine.ICE.__init__(self, params)

    def constraints(self, mask):
        """ Builds the master constraint list for the subset of timeseries data being optimized.

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set

        Returns:
            A list of constraints that corresponds the battery's physical constraints and its service constraints
        """
        ice_gen = self.variables_dict['ice_gen']
        on_ice = self.variables_dict['on_ice']
        constraint_list = super().constraints(mask)

        if self.being_sized():
            # take only the first constraint from parent class - second will cause a DCP error, so we add other constraints here to
            # cover that constraint
            constraint_list = [constraint_list[0]]

            constraint_list += [cvx.NonPos(ice_gen - cvx.multiply(self.rated_power * self.n_max, on_ice))]
            constraint_list += [cvx.NonPos(ice_gen - self.n * self.rated_power)]

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
        costs = super().objective_function(mask, annuity_scalar)
        if self.being_sized():
            costs[self.name + '_ccost'] = self.get_capex()

        return costs

    def sizing_summary(self):
        """

        Returns: A dictionary describe this DER's size and captial costs.

        """
        # obtain the size of the battery, these may or may not be optimization variable
        # therefore we check to see if it is by trying to get its value attribute in a try-except statement.
        # If there is an error, then we know that it was user inputted and we just take that value instead.
        try:
            n = self.n.value
        except AttributeError:
            n = self.n

        sizing_results = {
            'DER': self.name,
            'Power Capacity (kW)': self.rated_power,
            'Capital Cost ($)': self.capital_cost_function[0],
            'Capital Cost ($/kW)': self.capital_cost_function[1],
            'Quantity': n}
        return sizing_results

    def max_power_out(self):
        """

        Returns: the maximum power that can be outputted by this genset

        """
        try:
            power_out = self.n.value * self.rated_power
        except AttributeError:
            power_out = self.n * self.rated_power
        return power_out

    def being_sized(self):
        """ checks itself to see if this instance is being sized

        Returns: true if being sized, false if not being sized

        """
        return self.n_min != self.n_max

    def update_for_evaluation(self, input_dict):
        """ Updates price related attributes with those specified in the input_dictionary

        Args:
            input_dict: hold input data, keys are the same as when initialized

        """
        super().update_for_evaluation(input_dict)
        # ccost = input_dict.get('ccost')
        # if ccost is not None:
        #     self.capital_cost_function[0] = ccost
        #
        ccost_kw = input_dict.get('ccost_kW')
        if ccost_kw is not None:
            self.capital_cost_function[1] = ccost_kw

        fuel_cost = input_dict.get('fuel_cost')
        if fuel_cost is not None:
            self.fuel_cost = fuel_cost

        variable_cost = input_dict.get('variable_om_cost')
        if variable_cost is not None:
            self.variable_om = variable_cost

        fixed_om_cost = input_dict.get('fixed_om_cost')
        if variable_cost is not None:
            self.fixed_om = fixed_om_cost
