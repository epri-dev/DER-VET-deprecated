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

Third-Party Software
EPRI does not own any portion of the software that is attributed
below.

<CVXPY/1.1.11> - <Steven Diamond>, <diamond@cs.stanford.edu>
Copyright © 2017 Steven Diamond

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

CVXPY is provided by the copyright holders and contributors "as is" and
any express or implied warranties, including, but not limited to, the
implied warranties of merchantability and fitness for a particular
purpose are disclaimed.

This software relies on CVXPY to interface with work(s) covered by the
following copyright and permission notice(s): 

GLPK 5.0 - Andrew Makhorin, mao@gnu.org
Copyright © 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009,
2010, 2011, 2012 Andrew Makhorin, Department for Applied Informatics,
Moscow Aviation Institute, Moscow, Russia. All rights reserved.

Licensed under GNU Public License v3.0; you may not use GLPK except in
compliance with the License. You may obtain a copy of the License at
https://www.gnu.org/licenses/gpl-3.0.en.html.

GLPK is a free program and is provided by the copyright holders and
contributors "as is" and any express or implied warranties, including,
but not limited to, the implied warranties of merchantability and fitness
for a particular purpose are disclaimed.
"""
"""
Reliability.py

This Python class contains methods and attributes specific for service analysis
 within StorageVet.
"""

from storagevet.SystemRequirement import Requirement
import storagevet.Library as Lib
from storagevet.ValueStreams.ValueStream import ValueStream
import numpy as np
import cvxpy as cvx
import pandas as pd
import time
import random
from storagevet.ErrorHandling import *
import copy

DEBUG = False


class Reliability(ValueStream):
    """ Reliability Service
    """

    def __init__(self, params):
        """ Generates the objective function, finds and creates constraints.

          Args:
            params (Dict): input parameters
        """
        # INHERIT FROM PARENT
        super().__init__('Reliability', params)

        # USER GIVEN VALUES
        self.outage_duration = int(params['target'])  # must be in hours
        self.dt = params['dt']
        self.post_facto_only = params['post_facto_only']
        self.soc_init = params['post_facto_initial_soc'] / 100
        self.max_outage_duration = params['max_outage_duration']
        self.n_2 = params['n-2']
        self.critical_load = params['critical load']
        self.load_shed = params['load_shed_percentage']

        # PRE-CALCULATED VALUES
        if self.load_shed:
            self.load_shed_data = params['load_shed_data']['Load Shed (%)']
        # determines how many time_series timestamps relates to the reliability
        # target hours to cover NOTE: integral type for indexing
        self.coverage_dt = int(np.round(self.outage_duration / self.dt))
        self.requirement = self.rolling_sum(self.critical_load.loc[:],
                                            self.coverage_dt) * self.dt

        # INITIAL ATTRIBUTES TO BE SET LATER
        self.outage_contribution_df = None
        self.min_soe_df = None
        self.outage_soe_profile = None
        self.soe_profile_all_0 = {}
        self.soe_profile_all_1 = {}
        # this is the rating of all DERs (expect for the intermittent ER)
        self.dg_rating = 0

        self.use_soc_init = False
        self.use_user_const = False
        self.use_sizing_module_results = False

    def grow_drop_data(self, years, frequency, load_growth):
        """ Adds data by growing the given data OR drops any extra data that
        might have slipped in. Update variable that hold timeseries data
        after adding growth data. These method should be called after
        add_growth_data and before the optimization is run.

        Args:
            years (List): list of years for which analysis will occur on
            frequency (str): period frequency of the timeseries data
            load_growth (float): percent/ decimal value of the growth rate of
                loads in this simulation

        """
        self.critical_load = Lib.fill_extra_data(self.critical_load, years, load_growth, frequency)
        self.critical_load = Lib.drop_extra_data(self.critical_load, years)

    def sizing_module(self, der_lst, opt_index):
        """ sizing module

        Args:
            der_lst: list of ders, where some ders need to be sized
            opt_index: pandas index of the full analysis horizon

        Returns: list of ders with size solved for the objective of reliability

        """
        der_list = copy.deepcopy(der_lst)

        top_n_outages = 10
        data_size = len(opt_index)
        first_fail_ind = 0

        # Sort the outages by max demand that is unserved
        indices = np.argsort(-1 * self.requirement)

        # Find the top n analysis indices that we are going to size our DER mix
        # for.
        analysis_indices = indices[:top_n_outages].values

        # stop looping when find first uncovered == -1 (got through entire opt
        while first_fail_ind >= 0:
            TellUser.debug(f"Sizing - first failure index: {first_fail_ind}")
            der_list = self.size_for_outages(opt_index, analysis_indices,
                                             der_list)
            dg_gen, total_pv_max, der_props, total_pv_vari, largest_gamma = \
                self.get_der_mix_properties(der_list, True)

            no_of_es = len(der_props['rte list'])
            if no_of_es == 0:
                soe = np.zeros(data_size)
                der_props = None
            else:
                soe = np.repeat(self.soc_init, data_size) * der_props['energy rating']
            start = 0
            first_fail_ind = 0
            # note: if this is too large, then you will get a RecursionError
            check_at_a_time = 500
            while start == first_fail_ind:
                first_fail_ind = self.find_first_uncovered(dg_gen,
                                                           total_pv_max,
                                                           total_pv_vari,
                                                           largest_gamma,
                                                           der_props, soe,
                                                           start,
                                                           check_at_a_time)
                start += check_at_a_time
            analysis_indices = np.append(analysis_indices, first_fail_ind)

        for der_inst in der_list:
            if der_inst.being_sized():
                der_inst.set_size()

        # check if there is ES in the der_list before determing the min SOE
        # profile
        for der_inst in der_list:
            if der_inst.technology_type == 'Energy Storage System' and der_inst.ene_max_rated > 0:
                # This is a faster method to find approximate min SOE
                der_list = self.min_soe_iterative(opt_index, der_list)

                # This is a slower method to find optimal min SOE
                # der_list = reliability_mod.min_soe_opt(opt_index, der_list)

        return der_list

    def size_for_outages(self, opt_index, outage_start_indices, der_list):
        """ Sets up sizing optimization.

        Args:
            opt_index (Index): index should match the index of the timeseries
                data being passed around
            der_list (list): list of initialized DERs from the POI class
            outage_start_indices

        Returns: modified DER list

        """

        consts = []
        cost_funcs = sum([der_instance.get_capex() for der_instance in der_list])
        outage_length = int(self.outage_duration / self.dt)

        mask = pd.Series(index=opt_index)
        for outage_ind in outage_start_indices:
            mask.iloc[:] = False
            mask.iloc[outage_ind: (outage_ind + outage_length)] = True
            # set up variables
            gen_sum = cvx.Parameter(value=np.zeros(outage_length),
                                    shape=outage_length, name='POI-Zero')
            tot_net_ess = cvx.Parameter(value=np.zeros(outage_length),
                                        shape=outage_length, name='POI-Zero')

            for der_instance in der_list:
                # initialize variables
                der_instance.initialize_variables(outage_length)
                consts += der_instance.constraints(mask, sizing_for_rel=True,
                                                   find_min_soe=False)
                if der_instance.technology_type == 'Energy Storage System':
                    tot_net_ess += der_instance.get_net_power(mask)
                if der_instance.technology_type == 'Generator':
                    gen_sum += der_instance.get_discharge(mask)
                if der_instance.technology_type == 'Intermittent Resource':
                    gen_sum += der_instance.get_discharge(mask) * \
                               der_instance.nu
            critical_load = self.critical_load.loc[mask].values
            if self.load_shed:
                critical_load = critical_load * (self.load_shed_data[0:outage_length].values / 100)

            critical_load_arr = cvx.Parameter(value=critical_load,
                                              shape=outage_length)
            consts += [
                cvx.NonPos(tot_net_ess + (-1) * gen_sum + critical_load_arr)
            ]

        obj = cvx.Minimize(cost_funcs)
        prob = cvx.Problem(obj, consts)
        prob.solve(solver=cvx.GLPK_MI)

        return der_list

    def get_der_mix_properties(self, der_list, need_solution=False):
        """ collect information required to call simulate_outage

        TODO change handling of multiple ESS
        Args:
            der_list: lis to DERs for reliability
            need_solution: this flag is true if DER parameters are optimization
                variables. Need to get .value to get value of the parameters


        Returns:

        """
        props = {  # der properties
            'charge max': 0,
            'discharge max': 0,
            'rte list': [],
            'operation SOE min': 0,
            'operation SOE max': 0,
            'energy rating': 0,
            'pv present': False
        }
        # PV generation w/o variability taken into account
        tot_pv_max = np.zeros(len(self.critical_load))
        # PV generation w/ variability taken into account
        tot_pv_vari = np.zeros(len(self.critical_load))
        largest_gamma = 0
        total_dg_max = 0
        for der_inst in der_list:
            if der_inst.technology_type == 'Intermittent Resource' and \
                    (not der_inst.being_sized() or not need_solution):
                pv_inst_gen = der_inst.maximum_generation()
                tot_pv_max += pv_inst_gen
                tot_pv_vari += pv_inst_gen * der_inst.nu
                largest_gamma = max(largest_gamma, der_inst.gamma)
                props['pv present'] = True
            if der_inst.technology_type == 'Generator' and \
                    (not der_inst.being_sized() or not need_solution):
                total_dg_max += der_inst.max_power_out()
            if der_inst.technology_type == 'Energy Storage System':
                props['rte list'].append(der_inst.rte)
                props['operation SOE min'] += \
                    der_inst.operational_min_energy(solution=need_solution)
                props['operation SOE max'] += \
                    der_inst.operational_max_energy(solution=need_solution)
                props['discharge max'] += \
                    der_inst.discharge_capacity(solution=need_solution)
                props['charge max'] += \
                    der_inst.charge_capacity(solution=need_solution)
                props['energy rating'] += \
                    der_inst.energy_capacity(solution=need_solution)
        # takes care of N-2 case
        if self.n_2:
            total_dg_max -= self.dg_rating
        tot_dg_gen = np.repeat(total_dg_max, len(self.critical_load))

        return tot_dg_gen, tot_pv_max, props, tot_pv_vari, largest_gamma

    def calculate_system_requirements(self, der_lst):
        """ Calculate the system requirements that must be meet regardless of
        what other value streams are active. However these requirements do
        depend on the technology that are active in our analysis

        Args:
            der_lst (list): list of the initialized DERs in our scenario

        """
        if not self.post_facto_only and self.min_soe_df is not None:
            for der_instance in der_lst:
                if der_instance.technology_type == 'Energy Storage System':
                    # add the power and energy constraints to ensure enough
                    # energy and power in the ESS for the next x hours there
                    # will be 2 constraints: one for power, one for energy
                    soe_array = self.min_soe_df['soe']
                    self.system_requirements = [
                        Requirement('energy', 'min', self.name, soe_array)
                    ]
                    # this should be the constraint that makes sure the next x
                    # hours have enough energy

    @staticmethod
    def rolling_sum(data, window):
        """ calculate a rolling sum of the date

        Args:
            data (DataFrame, Series): data of integers that can be added
            window (int): number of indexes to add

        Returns:

        """
        # reverse the time series to use rolling function
        reverse = data.iloc[::-1]
        # rolling function looks back, so reversing looks forward
        reverse = reverse.rolling(window, min_periods=1).sum()
        # set it back the right way
        data = reverse.iloc[::-1]
        return data

    @staticmethod
    def get_first_data(array):
        """ TODO fill this

        Args:
            array:

        Returns:

        """
        try:
            first_data = array[0]
        except KeyError:
            first_data = array.values[0]
        return first_data

    def find_first_uncovered(self, generation, total_pv_max, total_pv_vari,
                             largest_gamma, ess_properties=None, soe=None,
                             start_indx=0, stop_at=600):
        """ THis function will return the first outage that is not covered with
         the given DERs

        Args:
            generation:
            total_pv_max:
            total_pv_vari:
            largest_gamma:
            ess_properties (dict): dictionary that describes the physical
                properties of the ess in the analysis includes 'charge max',
                'discharge max, 'operation SOE min', 'operation SOE max', 'rte'
            soe (list, None): if ESSs are active, then this is an array
                indicating the soe at the start of the outage
            start_indx (int): start index, idetifies the index of the start of
                the outage we are going to simulate
            stop_at (int): when the start_index is divisible by this number,
                stop recursion

        Returns: index of the first outage that cannot be covered by the DER
            sizes, or -1 if none is found

        """
        # base case 1: outage_init is beyond range of critical load
        if start_indx >= (len(self.critical_load)):
            return -1
        # find longest possible outage

        demand_left, reliability_check, energy_requirement_check = \
            self.data_process(start_indx, generation, total_pv_max,
                              ess_properties, total_pv_vari,
                              largest_gamma)
        ess_properties['init_soe'] = soe[start_indx]
        soe_profile = self.simulate_outage(reliability_check, demand_left,
                                           energy_requirement_check,
                                           self.max_outage_duration / self.dt,
                                           **ess_properties)

        longest_outage = len(soe_profile)
        # base case 2: longest outage is less than the outage duration target
        if longest_outage < self.outage_duration / self.dt:
            if longest_outage < (len(self.critical_load) - start_indx):
                return start_indx
        # base case 3: break recursion when you get to this (like a limit to
        # the resursion)
        if (start_indx + 1) % stop_at == 0:
            return start_indx + 1
        # else, go on to test the next outage_init (increase index returned
        return self.find_first_uncovered(generation, total_pv_max,
                                         total_pv_vari, largest_gamma,
                                         ess_properties=ess_properties,
                                         soe=soe, start_indx=start_indx + 1,
                                         stop_at=stop_at)

    def data_process(self, ts_index, generation, total_pv_max,
                     ess_properties, total_pv_vari, largest_gamma):
        """ TODO fill this out

        Args:
            ts_index:
            generation:
            total_pv_max:
            ess_properties: (unused by method TODO: remove)
            total_pv_vari:
            largest_gamma:

        Returns:

        """
        ts_max_index = ts_index + self.max_outage_duration
        critical_load_sub = self.critical_load.values[ts_index:ts_max_index]
        gen_sub = generation[ts_index:ts_max_index]
        var_pv_sub = total_pv_vari[ts_index:ts_max_index]
        max_pv_sub = total_pv_max[ts_index:ts_max_index]
        if not self.load_shed:
            demand_left = np.around(critical_load_sub - gen_sub - max_pv_sub,
                                    decimals=5)
            reliability_check = np.around(critical_load_sub - gen_sub -
                                          var_pv_sub, decimals=5)
            energy_requirement_check = reliability_check * largest_gamma
        else:
            extra_index = ts_max_index - len(self.critical_load)
            if extra_index <= 0:
                cl_with_loadshed = critical_load_sub * \
                                   (self.load_shed_data / 100)
            else:
                load_shed_data = self.load_shed_data[:-extra_index]
                cl_with_loadshed = critical_load_sub * (load_shed_data / 100)
            demand_left = np.around(cl_with_loadshed - gen_sub - max_pv_sub,
                                    decimals=5)
            reliability_check = np.around(cl_with_loadshed - gen_sub -
                                          var_pv_sub, decimals=5)
            energy_requirement_check = reliability_check * largest_gamma

        return demand_left, reliability_check, energy_requirement_check

    def simulate_outage(self, reliability_check, demand_left, energy_check,
                        outage_left, **kwargs):
        """ Simulate an outage that starts with lasting only 1 hour and will
        either last as long as MAX_OUTAGE_LENGTH or the iteration loop hits
        the end of any of the array arguments. Updates and tracks the SOC
        throughout the outage
        Args:
            reliability_check (np.ndarray): the amount of load minus fuel
                generation and a percentage of PV generation
            demand_left (np.ndarray): the amount of load minus fuel generation
                and all of PV generation
            energy_check (np.ndarray):
            outage_left (int): the length of outage yet to be simulated
            kwargs (dict): dictionary that describes the physical properties of
                the ess or PV in the analysis includes:
                    charge max
                    discharge max
                    operation SOE min
                    operation SOE max
                    rte
                    init_soe (float, None): the soc of the ESS (if included in
                        analysis) at the beginning of time t

        Returns: an 1 x M dimensional list where M is the SOC at each index in
            time

        TODO return an N x M dimensional list where N is the number of ESS
            present and M is the SOC at each index in time
        """
        # select init_soe if included, else use user defined soc
        init_soe = kwargs.get('init_soe', self.soc_init*kwargs.get('energy rating', 0))
        # base case: when to terminate recursion
        if outage_left == 0 or not len(reliability_check):
            return []
        current_reliability_check = self.get_first_data(reliability_check)
        current_demand_left = self.get_first_data(demand_left)
        current_energy_check = self.get_first_data(energy_check)
        if 0 >= current_reliability_check:
            # check to see if there is space to storage energy in the ESS to
            # save extra generation
            physical_energy_max = kwargs.get('operation SOE max', 0)
            if physical_energy_max >= init_soe:
                # the amount we can charge based on its current SOC
                random_rte = random.choice(kwargs.get('rte list', []))
                charge_possible = (physical_energy_max - init_soe) / (random_rte * self.dt)
                charge = min(charge_possible, -current_demand_left, kwargs.get('charge max', 0))
                # update the state of charge of the ESS
                next_soe = init_soe + (charge * random_rte * self.dt)
            else:
                # there is no space to save the extra generation, so the ess
                # will not do anything
                next_soe = init_soe
        # can reliably meet the outage in that timestep: jump to SIMULATE
        # OUTAGE IN NEXT TIMESTEP
        else:
            # check that there is enough SOC in the ESS to satisfy worst case
            energy_min = kwargs.get('operation SOE min')
            if energy_min is not None:
                if 0 >= np.around(current_energy_check * self.dt - init_soe, decimals=2):
                    # so discharge to meet the load offset by all generation
                    discharge_possible = (init_soe - energy_min) / self.dt
                    discharge = min(discharge_possible, current_demand_left,
                                    kwargs.get('discharge max', 0))
                    if 0 < np.around(current_demand_left - discharge, decimals=2):
                        # can't discharge enough to meet demand
                        return []
                    # update the state of charge of the ESS
                    next_soe = init_soe - (discharge * self.dt)
                    # we can reliably meet the outage in that timestep: jump to
                    # SIMULATE OUTAGE IN NEXT TIMESTEP
                else:
                    # there is not enough energy in the ESS to cover the load
                    # reliability
                    return []
            else:
                # there is no more that can be discharged to meet the load
                # requirement
                return []
        # SIMULATE OUTAGE IN NEXT TIMESTEP
        kwargs['init_soe'] = next_soe
        return [next_soe] + self.simulate_outage(reliability_check[1:], demand_left[1:],
                                                 energy_check[1:], outage_left - 1, **kwargs)

    def min_soe_opt(self, opt_index, der_list):
        """ Calculates min SOE at every time step for the given DER size

           Args:
               opt_index
               der_list

        Returns: der_list -- ESSs will have an SOE min if they were sized for
            reliability
        """

        month_min_soc = {}
        data_length = len(opt_index)
        for month in opt_index.month.unique():

            outage_mask = month == opt_index.month
            consts = []

            min_soc = {}
            ana_ind = [a for a in range(data_length) if outage_mask[a] is True]
            outage_mask = pd.Series(index=opt_index)
            for outage_ind in ana_ind:
                outage_end_ind = outage_ind + self.outage_duration
                outage_mask.iloc[:] = False
                outage_mask.iloc[outage_ind:outage_end_ind] = True
                # set up variables
                var_gen_sum = cvx.Parameter(
                    value=np.zeros(self.outage_duration),
                    shape=self.outage_duration,
                    name='POI-Zero')  # at POI
                dg_sum = cvx.Parameter(value=np.zeros(self.outage_duration),
                                       shape=self.outage_duration,
                                       name='POI-Zero')
                net_ess = cvx.Parameter(
                    value=np.zeros(self.outage_duration),
                    shape=self.outage_duration,
                    name='POI-Zero')

                for der in der_list:
                    # initialize variables
                    der.initialize_variables(self.outage_duration)

                    if der.technology_type == 'Energy Storage System':
                        net_ess += der.get_net_power(outage_mask)
                        # set the soc_target to a CVXPY variable
                        var_name = f"{der.name}{outage_ind}-min_soc"
                        der.soc_target = cvx.Variable(shape=1,
                                                               name=var_name)
                        min_soc[outage_ind] = der.soc_target

                        # Assuming Soc_init is the soc reservation required for
                        # other services
                        consts += [
                            cvx.NonPos(der.soc_target - 1)
                        ]  # check to include ulsoc
                        consts += [
                            cvx.NonPos(-der.soc_target + (1 - self.soc_init))
                        ]

                    if der.technology_type == 'Generator':
                        dg_sum += der.get_discharge(outage_mask)
                    if der.technology_type == 'Intermittent Resource':
                        var_gen_sum += der.get_discharge(outage_mask)

                    consts += der.constraints(outage_mask,
                                              sizing_for_rel=True,
                                              find_min_soe=True)

                if outage_ind + self.outage_duration > data_length:
                    remaining_out_duration = data_length - outage_ind
                    crit_load_values = np.zeros(self.outage_duration)
                    crit_load_values[0:remaining_out_duration] = \
                        self.critical_load.loc[outage_mask].values
                    load = cvx.Parameter(value=crit_load_values,
                                         shape=self.outage_duration)

                else:
                    load = cvx.Parameter(
                        value=self.critical_load.loc[outage_mask].values,
                        shape=self.outage_duration)
                consts += [
                    cvx.Zero(net_ess + (-1)*dg_sum + (-1)*var_gen_sum + load)
                ]

            cost_funcs = sum(min_soc.values())
            obj = cvx.Minimize(cost_funcs)
            prob = cvx.Problem(obj, consts)
            prob.solve(solver=cvx.GLPK_MI)

            month_min_soc[month] = min_soc

        for der in der_list:
            if der.technology_type == 'Energy Storage System':
                # TODO multi ESS
                # Get energy rating
                energy_rating = der.energy_capacity(True)

                # Collecting soe array for all ES
                month_min_soc_array = []
                outage_ind = 0
                # TODO make sure this is in order
                for month in month_min_soc.keys():
                    for hours in range(len(month_min_soc[month])):
                        month_min_soc_array.append(
                            month_min_soc[month][outage_ind].value[0])
                        outage_ind += 1
                month_min_soe_array = (
                            np.array(month_min_soc_array) * energy_rating)

        self.min_soe_df = pd.DataFrame({'soe': month_min_soe_array},
                                       index=opt_index)
        return der_list

    def min_soe_iterative(self, opt_index, der_list):
        """ Calculates min SOE at every time step for the given DER size

           Args:
               opt_index
               der_list

        Returns: der_list -- ESSs will have an SOE min if they were sized for
            reliability

        """

        for der_instance in der_list:

            if der_instance.technology_type == 'Energy Storage System':
                # TODO multi ESS
                # Get energy rating
                energy_rating = der_instance.energy_capacity(True)
                min_soe_array = []
                # Check if ES is sized for Reliability:
                if energy_rating > 0:

                    dg_gen, pv_max, der_props, pv_vari, largest_gamma = \
                        self.get_der_mix_properties(der_list)

                    soe = np.repeat(self.soc_init*der_props['energy rating'],
                                    len(self.critical_load))
                    for outage_init in range(len(opt_index)):
                        demand, power_req, energy_req = \
                            self.data_process(outage_init, dg_gen,
                                              pv_max,
                                              der_props,
                                              pv_vari,
                                              largest_gamma)
                        der_props['init_soe'] = soe[outage_init]
                        outage_len = self.outage_duration / self.dt
                        soe_outage_profile = \
                            self.simulate_outage(power_req, demand, energy_req,
                                                 outage_len, **der_props)

                        soe_outage_profile.insert(0, soe[outage_init])
                        min_soe_array.append(self.soe_used(soe_outage_profile))
                    # TODO eventually going to give this to ESS to apply on
                    #  itself
                    self.min_soe_df = pd.DataFrame(min_soe_array,
                                                   index=opt_index,
                                                   columns=['soe'])
        return der_list

    def soe_used(self, soe_profile):
        """ this is the range that the battery system as to be able to achieve
        during the corresponding outage in order for the outage to be
        reliability covered

        Args:
            soe_profile (list): the SOE profile of an ESS system during a
                simulated outage

        Returns (float) : Maximum SOE of profile - Minimum SOE of profile

        """
        min_soe = np.min(soe_profile)
        max_soe = np.max(soe_profile)
        effective_soe = max_soe - min_soe
        dict_size = len(self.soe_profile_all_0)
        if len(soe_profile) == 3:
            self.soe_profile_all_0[dict_size] = soe_profile[1]
            self.soe_profile_all_1[dict_size] = soe_profile[2]
        else:
            self.soe_profile_all_0[dict_size] = 0
            self.soe_profile_all_1[dict_size] = 0
        return effective_soe

    def timeseries_report(self):
        """ Summaries the optimization results for this Value Stream.

        Returns: A timeseries dataframe with user-friendly column headers that
            summarize the results pertaining to this instance

        """
        report = pd.DataFrame(index=self.critical_load.index)
        if not self.post_facto_only:
            report.loc[:, 'Total Critical Load (kWh)'] = self.requirement

        report.loc[:, 'Critical Load (kW)'] = self.critical_load
        if self.min_soe_df is not None:
            report.loc[:, 'Reliability Min State of Energy (kWh)'] = \
                self.min_soe_df['soe']
            # These two following lines have to commented out if using the optimized soe routine
            report.loc[:, 'Reliability Min SOE profile 0'] = \
                self.soe_profile_all_0.values()
            report.loc[:, 'Reliability Min SOE profile 1'] = \
                self.soe_profile_all_1.values()

        return report

    def drill_down_reports(self, monthly_data=None, time_series_data=None,
                           technology_summary=None, sizing_df=None,
                           der_list=None):
        """ Calculates any service related dataframe that is reported to the
        user.

        Returns: dictionary of DataFrames of any reports that are value stream
            keys are the file name that the df will be saved with

        """
        df_dict = {}
        TellUser.info(
            'Starting load coverage calculation. This may take a while.')
        df_dict['load_coverage_prob'] = self.load_coverage_probability(
            der_list, time_series_data, technology_summary)
        TellUser.info('Finished load coverage calculation.')
        if 'Energy Storage System' in technology_summary['Type'].values:
            df_dict['lcp_outage_soe_profiles'] = self.outage_soe_profile
        # calculate potential energy contribution from each DER in every outage
        if not self.post_facto_only:
            self.contribution_summary(technology_summary, time_series_data)
            df_dict['outage_energy_contributions'] = \
                self.outage_contribution_df

        return df_dict

    def contribution_summary(self, technology_summary_df, results):
        """ Determines that contribution from each DER type in the event of an
        outage. Call IFF attribute POST_FACTO_ONLY is False

        Args:
            technology_summary_df (DataFrame): list of active technologies
            results (DataFrame): dataframe that holds all the results of the
                optimzation

        Returns: dataframe of der's outage contribution

        """
        outage_energy = self.requirement
        contribution_arrays = {}

        pv_names = technology_summary_df.loc[
            technology_summary_df['Type'] == 'Intermittent Resource']
        if len(pv_names):
            agg_pv_max = np.zeros(len(results))
            for name in pv_names['Name']:
                agg_pv_max += results.loc[:, f'PV: {name} Maximum (kW)'].values
            agg_pv_max = pd.Series(agg_pv_max, index=results.index)
            # rolling sum of energy within a coverage_timestep window
            pv_outage_e = self.rolling_sum(agg_pv_max,
                                           self.coverage_dt) * self.dt
            # try to cover as much of the outage that can be with PV energy
            net_outage_energy = outage_energy - pv_outage_e
            # pv generation might have more energy than in the outage, so dont
            # let energy go negative
            outage_energy = net_outage_energy.clip(lower=0)

            # remove any extra energy from PV contribution
            pv_outage_e += net_outage_energy.clip(upper=0)

            # record contribution
            contribution_arrays.update({'PV Outage Contribution (kWh)': pv_outage_e})

        ess_names = technology_summary_df.loc[
            technology_summary_df['Type'] == 'Energy Storage System']
        if len(ess_names):
            try:
                ess_outage = results.loc[:, 'Aggregated State of Energy (kWh)']

            except KeyError:
                ess_outage = results.loc[:, 'Reliability Min State of Energy (kWh)']

            # try to cover as much of the outage that can be with the ES
            net_outage_energy = outage_energy - ess_outage
            # ESS might have more energy than in the outage, so dont let energy
            # go negative
            outage_energy = net_outage_energy.clip(lower=0)

            # remove any extra energy from ESS contribution
            ess_outage = ess_outage + net_outage_energy.clip(upper=0)

            # record contribution
            contribution_arrays.update(
                {'Storage Outage Contribution (kWh)': ess_outage.values})

        ice_names = technology_summary_df.loc[
            technology_summary_df['Type'] == 'ICE']
        if len(ice_names):
            # supplies what every energy that cannot be by pv and diesel
            # diesel_contribution is what ever is left
            contribution_arrays.update(
                {'ICE Outage Contribution (kWh)': outage_energy.values})

        self.outage_contribution_df = pd.DataFrame(contribution_arrays,
                                                   index=self.critical_load.index)

    def load_coverage_probability(self, der_list, results_df,
                                  technology_summary_df):
        """ Creates and returns a data frame with that reports the load
        coverage probability of outages that last from 0 to OUTAGE_LENGTH
        hours with the DER mix described in TECHNOLOGIES

        Args:
            results_df (DataFrame): the dataframe that consolidates all results
            technology_summary_df(DataFrame): maps DER type to user inputted
                name that indexes the size df
            der_list (list): list of ders

        Returns: DataFrame with 2 columns - 'Outage Length (hrs)' and
            'Load Coverage Probability (%)'

        """
        start = time.time()
        if 'Energy Storage System' in technology_summary_df['Type'].values:
            no_storage_case=False
        else:
            no_storage_case=True
        # 1) collect information required to call simulate_outage

        aggregate_soe = None
        dg_gen, total_pv_max, der_props, total_pv_vari, largest_gamma = \
            self.get_der_mix_properties(der_list)
        if no_storage_case==False:
            # save the state of charge
            if self.use_user_const:
                aggregate_soe = results_df.loc[:, 'Aggregate Energy Min (kWh)']
            elif not self.use_soc_init:
                if self.use_sizing_module_results:
                    aggregate_soe = results_df.loc[:, 'Reliability Min State of Energy (kWh)']
                else:
                    aggregate_soe = results_df.loc[:, 'Aggregated State of Energy (kWh)']

        end = time.time()
        TellUser.info(f'Critical Load Coverage Curve overhead time: {end - start}')

        # 2) simulate outage starting on every timestep
        start = time.time()
        outage_len = int(self.max_outage_duration / self.dt)
        # initialize a list to track the frequency of the results of the
        # simulate_outage method
        frequency_simulate_outage = np.zeros(outage_len + 1)
        outage_init = 0
        self.outage_soe_profile = {hour+1: [] for hour in range(outage_len)}
        while outage_init < (len(self.critical_load)):
            if no_storage_case==False:
                if aggregate_soe is not None:
                    der_props['init_soe'] = aggregate_soe[outage_init]
            demand_left, reliability_check, energy_requirement_check = \
                self.data_process(outage_init, dg_gen,
                                  total_pv_max, der_props,
                                  total_pv_vari, largest_gamma)
            if no_storage_case==True:
                # In case energy storage is not present, no outage simulation is required
                #Is there a failure
                if any(reliability_check>0)==True:
                    failure_ind=np.where((reliability_check>0)==True)[0]
                    coverage_length=failure_ind[0]
                else:
                    coverage_length=len(reliability_check)
                # record value of foo in frequency count
                frequency_simulate_outage[int(coverage_length)] += 1

            else:
                #Outage simulation in the presence of energy storage
                outage_soc_profile = self.simulate_outage(reliability_check,
                                                          demand_left,
                                                          energy_requirement_check,
                                                          outage_len,
                                                          **der_props)

                # record value of foo in frequency count
                coverage_length = len(outage_soc_profile)
                for key, value in self.outage_soe_profile.items():
                    value.append(outage_soc_profile[key-1] if key-1 < coverage_length else 0)

                frequency_simulate_outage[int(coverage_length)] += 1
            # start outage on next timestep
            outage_init += 1
        if no_storage_case==False:
            self.outage_soe_profile = pd.DataFrame(self.outage_soe_profile,
                                                   index=self.critical_load.index)
            self.outage_soe_profile.fillna(0, inplace=True)
        # 3) calculate probabilities
        load_coverage_prob = []
        length = self.dt
        while length <= self.max_outage_duration:
            scenarios_covered = frequency_simulate_outage[
                                int(length / self.dt):].sum()
            total_possible_scenarios = len(self.critical_load) - (
                        length / self.dt) + 1
            percentage = scenarios_covered / total_possible_scenarios
            load_coverage_prob.append(percentage)
            length += self.dt

        # 3) build DataFrame to return
        outage_coverage = {'Outage Length (hrs)': np.arange(self.dt,
                                                            self.max_outage_duration + self.dt,
                                                            self.dt),
                           'Load Coverage Probability (%)': load_coverage_prob}
        end = time.time()
        TellUser.info(
            f'Critical Load Coverage Curve calculation time: {end - start}')
        lcpc_df = pd.DataFrame(outage_coverage)
        lcpc_df.set_index('Outage Length (hrs)', inplace=True)
        return lcpc_df
