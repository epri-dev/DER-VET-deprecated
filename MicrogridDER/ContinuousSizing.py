"""
Continuous Sizing Module

"""

__author__ = 'Andrew Etringer and Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani', 'Micah Botkin-Levy', 'Yekta Yazar']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Evan Giarta', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'egiarta@epri.com', 'mevans@epri.com']
__version__ = 'beta'

from ErrorHandelling import *


class ContinuousSizing:
    """ This class is to be inherited by DER classes that want to also define the ability
    to optimally size itself by kW of energy capacity

    """

    def __init__(self, params):
        TellUser.debug(f"Initializing {__name__}")
        self.size_constraints = []

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
        constraint_list = self.size_constraints

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

    def sizing_summary(self):
        """

        Returns: A dictionary describe this DER's size and capital costs.

        """
        # template = pd.DataFrame(columns=)
        # sizing_dict = {
        #     'DER': np.nan,
        #     'Energy Rating (kWh)': np.nan,
        #     'Charge Rating (kW)': np.nan,
        #     'Discharge Rating (kW)': np.nan,
        #     'Round Trip Efficiency (%)': np.nan,
        #     'Lower Limit on SOC (%)': np.nan,
        #     'Upper Limit on SOC (%)': np.nan,
        #     'Duration (hours)': np.nan,
        #     'Capital Cost ($)': np.nan,
        #     'Capital Cost ($/kW)': np.nan,
        #     'Capital Cost ($/kWh)': np.nan,
        #     'Power Capacity (kW)': np.nan,
        #     'Quantity': 1,
        # }
        # return sizing_dict

    def sizing_error(self):
        """

        Returns: True if there is an input error

        """
        return False

    def max_p_schedule_down(self):
        return 0

    def max_p_schedule_up(self):
        return self.max_p_schedule_down()

    def is_discharge_sizing(self):
        return self.being_sized()

    def is_power_sizing(self):
        return self.being_sized()

    def max_power_defined(self):
        return True
