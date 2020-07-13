"""
BatteryTech.py

This Python class contains methods and attributes specific for technology analysis within StorageVet.
"""

__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'mevans@epri.com']
__version__ = 'beta'  # beta version

import logging
import cvxpy as cvx
from MicrogridDER.Sizing import Sizing
from storagevet.Technology import BatteryTech
from MicrogridDER.DERExtension import DERExtension
from ErrorHandelling import *

DEBUG = False


class Battery(BatteryTech.Battery, Sizing, DERExtension):
    """ Battery class that inherits from Storage.

    """

    def __init__(self, params):
        """ Initializes a battery class that inherits from the technology class.
        It sets the type and physical constraints of the technology.

        Args:
            params (dict): params dictionary from dataframe for one case
        """

        # create generic storage object
        BatteryTech.Battery.__init__(self, params)
        DERExtension.__init__(self, params)
        Sizing.__init__(self)

        self.user_duration = params['duration_max']
        self.user_ch_rated_max = params['user_ch_rated_max']
        self.user_ch_rated_min = params['user_ch_rated_min']
        self.user_dis_rated_max = params['user_dis_rated_max']
        self.user_dis_rated_min = params['user_dis_rated_min']
        self.user_ene_rated_max = params['user_ene_rated_max']
        self.user_ene_rated_min = params['user_ene_rated_min']

        # TODO: move these user-defined optimization constraints to objective constraints method of BatterySizing
        #  instead of setting up them in the class initialization
        # if the user inputted the energy rating as 0, then size for energy rating
        if not self.ene_max_rated:
            self.ene_max_rated = cvx.Variable(name='Energy_cap', integer=True)
            self.size_constraints += [cvx.NonPos(-self.ene_max_rated)]
            # recalculate the effective SOE limits s.t. they are CVXPY expressions
            self.effective_soe_min = self.llsoc * self.ene_max_rated
            self.effective_soe_max = self.ulsoc * self.ene_max_rated
            if self.incl_energy_limits and self.limit_energy_max is not None:
                e_logger.error(f'Ignoring energy max time series because {self.tag}-{self.name} sizing for energy capacity')
                self.limit_energy_max = None
            if self.user_ene_rated_min:
                self.size_constraints += [cvx.NonPos(self.user_ene_rated_min - self.ene_max_rated)]
            if self.user_ene_rated_max:
                self.size_constraints += [cvx.NonPos(self.ene_max_rated - self.user_ene_rated_max)]

        # if both the discharge and charge ratings are 0, then size for both and set them equal to each other
        if not self.ch_max_rated and not self.dis_max_rated:
            self.ch_max_rated = cvx.Variable(name='power_cap', integer=True)
            self.size_constraints += [cvx.NonPos(-self.ch_max_rated)]
            if self.user_ch_rated_max:
                self.size_constraints += [cvx.NonPos(self.ch_max_rated - self.user_ch_rated_max)]
            if self.user_ch_rated_min:
                self.size_constraints += [cvx.NonPos(self.user_ch_rated_min - self.ch_min_rated)]
            self.dis_max_rated = self.ch_max_rated
            if self.user_dis_rated_min:
                self.size_constraints += [cvx.NonPos(self.user_dis_rated_min - self.dis_min_rated)]
            if self.user_dis_rated_max:
                self.size_constraints += [cvx.NonPos(self.dis_max_rated - self.user_dis_rated_max)]
            if self.incl_charge_limits and self.limit_charge_max is not None:
                e_logger.error(f'Ignoring charge max time series because {self.tag}-{self.name} sizing for power capacity')
                self.limit_charge_max = None
            if self.incl_discharge_limits and self.limit_discharge_max is not None:
                e_logger.error(f'Ignoring discharge max time series because {self.tag}-{self.name} sizing for power capacity')
                self.limit_discharge_max = None

        elif not self.ch_max_rated:  # if the user inputted the discharge rating as 0, then size discharge rating
            self.ch_max_rated = cvx.Variable(name='charge_power_cap', integer=True)
            self.size_constraints += [cvx.NonPos(-self.ch_max_rated)]
            if self.incl_charge_limits and self.limit_charge_max is not None:
                e_logger.error(f'Ignoring charge max time series because {self.tag}-{self.name} sizing for power capacity')
                self.limit_charge_max = None
            if self.user_ch_rated_max:
                self.size_constraints += [cvx.NonPos(self.ch_max_rated-self.user_ch_rated_max)]
            if self.user_ch_rated_min:
                self.size_constraints += [cvx.NonPos(self.user_ch_rated_min-self.ch_min_rated)]

        elif not self.dis_max_rated:  # if the user inputted the charge rating as 0, then size for charge
            self.dis_max_rated = cvx.Variable(name='discharge_power_cap', integer=True)
            self.size_constraints += [cvx.NonPos(-self.dis_max_rated)]
            if self.incl_discharge_limits and self.limit_discharge_max is not None:
                e_logger.error(f'Ignoring discharge max time series because {self.tag}-{self.name} sizing for power capacity')
                self.limit_discharge_max = None
            if self.user_dis_rated_min:
                self.size_constraints += [cvx.NonPos(self.user_dis_rated_min - self.dis_min_rated)]
            if self.user_dis_rated_max:
                self.size_constraints += [cvx.NonPos(self.dis_max_rated - self.user_dis_rated_max)]

        if self.user_duration:
            self.size_constraints += [cvx.NonPos((self.ene_max_rated / self.dis_max_rated) - self.user_duration)]

    def discharge_capacity(self, solution=False):
        """

        Returns: the maximum discharge that can be attained

        """
        if not solution:
            return self.dis_max_rated
        else:
            try:
                dis_max_rated = self.dis_max_rated.value
            except AttributeError:
                dis_max_rated = self.dis_max_rated
            return dis_max_rated

    def charge_capacity(self, solution=False):
        """

        Returns: the maximum charge that can be attained

        """
        if not solution:
            return self.dis_max_rated
        else:
            try:
                ch_max_rated = self.ch_max_rated.value
            except AttributeError:
                ch_max_rated = self.ch_max_rated
            return ch_max_rated

    def energy_capacity(self, solution=False):
        """

        Returns: the maximum energy that can be attained

        """
        if not solution:
            return self.ene_max_rated
        else:
            try:
                max_rated = self.ene_max_rated.value
            except AttributeError:
                max_rated = self.ene_max_rated
            return max_rated

    def operational_max_energy(self, solution=False):
        """

        Returns: the maximum energy that should stored in this DER based on user inputs

        """
        if not solution:
            return self.effective_soe_max
        else:
            try:
                effective_soe_max = self.effective_soe_max.value
            except AttributeError:
                effective_soe_max = self.effective_soe_max
            return effective_soe_max

    def operational_min_energy(self, solution=False):
        """

        Returns: the minimum energy that should stored in this DER based on user inputs
        """
        if not solution:
            return self.effective_soe_min
        else:
            try:
                effective_soe_min = self.effective_soe_min.value
            except AttributeError:
                effective_soe_min = self.effective_soe_min
            return effective_soe_min

    def constraints(self, mask):
        """ Builds the master constraint list for the subset of timeseries data being optimized.

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set

        Returns:
            A list of constraints that corresponds the battery's physical constraints and its service constraints
        """

        constraint_list = super().constraints(mask)

        constraint_list += self.size_constraints

        return constraint_list

    def objective_function(self, mask, annuity_scalar=1):
        """ Generates the objective function related to a technology. Default includes O&M which can be 0

        Args:
            mask (Series): Series of booleans used, the same length as case.power_kw
            annuity_scalar (float): a scalar value to be multiplied by any yearly cost or benefit that helps capture the cost/benefit over
                    the entire project lifetime (only to be set iff sizing, else alpha should not affect the aobject function)

        Returns:
            self.costs (Dict): Dict of objective costs
        """
        costs = super().objective_function(mask, annuity_scalar)

        costs.update({self.name + 'capex': self.get_capex()})
        return costs

    def sizing_summary(self):
        """

        Returns: A dataframe indexed by the terms that describe this DER's size and captial costs.

        """
        sizing_results = {
            'DER': self.name,
            'Energy Rating (kWh)': self.energy_capacity(solution=True),
            'Charge Rating (kW)': self.charge_capacity(solution=True),
            'Discharge Rating (kW)': self.discharge_capacity(solution=True),
            'Round Trip Efficiency (%)': self.rte,
            'Lower Limit on SOC (%)': self.llsoc,
            'Upper Limit on SOC (%)': self.ulsoc,
            'Duration (hours)': self.calculate_duration(),
            'Capital Cost ($)': self.capital_cost_function[0],
            'Capital Cost ($/kW)': self.capital_cost_function[1],
            'Capital Cost ($/kWh)': self.capital_cost_function[2]}
        if sizing_results['Duration (hours)'] > 24:
            LogError.warning(f'The duration of {self.name} is greater than 24 hours!')

        # warn about tight sizing margins
        # TODO clean up these warnings into a single method --AE
        if isinstance(self.ene_max_rated, cvx.Variable):
            energy_cap = self.energy_capacity(True)
            sizing_margin1 = (abs(energy_cap - self.user_ene_rated_max) - 0.05 * self.user_ene_rated_max)
            sizing_margin2 = (abs(energy_cap - self.user_ene_rated_min) - 0.05 * self.user_ene_rated_min)
            if (sizing_margin1 < 0).any() or (sizing_margin2 < 0).any():
                LogError.warning("Difference between the optimal Battery ene max rated and user upper/lower "
                                 "bound constraints is less than 5% of the value of user upper/lower bound constraints")
        if isinstance(self.ch_max_rated, cvx.Variable):
            charge_cap = self.charge_capacity(True)
            sizing_margin1 = (abs(charge_cap - self.user_ch_rated_max) - 0.05 * self.user_ch_rated_max)
            sizing_margin2 = (abs(charge_cap - self.user_ch_rated_min) - 0.05 * self.user_ch_rated_min)
            if (sizing_margin1 < 0).any() or (sizing_margin2 < 0).any():
                LogError.warning("Difference between the optimal Battery ch max rated and user upper/lower "
                                 "bound constraints is less than 5% of the value of user upper/lower bound constraints")
        if isinstance(self.dis_max_rated, cvx.Variable):
            discharge_cap = self.discharge_capacity(True)
            sizing_margin1 = (abs(discharge_cap - self.user_dis_rated_max) - 0.05 * self.user_dis_rated_max)
            sizing_margin2 = (abs(discharge_cap - self.user_dis_rated_min) - 0.05 * self.user_dis_rated_min)
            if (sizing_margin1 < 0).any() or (sizing_margin2 < 0).any():
                LogError.warning("Difference between the optimal Battery dis max rated and user upper/lower "
                                 "bound constraints is less than 5% of the value of user upper/lower bound constraints")

        return sizing_results

    def calculate_duration(self):
        """ Determines the duration of the storage (after solving for the size)

        Returns:
        """
        try:
            energy_rated = self.ene_max_rated.value
        except AttributeError:
            energy_rated = self.ene_max_rated

        return energy_rated / self.discharge_capacity(solution=True)

    def update_for_evaluation(self, input_dict):
        """ Updates price related attributes with those specified in the input_dictionary

        Args:
            input_dict: hold input data, keys are the same as when initialized

        """
        super().update_for_evaluation(input_dict)
        fixed_om = input_dict.get('fixedOM')
        if fixed_om is not None:
            self.fixedOM_perKW = fixed_om

        variable_om = input_dict.get('OMexpenses')
        if variable_om is not None:
            self.variable_om = variable_om*100

        if self.incl_startup:
            p_start_ch = input_dict.get('p_start_ch')
            if p_start_ch is not None:
                self.p_start_ch = p_start_ch * 100

            p_start_dis = input_dict.get('p_start_dis')
            if p_start_dis is not None:
                self.p_start_dis = p_start_dis * 100

    def sizing_error(self):
        """

        Returns: True if there is an input error

        """
        if not self.ch_max_rated:
            if self.user_ch_rated_min > self.user_ch_rated_max:
                LogError.error('User battery min charge power requirement is greater than max charge power requirement.')
                return False
        if not self.dis_max_rated:
            if self.user_dis_rated_min > self.user_dis_rated_max:
                LogError.error('User battery min discharge power requirement is greater than max discharge power requirement.')
                return False
        if not self.ene_max_rated:
            if self.user_ene_rated_min > self.user_ene_rated_max:
                LogError.error('User battery min energy requirement is greater than max energy requirement.')
                return False
        return True
