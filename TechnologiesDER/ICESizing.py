"""
Diesel

This Python class contains methods and attributes specific for technology analysis within StorageVet.
"""

__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani', 'Micah Botkin-Levy', 'Yekta Yazar']
__license__ = 'EPRI'
__maintainer__ = ['Evan Giarta', 'Miles Evans']
__email__ = ['egiarta@epri.com', 'mevans@epri.com']

import cvxpy as cvx
import pandas as pd
import storagevet


class ICESizing(storagevet.ICE):
    """ An ICE generator

    """

    def __init__(self, name, params):
        """ Initialize all technology with the following attributes.

        Args:
            name (str): A unique string name for the technology being added, also works as category.
            params (dict): Dict of parameters for initialization
        """
        # create generic technology object
        storagevet.ICE.__init__(self, name, params)
        self.n_min = params['n_min']  # generators
        self.n_max = params['n_max']  # generators
        self.n = cvx.Variable(integer=True, name='generators')
        self.capex = self.capital_cost * self.n + self.capital_cost * self.rated_power

    def objective_constraints(self, variables, mask, reservations, mpc_ene=None):
        """ Builds the master constraint list for the subset of timeseries data being optimized.

        Args:
            variables (Dict): Dictionary of variables being optimized
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set
            reservations (Dict): Dictionary of energy and power reservations required by the services being
                preformed with the current optimization subset
            mpc_ene (float): value of energy at end of last opt step (for mpc opt)

        Returns:
            A list of constraints that corresponds the battery's physical constraints and its service constraints
        """
        ice_gen = variables['ice_gen']
        on_ice = variables['on_ice']

        # take only the first constraint from parent class - second will cause a DCP error, so we add other constraints here to
        # cover that constraint
        constraint_list = [storagevet.ICE.objective_constraints(self, variables, mask, reservations, mpc_ene)[0]]

        constraint_list += [cvx.NonPos(ice_gen - cvx.multiply(self.rated_power * self.n_max, on_ice))]
        constraint_list += [cvx.NonPos(ice_gen - self.n * self.rated_power)]

        constraint_list += [cvx.NonPos(self.n_min - self.n)]
        constraint_list += [cvx.NonPos(self.n - self.n_max)]

        return constraint_list

    def sizing_summary(self):
        """

        Returns: A datafram indexed by the terms that describe this DER's size and captial costs.

        """
        # obtain the size of the battery, these may or may not be optimization variable
        # therefore we check to see if it is by trying to get its value attribute in a try-except statement.
        # If there is an error, then we know that it was user inputted and we just take that value instead.
        try:
            n = self.n.value
        except AttributeError:
            n = self.n

        index = pd.Index([self.name], name='DER')
        sizing_results = pd.DataFrame({'Power Capacity (kW)': self.rated_power,
                                       'Capital Cost ($)': self.capital_cost,
                                       'Capital Cost ($/kW)': self.ccost_kw,
                                       'Quantity': n}, index=index)
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
