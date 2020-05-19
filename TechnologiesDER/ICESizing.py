"""
Diesel

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

        # Note: previous constraints from parent class ICE might lead to variable "start_gen" being unbounded for
        #  startup cost consideration when n is a sized variable
        # constraint_list = [storagevet.ICE.objective_constraints(self, variables, mask, reservations, mpc_ene)[0]]

        constraint_list = []
        constraint_list += [cvx.NonPos(cvx.multiply(self.p_min * self.n_min, on_ice) - ice_gen)]
        constraint_list += [cvx.NonPos(ice_gen - cvx.multiply(self.rated_power * self.n_max, on_ice))]

        # these 2 constraints below might be optional, but they are kept here to prevent the edge cases to produce
        # unwanted results
        constraint_list += [cvx.NonPos(self.n * self.p_min - ice_gen)]
        constraint_list += [cvx.NonPos(ice_gen - self.n * self.rated_power)]

        constraint_list += [cvx.NonPos(self.n_min - self.n)]
        constraint_list += [cvx.NonPos(self.n - self.n_max)]

        if self.incl_startup:
            start_gen = variables['start_gen']
            # startup variables are positive
            constraint_list += [cvx.NonPos(-start_gen)]

            self.min_started_generators = (ice_gen - self.p_min) / self.rated_power

            # difference between binary variables determine if started up in previous interval
            constraint_list += [cvx.NonPos((cvx.diff(self.min_started_generators)) - start_gen[1:])]
            # this takes care of the first time-step for start_gen
            constraint_list += [cvx.NonPos(self.min_started_generators[0] - start_gen[0])]

        return constraint_list

    def proforma_report(self, opt_years, results):
        """ Calculates the proforma that corresponds to participation in this value stream

        Args:
            opt_years (list): list of years the optimization problem ran for
            results (DataFrame): DataFrame with all the optimization variable solutions

        Returns: A DateFrame of with each year in opt_year as the index and
            the corresponding value this stream provided.

            Creates a dataframe with only the years that we have data for. Since we do not label the column,
            it defaults to number the columns with a RangeIndex (starting at 0) therefore, the following
            DataFrame has only one column, labeled by the int 0

        """
        # recacluate capex before reporting proforma
        self.capex = self.capital_cost * self.n + self.ccost_kw * self.rated_power * self.n
        proforma = super().proforma_report(opt_years, results)
        return proforma

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

    def being_sized(self):
        """ checks itself to see if this instance is being sized

        Returns: true if being sized, false if not being sized

        """
        return self.n_min == self.n_max
