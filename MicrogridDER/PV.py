"""
PV.py

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
from MicrogridDER.DERExtension import DERExtension
import pandas as pd


class PV(PVSystem.PV, Sizing, DERExtension):
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
        super(PV, self).__init__(params)

        self.curtail = params['curtail']
        if not self.curtail:
            # if we are not curatiling, remove
            self.variable_names = {}
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
        sr_max_capacity = self.variables_dict['sr_max_capacity']
        nsr_max_capacity = self.variables_dict['nsr_max_capacity']
        fr_max_regulation = self.variables_dict['fr_max_regulation']
        # add ramp rate constraints here --> SR, NSR, FR
        # TODO: for fr_max_regulation, make sure that you go back and do the up/down regulation part. Because FR is bidirectional --> Kunle
        # TODO: refer to Miles handout as well to make sure that your objective functions are in line w/ expectations --> Kunle
        constraints += [cvx.NonPos(sr_max_capacity - cvx.multiply(self.lag_time, self.sr_response_time) +
                                       cvx.multiply(self.sr_response_time, self.startup_time, self.sr_max_ramp_rate))]
        constraints += [cvx.NonPos(nsr_max_capacity - cvx.multiply(self.lag_time, self.nsr_response_time) +
                                       cvx.multiply(self.nsr_response_time, self.nsr_max_ramp_rate) +
                                       cvx.multiply(self.startup_time, self.nsr_max_ramp_rate))]
        constraints += [cvx.NonPos(fr_max_regulation - cvx.multiply(self.lag_time, self.fr_response_time) +
                                       cvx.multiply(self.fr_response_time, self.fr_max_ramp_rate) +
                                       cvx.multiply(self.startup_time, self.fr_max_ramp_rate))]

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
            'Capital Cost ($/kW)': self.capital_cost_function}
        return sizing_results

    def update_for_evaluation(self, input_dict):
        """ Updates price related attributes with those specified in the input_dictionary

        Args:
            input_dict: hold input data, keys are the same as when initialized

        """
        super(PV, self).update_for_evaluation(input_dict)
        cost_per_kw = input_dict.get('cost_per_kW')
        if cost_per_kw is not None:
            self.capital_cost_function = cost_per_kw

    def timeseries_report(self):
        """ Summaries the optimization results for this DER.

        Returns: A timeseries dataframe with user-friendly column headers that summarize the results
            pertaining to this instance

        """
        results = PVSystem.PV.timeseries_report(self)
        more_results = DERExtension.timeseries_report(self)
        results = pd.concat([results, more_results], axis=1)
        return results
