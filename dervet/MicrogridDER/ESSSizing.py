"""
Copyright (c) 2021, Electric Power Research Institute

 All rights reserved.

 Redistribution and use in source and binary forms, with or without modification,
 are permitted provided that the following conditions are met:

     * Redistributions of source code must retain the above copyright notice,
       this list of conditions and the following disclaimer.
     * Redistributions in binary form must reproduce the above copyright notice,
       this list of conditions and the following disclaimer in the documentation
       and/or other materials provided with the distribution.
     * Neither the name of DER-VET nor the names of its contributors
       may be used to endorse or promote products derived from this software
       without specific prior written permission.

 THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
 PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
 LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
 NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
 SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
"""
ESSSizing.py

This file defines the ability for ESSes to be sized by DERVET
"""

from dervet.MicrogridDER.ContinuousSizing import ContinuousSizing
from storagevet.Technology.EnergyStorage import EnergyStorage
from dervet.MicrogridDER.DERExtension import DERExtension
import cvxpy as cvx
from storagevet.ErrorHandling import *
import numpy as np


class ESSSizing(EnergyStorage, DERExtension, ContinuousSizing):
    """ Extended ESS class that can also be sized

    """

    def __init__(self, params):
        """ Initialize all technology with the following attributes.

        Args:
            params (dict): Dict of parameters
        """
        TellUser.debug(f"Initializing {__name__}")
        EnergyStorage.__init__(self, params)
        DERExtension.__init__(self, params)
        ContinuousSizing.__init__(self, params)
        self.incl_energy_limits = params.get('incl_ts_energy_limits', False)
        if self.incl_energy_limits:
            self.limit_energy_max = params['ts_energy_max'].fillna(self.ene_max_rated)
            self.limit_energy_min = params['ts_energy_min'].fillna(0)
        self.incl_charge_limits = params.get('incl_ts_charge_limits', False)
        if self.incl_charge_limits:
            self.limit_charge_max = params['ts_charge_max'].fillna(self.ch_max_rated)
            self.limit_charge_min = params['ts_charge_min'].fillna(self.ch_min_rated)
        self.incl_discharge_limits = params.get('incl_ts_discharge_limits', False)
        if self.incl_discharge_limits:
            self.limit_discharge_max = params['ts_discharge_max'].fillna(self.dis_max_rated)
            self.limit_discharge_min = params['ts_discharge_min'].fillna(self.dis_min_rated)
        if self.tag == 'CAES':
            # note that CAES sizing is not allowed bc it has not been validated -HN
            # TODO CAES + a warning if the user tries to size it
            return
        self.user_ch_rated_max = params['user_ch_rated_max']
        self.user_ch_rated_min = params['user_ch_rated_min']
        self.user_dis_rated_max = params['user_dis_rated_max']
        self.user_dis_rated_min = params['user_dis_rated_min']
        self.user_ene_rated_max = params['user_ene_rated_max']
        self.user_ene_rated_min = params['user_ene_rated_min']
        # if the user inputted the energy rating as 0, then size for energy rating
        if not self.ene_max_rated:
            self.ene_max_rated = cvx.Variable(name='Energy_cap', integer=True)
            self.size_constraints += [cvx.NonPos(-self.ene_max_rated)]
            # recalculate the effective SOE limits s.t. they are CVXPY expressions
            self.effective_soe_min = self.llsoc * self.ene_max_rated
            self.effective_soe_max = self.ulsoc * self.ene_max_rated
            if self.incl_energy_limits and self.limit_energy_max is not None:
                TellUser.error(f'Ignoring energy max time series because {self.tag}-{self.name} sizing for energy capacity')
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
                self.size_constraints += [cvx.NonPos(-self.ch_max_rated + self.user_ch_rated_min)]

            self.dis_max_rated = self.ch_max_rated

            if self.user_dis_rated_max:
                self.size_constraints += [cvx.NonPos(self.dis_max_rated - self.user_dis_rated_max)]
            if self.user_dis_rated_min:
                self.size_constraints += [cvx.NonPos(-self.dis_max_rated + self.user_dis_rated_min)]
            if self.incl_charge_limits and self.limit_charge_max is not None:
                TellUser.error(f'Ignoring charge max time series because {self.tag}-{self.name} sizing for power capacity')
                self.limit_charge_max = None
            if self.incl_discharge_limits and self.limit_discharge_max is not None:
                TellUser.error(f'Ignoring discharge max time series because {self.tag}-{self.name} sizing for power capacity')
                self.limit_discharge_max = None

        elif not self.ch_max_rated:  # if the user inputted the charge rating as 0, then size for charge
            self.ch_max_rated = cvx.Variable(name='charge_power_cap', integer=True)
            self.size_constraints += [cvx.NonPos(-self.ch_max_rated)]
            if self.user_ch_rated_max:
                self.size_constraints += [cvx.NonPos(self.ch_max_rated - self.user_ch_rated_max)]
            if self.user_ch_rated_min:
                self.size_constraints += [cvx.NonPos(-self.ch_max_rated + self.user_ch_rated_min)]
            if self.incl_charge_limits and self.limit_charge_max is not None:
                TellUser.error(f'Ignoring charge max time series because {self.tag}-{self.name} sizing for power capacity')
                self.limit_charge_max = None

        elif not self.dis_max_rated:  # if the user inputted the discharge rating as 0, then size discharge rating
            self.dis_max_rated = cvx.Variable(name='discharge_power_cap', integer=True)
            self.size_constraints += [cvx.NonPos(-self.dis_max_rated)]
            if self.user_dis_rated_max:
                self.size_constraints += [cvx.NonPos(self.dis_max_rated - self.user_dis_rated_max)]
            if self.user_dis_rated_min:
                self.size_constraints += [cvx.NonPos(-self.dis_max_rated + self.user_dis_rated_min)]
            if self.incl_discharge_limits and self.limit_discharge_max is not None:
                TellUser.error(f'Ignoring discharge max time series because {self.tag}-{self.name} sizing for power capacity')
                self.limit_discharge_max = None

    def discharge_capacity(self, solution=False):
        """

        Returns: the maximum discharge that can be attained

        """
        if not solution:
            return self.dis_max_rated
        else:
            try:
                dis_max_rated = int(self.dis_max_rated.value)
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
                ch_max_rated = int(self.ch_max_rated.value)
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
                max_rated = int(self.ene_max_rated.value)
            except AttributeError:
                max_rated = self.ene_max_rated
            return max_rated

    def operational_max_energy(self, solution=False):
        """

        Returns: the maximum energy that should stored in this DER based on user inputs

        """
        if not solution:
            return super(ESSSizing, self).operational_max_energy()
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
            return super(ESSSizing, self).operational_min_energy()
        else:
            try:
                effective_soe_min = self.effective_soe_min.value
            except AttributeError:
                effective_soe_min = self.effective_soe_min
            return effective_soe_min

    def get_capex(self, solution=False):
        capex = super().get_capex()
        if solution:
            try:
                capex = capex.value
            except AttributeError:
                capex = capex
        return capex

    def constraints(self, mask, **kwargs):
        """ Builds the master constraint list for the subset of timeseries data being optimized.

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set

        Returns:
            A list of constraints that corresponds the battery's physical constraints and its service constraints
        """

        constraint_list = super().constraints(mask,**kwargs)
        constraint_list += self.size_constraints
        if self.incl_energy_limits:
            # add timeseries energy limits on this instance
            ene = self.variables_dict['ene']
            if self.limit_energy_max is not None:
                energy_max = cvx.Parameter(value=self.limit_energy_max.loc[mask].values, shape=sum(mask), name='ts_energy_max')
                constraint_list += [cvx.NonPos(ene - energy_max)]
            if self.limit_energy_min is not None:
                energy_min = cvx.Parameter(value=self.limit_energy_min.loc[mask].values, shape=sum(mask), name='ts_energy_min')
                constraint_list += [cvx.NonPos(energy_min - ene)]
        if self.incl_charge_limits:
            # add timeseries energy limits on this instance
            charge = self.variables_dict['ch']
            if self.limit_charge_max is not None:
                charge_max = cvx.Parameter(value=self.limit_charge_max.loc[mask].values, shape=sum(mask), name='ts_charge_max')
                constraint_list += [cvx.NonPos(charge - charge_max)]
            if self.limit_charge_min is not None:
                charge_min = cvx.Parameter(value=self.limit_charge_min.loc[mask].values, shape=sum(mask), name='ts_charge_min')
                constraint_list += [cvx.NonPos(charge_min - charge)]
        if self.incl_discharge_limits:
            # add timeseries energy limits on this instance
            discharge = self.variables_dict['dis']
            if self.limit_discharge_max is not None:
                discharge_max = cvx.Parameter(value=self.limit_discharge_max.loc[mask].values, shape=sum(mask), name='ts_discharge_max')
                constraint_list += [cvx.NonPos(discharge - discharge_max)]
            if self.limit_discharge_min is not None:
                discharge_min = cvx.Parameter(value=self.limit_discharge_min.loc[mask].values, shape=sum(mask), name='ts_discharge_min')
                constraint_list += [cvx.NonPos(discharge_min - discharge)]
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
        costs.update(self.sizing_objective())
        return costs

    def set_size(self):
        """ Save value of size variables of DERs

        """
        self.dis_max_rated = self.discharge_capacity(solution=True)
        self.ch_max_rated = self.charge_capacity(solution=True)
        self.ene_max_rated = self.energy_capacity(solution=True)
        self.effective_soe_min = self.operational_min_energy(solution=True)
        self.effective_soe_max = self.operational_max_energy(solution=True)
        return

    def timeseries_report(self):
        """ Summaries the optimization results for this DER.

        Returns: A timeseries dataframe with user-friendly column headers that
            summarize the results pertaining to this instance

        """
        tech_id = self.unique_tech_id()
        results = super().timeseries_report()
        if self.incl_energy_limits:
            results[tech_id + ' User Energy Max (kWh)'] = self.limit_energy_max
            results[tech_id + ' User Energy Min (kWh)'] = self.limit_energy_min
        if self.incl_charge_limits:
            results[tech_id + ' User Charge Max (kW)'] = self.limit_charge_max
            results[tech_id + ' User Charge Min (kW)'] = self.limit_charge_min
        if self.incl_discharge_limits:
            results[tech_id + ' User Discharge Max (kW)'] = self.limit_discharge_max
            results[tech_id + ' User Discharge Min (kW)'] = self.limit_discharge_min

        return results

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
            TellUser.warning(f'The duration of {self.name} is greater than 24 hours!')
        if self.tag == 'CAES':
            return

        # warn about tight sizing margins
        if self.is_energy_sizing():
            energy_cap = self.energy_capacity(True)
            sizing_margin1 = (abs(energy_cap - self.user_ene_rated_max) - 0.05 * self.user_ene_rated_max)
            sizing_margin2 = (abs(energy_cap - self.user_ene_rated_min) - 0.05 * self.user_ene_rated_min)
            if (sizing_margin1 < 0).any() or (sizing_margin2 < 0).any():
                TellUser.warning("Difference between the optimal Battery ene max rated and user upper/lower "
                                 "bound constraints is less than 5% of the value of user upper/lower bound constraints")
        if self.is_charge_sizing():
            charge_cap = self.charge_capacity(True)
            sizing_margin1 = (abs(charge_cap - self.user_ch_rated_max) - 0.05 * self.user_ch_rated_max)
            sizing_margin2 = (abs(charge_cap - self.user_ch_rated_min) - 0.05 * self.user_ch_rated_min)
            if (sizing_margin1 < 0).any() or (sizing_margin2 < 0).any():
                TellUser.warning("Difference between the optimal Battery ch max rated and user upper/lower "
                                 "bound constraints is less than 5% of the value of user upper/lower bound constraints")
        if self.is_discharge_sizing():
            discharge_cap = self.discharge_capacity(True)
            sizing_margin1 = (abs(discharge_cap - self.user_dis_rated_max) - 0.05 * self.user_dis_rated_max)
            sizing_margin2 = (abs(discharge_cap - self.user_dis_rated_min) - 0.05 * self.user_dis_rated_min)
            if (sizing_margin1 < 0).any() or (sizing_margin2 < 0).any():
                TellUser.warning("Difference between the optimal Battery dis max rated and user upper/lower "
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
        discharge = self.discharge_capacity(solution=True)
        if discharge == 0 or energy_rated == 0:
            return 0
        return energy_rated / discharge

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
            self.variable_om = variable_om * 1e-3

        if self.incl_startup:
            p_start_ch = input_dict.get('p_start_ch')
            if p_start_ch is not None:
                self.p_start_ch = p_start_ch

            p_start_dis = input_dict.get('p_start_dis')
            if p_start_dis is not None:
                self.p_start_dis = p_start_dis

    def sizing_error(self):
        """

        Returns: True if there is an input error

        """
        if self.tag == 'CAES':
            return True
        if self.is_power_sizing() and self.incl_binary:
            TellUser.error(f'{self.unique_tech_id()} is being sized and binary is turned on. You will get a DCP error.')
            return True
        if self.user_ch_rated_min > self.user_ch_rated_max:
            TellUser.error(f'{self.unique_tech_id()} min charge power requirement is greater than max charge power requirement.')
            return True
        if self.user_dis_rated_min > self.user_dis_rated_max:
            TellUser.error(f'{self.unique_tech_id()} min discharge power requirement is greater than max discharge power requirement.')
            return True
        if self.user_ene_rated_min > self.user_ene_rated_max:
            TellUser.error(f'{self.unique_tech_id()} min energy requirement is greater than max energy requirement.')
            return True

    def max_p_schedule_down(self):
        # ability to provide regulation down through charging more
        if self.is_charge_sizing():
            if not self.user_ch_rated_max:
                max_charging_range = self.user_ch_rated_max - self.ch_min_rated
            else:
                max_charging_range = np.inf
        else:
            max_charging_range = self.ch_max_rated - self.ch_min_rated
        # ability to provide regulation down through discharging less
        if self.is_discharge_sizing():
            if not self.user_dis_rated_max:
                max_discharging_range = self.user_dis_rated_max - self.dis_min_rated
            else:
                max_discharging_range = np.inf
        else:
            max_discharging_range = self.dis_max_rated - self.dis_min_rated
        return max_charging_range + max_discharging_range

    def replacement_cost(self):
        """

        Returns: the cost of replacing this DER

        """
        return np.dot(self.replacement_cost_function, [1, self.discharge_capacity(True), self.energy_capacity(True)])

    def is_charge_sizing(self):
        return isinstance(self.ch_max_rated, cvx.Variable)

    def is_discharge_sizing(self):
        return isinstance(self.dis_max_rated, cvx.Variable)

    def is_power_sizing(self):
        return self.is_charge_sizing() or self.is_discharge_sizing()

    def is_energy_sizing(self):
        return isinstance(self.ene_max_rated, cvx.Variable)

    def max_power_defined(self):
        return (self.is_charge_sizing() and not self.user_ch_rated_max) and (self.is_discharge_sizing() and not self.user_dis_rated_max)
