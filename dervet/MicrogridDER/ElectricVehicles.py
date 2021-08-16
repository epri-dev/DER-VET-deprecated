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
Storage

This Python class contains methods and attributes specific for technology analysis within StorageVet.
"""
import logging
import cvxpy as cvx
import numpy as np
import pandas as pd
from storagevet.Technology.DistributedEnergyResource import DER
from dervet.MicrogridDER.DERExtension import DERExtension
from dervet.MicrogridDER.ContinuousSizing import ContinuousSizing
from storagevet.ErrorHandling import *


class ElectricVehicle1(DER, ContinuousSizing, DERExtension):
    """ A general template for storage object

    We define "storage" as anything that can affect the quantity of load/power being delivered or used. Specific
    types of storage are subclasses. The storage subclass should be called. The storage class should never
    be called directly.

    """

    def __init__(self, params):
        """ Initialize all technology with the following attributes.

        Args:
            params (dict): Dict of parameters
        """
        TellUser.debug(f"Initializing ElectricVehicle1")
        # create generic technology object
        DER.__init__(self, params)
        ContinuousSizing.__init__(self, params)
        DERExtension.__init__(self, params)

        self.technology_type = 'Electric Vehicle'
        self.tag = 'ElectricVehicle1'

        self.ene_target = params['ene_target']
        self.ch_max_rated = params['ch_max_rated']
        self.ch_min_rated = params['ch_min_rated']

        self.plugin_time = params['plugin_time']
        self.plugout_time = params['plugout_time']

        self.capital_cost_function = params['ccost']

        self.fixed_om = params['fixed_om']
        self.incl_binary = False  # params['binary'] #TODO

        self.variable_names = {'ene', 'ch', 'uene', 'uch', 'on_c'}

        # initialize any attributes you want to set and use later
        self.plugin_times_index = None
        self.plugout_times_index = None
        self.unplugged_index = None

    # def charge_capacity(self):
    #     """

    #     Returns: the maximum charge that can be attained

    #     """
    #     return self.ch_max_rated

    def initialize_variables(self, size):
        """ Adds optimization variables to dictionary

        Variables added: (with self.unique_ess_id as a prefix to these)
            ene (Variable): A cvxpy variable for Energy collected at the end of the time step (kWh)
            ch (Variable): A cvxpy variable for Charge Power, kW during the previous time step (kW)
            on_c (Variable/Parameter): A cvxpy variable/parameter to flag for charging in previous interval (bool)

        Notes:
            CVX Parameters turn into Variable when the condition to include them is active

        Args:
            size (Int): Length of optimization variables to create

        """
        self.variables_dict = {
            'ene': cvx.Variable(shape=size, name=self.name + '-ene'),
            'ch': cvx.Variable(shape=size, name=self.name + '-ch'),
            'uene': cvx.Variable(shape=size, name=self.name + '-uene'),  # TODO you can switch to parameter, where value == np.zeros(size)  -HN
            'uch': cvx.Variable(shape=size, name=self.name + '-uch'),  # TODO you can switch to parameter, where value == np.zeros(size)  -HN
            'on_c': cvx.Parameter(shape=size, name=self.name + '-on_c', value=np.ones(size)),

        }

        if self.incl_binary:
            self.variable_names.update(['on_c'])
            self.variables_dict.update({'on_c': cvx.Variable(shape=size, boolean=True, name=self.name + '-on_c')})

    def get_state_of_energy(self, mask):
        """
        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set

        Returns: the state of energy as a function of time for the

        """
        return self.variables_dict['ene']

    def get_charge(self, mask):
        """
        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set

        Returns: the charge as a function of time for the

        """
        return self.variables_dict['ch']

    def get_capex(self, **kwargs):
        """ Returns the capex of a given technology
        """
        return self.capital_cost_function

    def get_charge_up_schedule(self, mask):
        """ the amount of charging power in the up direction (supplying power up into the grid) that
        this DER can schedule to reserve

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                    in the subs data set

        Returns: CVXPY parameter/variable

        """
        return self.variables_dict['ch'] - self.ch_min_rated

    def get_charge_down_schedule(self, mask):
        """ the amount of charging power in the up direction (pulling power down from the grid) that
        this DER can schedule to reserve

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                    in the subs data set

        Returns: CVXPY parameter/variable

        """
        return self.ch_max_rated - self.variables_dict['ch']

    def get_delta_uenegy(self, mask):
        """ the amount of energy, from the current SOE level the DER's state of energy changes
        from subtimestep energy shifting

        Returns: the energy throughput in kWh for this technology

        """
        return self.variables_dict['uene']

    def get_uenergy_increase(self, mask):
        """ the amount of energy in a timestep that is provided to the distribution grid

        Returns: the energy throughput in kWh for this technology

        """
        return self.variables_dict['uch'] * self.dt

    def get_active_times(self, mask):
        """

        Args:
            mask:

        Returns:

        """
        compute_plugin_index = pd.DataFrame(index=mask.index)
        compute_plugin_index['plugin'] = compute_plugin_index.index.hour == self.plugin_time
        compute_plugin_index['plugout'] = compute_plugin_index.index.hour == self.plugout_time
        compute_plugin_index['unplugged'] = False

        if self.plugin_time < self.plugout_time:  # plugin time and plugout time must be different
            compute_plugin_index.loc[
                (compute_plugin_index.index.hour >= self.plugin_time) * (compute_plugin_index.index.hour < self.plugout_time), 'unplugged'] = True
        elif self.plugin_time > self.plugout_time:
            compute_plugin_index.loc[
                (compute_plugin_index.index.hour >= self.plugin_time) | (compute_plugin_index.index.hour < self.plugout_time), 'unplugged'] = True

        self.plugout_times_index = compute_plugin_index['plugout']
        self.plugin_times_index = compute_plugin_index['plugin']
        self.unplugged_index = compute_plugin_index['unplugged']

    def constraints(self, mask):
        """Default build constraint list method. Used by services that do not have constraints.

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                    in the subs data set

        Returns:
            A list of constraints that corresponds the EV requirement to collect the required energy to operate. It also allows
            flexibility to provide other grid services
        """

        constraint_list = []
        self.get_active_times(mask.loc[mask])  # constructing the array that indicates whether the ev is plugged or not

        # print(self.plugin_times_index.iloc[0:24])
        # print(self.plugout_times_index.iloc[0:24])
        # print(self.unplugged_index.iloc[0:24])
        # print('Ene target :' + str(self.ene_target))
        # print('Charging max :' + str(self.ch_max_rated))
        # print('Charging min :' + str(self.ch_min_rated))

        # optimization variables
        ene = self.variables_dict['ene']
        ch = self.variables_dict['ch']
        uene = self.variables_dict['uene']
        uch = self.variables_dict['uch']
        on_c = self.variables_dict['on_c']

        # collected energy at start time is zero for all start times
        constraint_list += [cvx.Zero(ene[self.plugin_times_index])]

        # energy evolution generally for every time step

        numeric_unplugged_index = pd.Series(range(len(self.unplugged_index)), index=self.unplugged_index.index).loc[self.unplugged_index]
        ene_ini_window = 0

        if numeric_unplugged_index.iloc[0] == 0:  # energy evolution for the EV, only during plugged times
            constraint_list += [cvx.Zero(ene[numeric_unplugged_index.iloc[0]] - ene_ini_window)]
            constraint_list += [cvx.Zero(ene[list(numeric_unplugged_index.iloc[1:])] - ene[list(numeric_unplugged_index.iloc[1:] - 1)] - (
                        self.dt * ch[list(numeric_unplugged_index.iloc[1:] - 1)]))]  # - uene[list(numeric_unplugged_index.iloc[1:]-1)])]
        else:
            constraint_list += [cvx.Zero(ene[list(numeric_unplugged_index)] - ene[list(numeric_unplugged_index - 1)] - (
                        self.dt * ch[list(numeric_unplugged_index - 1)]))]  # - uene[list(numeric_unplugged_index-1)])]
        # constraint_list += [cvx.Zero(ene[1:] - ene[:-1]  - ( self.dt * ch[:-1]) - uene[:-1])]

        # energy at plugout times must be greater or equal to energy target

        numeric_plugout_time_index = pd.Series(range(len(self.plugout_times_index)), index=self.plugout_times_index.index).loc[
            self.plugout_times_index]

        # the next few lines make sure that the state of energy at the end of the chargign period is equal to the target
        if numeric_plugout_time_index[0] == 0:
            constraint_list += [cvx.Zero(self.ene_target - ene[list(numeric_plugout_time_index.iloc[1:] - 1)] - (
                        self.dt * ch[list(numeric_plugout_time_index.iloc[1:] - 1)]))]  # - uene[list(numeric_plugout_time_index.iloc[1:]-1)])]
        else:
            constraint_list += [cvx.Zero(self.ene_target - ene[list(numeric_plugout_time_index - 1)] - (
                        self.dt * ch[list(numeric_plugout_time_index - 1)]))]  # - uene[list(numeric_plugout_time_index-1)])]

        constraint_list += [cvx.Zero(ene[list(numeric_plugout_time_index)] - self.ene_target)]

        # constraints on the ch/dis power

        # make it MILP or not depending on user selection
        if self.incl_binary:
            constraint_list += [cvx.NonPos(ch - (on_c * self.ch_max_rated))]
            constraint_list += [cvx.NonPos((on_c * self.ch_min_rated) - ch)]
        else:
            constraint_list += [cvx.NonPos(ch - self.ch_max_rated)]
            constraint_list += [cvx.NonPos(- ch)]

        # constraints to make sure that the ev does nothing when it is unplugged
        constraint_list += [cvx.NonPos(ch[~self.unplugged_index])]

        # account for -/+ sub-dt energy -- this is the change in energy that the battery experiences as a result of energy option
        # constraint_list += [cvx.Zero(uene - (uch * self.dt))]
        constraint_list += [cvx.Zero(uch)]  # TODO: you can set the variable to be parameters instead  -HN
        constraint_list += [cvx.Zero(uene)]  # TODO: you can set the variable to be parameters instead  -HN
        return constraint_list

    def timeseries_report(self):
        """ Summaries the optimization results for this DER.

        Returns: A timeseries dataframe with user-friendly column headers that
            summarize the results pertaining to this instance

        """
        tech_id = self.unique_tech_id()
        results = pd.DataFrame(index=self.variables_df.index)
        solve_dispatch_opt = self.variables_df.get('ch')
        if solve_dispatch_opt is not None:
            results[tech_id + ' Charge (kW)'] = self.variables_df['ch']
            results[tech_id + ' Power (kW)'] = -self.variables_df['ch']
            results[tech_id + ' State of Energy (kWh)'] = \
                self.variables_df['ene']

            results[tech_id + ' Energy Option (kWh)'] = \
                self.variables_df['uene']
            results[tech_id + ' Charge Option (kW)'] = self.variables_df['uch']

        return results

    def proforma_report(self, apply_inflation_rate_func, fill_forward_func, results):
        """ Calculates the proforma that corresponds to participation in this value stream

        Args:
            apply_inflation_rate_func:
            fill_forward_func:
            results (pd.DataFrame):

        Returns: A DateFrame of with each year in opt_year as the index and
            the corresponding value this stream provided.

        """
        pro_forma = super().proforma_report(apply_inflation_rate_func, fill_forward_func, results)
        if self.variables_df.empty:
            return pro_forma
        analysis_years = self.variables_df.index.year.unique()
        om_costs = pd.DataFrame()
        for year in analysis_years:
            # add fixed o&m costs
            index_yr = pd.Period(year=year, freq='y')
            om_costs.loc[index_yr, self.fixed_column_name()] = -self.fixed_om
        # fill forward
        om_costs = fill_forward_func(om_costs, None)
        # apply inflation rates
        om_costs = apply_inflation_rate_func(om_costs, None, min(analysis_years))
        # append will super class's proforma
        pro_forma = pd.concat([pro_forma, om_costs], axis=1)
        return pro_forma

    def sizing_summary(self):
        """ Creates the template for sizing df that each DER must fill to report their size.

        Returns: A dictionary describe this DER's size and captial costs.

        """
        # template = pd.DataFrame(columns=)
        sizing_dict = {
            'DER': np.nan,
            'Energy Rating (kWh)': np.nan,
            'Charge Rating (kW)': np.nan,
            'Discharge Rating (kW)': np.nan,
            'Round Trip Efficiency (%)': np.nan,
            'Lower Limit on SOC (%)': np.nan,
            'Upper Limit on SOC (%)': np.nan,
            'Duration (hours)': np.nan,
            'Capital Cost ($)': np.nan,
            'Capital Cost ($/kW)': np.nan,
            'Capital Cost ($/kWh)': np.nan,
            'Power Capacity (kW)': np.nan,
            'Quantity': 1,
        }
        return sizing_dict


class ElectricVehicle2(DER, ContinuousSizing, DERExtension):
    """ A general template for storage object

    We define "storage" as anything that can affect the quantity of load/power being delivered or used. Specific
    types of storage are subclasses. The storage subclass should be called. The storage class should never
    be called directly.

    """

    def __init__(self, params):
        """ Initialize all technology with the following attributes.

        Args:
            params (dict): Dict of parameters
        """
        TellUser.debug(f"Initializing ElectricVehicle2")
        # create generic technology object
        DER.__init__(self, params)
        ContinuousSizing.__init__(self, params)
        DERExtension.__init__(self, params)

        self.technology_type = 'Electric Vehicle'
        self.tag = 'ElectricVehicle2'

        # input params
        # note: these should never be changed in simulation (i.e from degradation)

        self.max_load_ctrl = params[
                                 'max_load_ctrl'] / 100.0  # maximum amount of baseline EV load that can be shed as a percentage of the original load
        # self.qualifying_cap = params['qualifying_cap'] #capacity that can be used for 'capacity' services (DR, RA) as a percentage of the baseline load
        self.lost_load_cost = params['lost_load_cost']
        self.incl_binary = params['binary']
        self.EV_load_TS = params['EV_baseline']

        self.capital_cost_function = params['ccost']

        self.fixed_om = params['fixed_om']

        self.variable_names = {'ch'}

    def qualifying_capacity(self, event_length):
        """ Describes how much power the DER can discharge to qualify for RA or DR. Used to determine
        the system's qualifying commitment.

        Args:
            event_length (int): the length of the RA or DR event, this is the
                total hours that a DER is expected to discharge for

        Returns: int/float

        """
        return 0

    def initialize_variables(self, size):
        """ Adds optimization variables to dictionary

        Variables added: (with self.unique_ess_id as a prefix to these)
            ene (Variable): A cvxpy variable for Energy collected at the end of the time step (kWh)
            ch (Variable): A cvxpy variable for Charge Power, kW during the previous time step (kW)
            on_c (Variable/Parameter): A cvxpy variable/parameter to flag for charging in previous interval (bool)

        Notes:
            CVX Parameters turn into Variable when the condition to include them is active

        Args:
            size (Int): Length of optimization variables to create

        """
        self.variables_dict = {
            'ch': cvx.Variable(shape=size, name=self.name + '-ch')
        }

        if self.incl_binary:
            self.variable_names.update(['on_c'])
            self.variables_dict.update({'on_c': cvx.Variable(shape=size, boolean=True, name=self.name + '-on_c')})

    def get_charge(self, mask):
        """
        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set

        Returns: the charge as a function of time for the

        """
        return self.variables_dict['ch']

    def get_capex(self, **kwargs):
        """ Returns the capex of a given technology
        """
        return self.capital_cost_function

    def get_charge_up_schedule(self, mask):
        """ the amount of charging power in the up direction (supplying power up into the grid) that
        this DER can schedule to reserve

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                    in the subs data set

        Returns: CVXPY parameter/variable



        """
        return self.variables_dict['ch'] - (1 - self.max_load_ctrl) * self.EV_load_TS[mask]

    def get_charge_down_schedule(self, mask):
        """ the amount of charging power in the up direction (pulling power down from the grid) that
        this DER can schedule to reserve

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                    in the subs data set

        Returns: CVXPY parameter/variable

        """
        return -self.variables_dict['ch'] + self.EV_load_TS[mask]

    def objective_function(self, mask, annuity_scalar=1):
        """ Generates the objective function related to a technology. Default includes O&M which can be 0

        Args:
            mask (Series): Series of booleans used, the same length as case.power_kw
            annuity_scalar (float): a scalar value to be multiplied by any yearly cost or benefit that helps capture the cost/benefit over
                    the entire project lifetime (only to be set iff sizing, else annuity_scalar should not affect the aobject function)

        Returns:
            self.costs (Dict): Dict of objective costs
        """

        # create objective expression for variable om based on discharge activity
        ch = self.variables_dict['ch']
        costs = {
            self.name + ' fixed_om': self.fixed_om * annuity_scalar,
            self.name + ' lost_load_cost': cvx.sum(self.EV_load_TS[mask].values - ch) * self.lost_load_cost  # added to account for lost load

        }
        # add startup objective costs

        return costs

    def constraints(self, mask):
        """Default build constraint list method. Used by services that do not have constraints.

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                    in the subs data set

        Returns:
            A list of constraints that corresponds the EV requirement to collect the required energy to operate. It also allows
            flexibility to provide other grid services
        """
        constraint_list = []

        # optimization variables

        ch = self.variables_dict['ch']
        # uch = self.variables_dict['uch']

        # constraints on the ch/dis power
        constraint_list += [cvx.NonPos(ch - self.EV_load_TS[mask].values)]
        constraint_list += [cvx.NonPos((1 - self.max_load_ctrl) * self.EV_load_TS[mask].values - ch)]

        # the constraint below limits energy throughput and total discharge to less than or equal to
        # (number of cycles * energy capacity) per day, for technology warranty purposes
        # this constraint only applies when optimization window is equal to or greater than 24 hours

        return constraint_list

    def timeseries_report(self):
        """ Summaries the optimization results for this DER.

        Returns: A timeseries dataframe with user-friendly column headers that
            summarize the results pertaining to this instance

        """
        tech_id = self.unique_tech_id()
        results = pd.DataFrame(index=self.variables_df.index)
        solve_dispatch_opt = self.variables_df.get('ch')
        if solve_dispatch_opt is not None:
            results[tech_id + ' EV Fleet Baseline Load'] = self.EV_load_TS
            results[tech_id + ' Charge (kW)'] = self.variables_df['ch']
            results[tech_id + ' Power (kW)'] = -self.variables_df['ch']

        return results

    def proforma_report(self, apply_inflation_rate_func, fill_forward_func, results):
        """ Calculates the proforma that corresponds to participation in this value stream

        Args:
            apply_inflation_rate_func:
            fill_forward_func:
            results (pd.DataFrame):

        Returns: A DateFrame of with each year in opt_year as the index and
            the corresponding value this stream provided.

        """
        pro_forma = super().proforma_report(apply_inflation_rate_func, fill_forward_func, results)
        if self.variables_df.empty:
            return pro_forma
        analysis_years = self.variables_df.index.year.unique()
        om_costs = pd.DataFrame()
        for year in analysis_years:
            # add fixed o&m costs
            index_yr = pd.Period(year=year, freq='y')
            om_costs.loc[index_yr, self.fixed_column_name()] = -self.fixed_om
        # fill forward
        om_costs = fill_forward_func(om_costs, None)
        # apply inflation rates
        om_costs = apply_inflation_rate_func(om_costs, None, min(analysis_years))
        # append will super class's proforma
        pro_forma = pd.concat([pro_forma, om_costs], axis=1)
        return pro_forma

    def sizing_summary(self):
        """ Creates the template for sizing df that each DER must fill to report their size.

        Returns: A dictionary describe this DER's size and captial costs.

        """
        # template = pd.DataFrame(columns=)
        sizing_dict = {
            'DER': np.nan,
            'Energy Rating (kWh)': np.nan,
            'Charge Rating (kW)': np.nan,
            'Discharge Rating (kW)': np.nan,
            'Round Trip Efficiency (%)': np.nan,
            'Lower Limit on SOC (%)': np.nan,
            'Upper Limit on SOC (%)': np.nan,
            'Duration (hours)': np.nan,
            'Capital Cost ($)': np.nan,
            'Capital Cost ($/kW)': np.nan,
            'Capital Cost ($/kWh)': np.nan,
            'Power Capacity (kW)': np.nan,
            'Quantity': 1,
        }
        return sizing_dict
