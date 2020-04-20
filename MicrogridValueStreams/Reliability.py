"""
Reliability.py

This Python class contains methods and attributes specific for service analysis within StorageVet.
"""

__author__ = 'Suma Jothibasu, Halley Nathwani and Miles Evans'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'mevans@epri.com']
__version__ = '0.1.1'

import storagevet.Constraint as Const
import numpy as np
import storagevet
import cvxpy as cvx
import pandas as pd
import time
import logging
import random

u_logger = logging.getLogger('User')
DEBUG = False


class Reliability(storagevet.ValueStream):
    """ Reliability Service. Each service will be daughters of the PreDispService class.
    """

    def __init__(self, params):
        """ Generates the objective function, finds and creates constraints.

          Args:
            params (Dict): input parameters
        """

        # generate the generic predispatch service object
        super().__init__('Reliability', params)
        self.outage_duration_coverage = params['target']  # must be in hours
        self.dt = params['dt']
        self.post_facto_only = params['post_facto_only']
        self.nu = params['nu'] / 100
        self.gamma = params['gamma'] / 100
        self.max_outage_duration = params['max_outage_duration']
        self.n_2 = params['n-2']
        # self.n_2 = 0

        # determines how many time_series timestamps relates to the reliability target hours to cover
        self.coverage_timesteps = int(np.round(self.outage_duration_coverage / self.dt))  # integral type for indexing
        self.critical_load = params['critical load'].copy()

        self.reliability_requirement = None
        self.contribution_perc_df = None
        self.outage_contribution_df = None
        self.ice_rating = 0  # this is the rating of all DERs (expect for the intermittent resources)

    def calculate_system_requirements(self, der_dict):
        """ Calculate the system requirements that must be meet regardless of what other value streams are active
        However these requirements do depend on the technology that are active in our analysis

        Args:
            der_dict (Dict): dictionary of the initialized DERs in our scenario

        """
        if 'ICE' in der_dict.keys():
            self.ice_rating = der_dict['ICE'].rated_power

        self.reliability_requirement = self.rolling_sum(self.critical_load.loc[:], self.coverage_timesteps) * self.dt

        if not self.post_facto_only:
            # add the power and energy constraints to ensure enough energy and power in the ESS for the next x hours
            # there will be 2 constraints: one for power, one for energy
            self.system_requirements = [Const.Constraint('ene_min', self.name, self.reliability_requirement)]
            # this should be the constraint that makes sure the next x hours have enough energy

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

    def objective_constraints(self, mask, load_sum, tot_variable_gen, generator_out_sum, net_ess_power, combined_rating):
        """Default build constraint list method. Used by services that do not have constraints.

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                    in the subs data set
            tot_variable_gen (Expression): the sum of the variable/intermittent generation sources
            load_sum (list, Expression): the sum of load within the system
            generator_out_sum (list, Expression): the sum of conventional generation within the system
            net_ess_power (list, Expression): the sum of the net power of all the ESS in the system. flow out into the grid is negative
            combined_rating (Dictionary): the combined rating of each DER class type

        Returns:
            A list of constraints
        """
        if not self.post_facto_only:
            if self.n_2:
                combined_rating -= self.ice_rating

            # We want the minimum power capability of our DER mix in the discharge direction to be the maximum net load (load - solar)
            # to ensure that our DER mix can cover peak net load during any outage in the year
            return [cvx.NonPos(cvx.max(self.critical_load.loc[mask].values - tot_variable_gen) - combined_rating)]

    def timeseries_report(self):
        """ Summaries the optimization results for this Value Stream.

        Returns: A timeseries dataframe with user-friendly column headers that summarize the results
            pertaining to this instance

        """
        report = pd.DataFrame(index=self.reliability_requirement.index)
        if not self.post_facto_only:
            report.loc[:, 'Total Outage Requirement (kWh)'] = self.reliability_requirement
        report.loc[:, 'Critical Load (kW)'] = self.critical_load
        return report

    def drill_down_reports(self, monthly_data, time_series_data, technology_summary, sizing_df):
        """ Calculates any service related dataframe that is reported to the user.

        Returns: dictionary of DataFrames of any reports that are value stream specific
            keys are the file name that the df will be saved with

        """
        df_dict = {}
        u_logger.info('Starting load coverage calculation. This may take a while.')
        df_dict['load_coverage_prob'] = self.load_coverage_probability(time_series_data, sizing_df, technology_summary)
        u_logger.info('Finished load coverage calculation.')
        # calculate RELIABILITY SUMMARY
        self.contribution_summary(technology_summary, time_series_data)
        df_dict['outage_energy_contributions'] = self.outage_contribution_df
        df_dict['reliability_summary'] = self.contribution_perc_df
        return df_dict

    def contribution_summary(self, technology_summary_df, results):
        """ Determines that contribution from each DER type in the event of an outage.
        Call IFF attribute POST_FACTO_ONLY is False

        Args:
            technology_summary_df (DataFrame): list of active technologies
            results (DataFrame): dataframe that holds all the results of the optimzation

        Returns: dataframe of der's outage contribution

        """
        outage_energy = self.reliability_requirement
        sum_outage_requirement = outage_energy.sum()  # sum of energy required to provide x hours of energy if outage occurred at every timestep

        percent_usage = {}
        contribution_arrays = {}

        pv_names = technology_summary_df.loc[technology_summary_df['Type'] == 'PV']
        if len(pv_names):
            agg_pv_max = pd.DataFrame(np.zeros(len(results)), index=results.index)
            for name in pv_names.index:

                agg_pv_max += results.loc[:, f'{name}: PV Maximum (kW)']
            # rolling sum of energy within a coverage_timestep window
            pv_outage_e = self.rolling_sum(agg_pv_max, self.coverage_timesteps) * self.dt
            # try to cover as much of the outage that can be with PV energy
            net_outage_energy = outage_energy - pv_outage_e
            # pv generation might have more energy than in the outage, so dont let energy go negative
            outage_energy = net_outage_energy.clip(lower=0)

            # remove any extra energy from PV contribution
            # over_gen = -net_outage_energy.clip(upper=0)
            # pv_outage_e = pv_outage_e - over_gen
            pv_outage_e += net_outage_energy.clip(upper=0)

            # record contribution
            percent_usage.update({'PV': np.sum(pv_outage_e) / sum_outage_requirement})
            contribution_arrays.update({'PV Outage Contribution (kWh)': pv_outage_e.values})

        ess_names = technology_summary_df.loc[technology_summary_df['Type'] is 'ESS']
        if len(ess_names):
            ess_outage = results.loc[:, 'Aggregated State of Energy (kWh)']
            # try to cover as much of the outage that can be with the ES
            net_outage_energy = outage_energy - ess_outage
            # ESS might have more energy than in the outage, so dont let energy go negative
            outage_energy = net_outage_energy.clip(lower=0)

            # remove any extra energy from ESS contribution
            ess_outage = ess_outage + net_outage_energy.clip(upper=0)

            # record contribution
            percent_usage.update({'Storage': np.sum(ess_outage) / sum_outage_requirement})
            contribution_arrays.update({'Storage Outage Contribution (kWh)': ess_outage.values})

        ice_names = technology_summary_df.loc[technology_summary_df['Type'] == 'ICE']
        if len(ice_names):
            # supplies what every energy that cannot be by pv and diesel
            # diesel_contribution is what ever is left
            percent_usage.update({'ICE': 1 - sum(percent_usage.keys())})
            contribution_arrays.update({'ICE Outage Contribution (kWh)': outage_energy.values})

        self.contribution_perc_df = pd.DataFrame(percent_usage, index=pd.Index(['Reliability contribution'])).T

        self.outage_contribution_df = pd.DataFrame(contribution_arrays, index=self.critical_load.index)

    def load_coverage_probability(self, results_df, size_df, technology_summary_df):
        """ Creates and returns a data frame with that reports the load coverage probability of outages that last from 0 to
        OUTAGE_LENGTH hours with the DER mix described in TECHNOLOGIES

        Args:
            results_df (DataFrame): the dataframe that consoidates all results
            size_df (DataFrame): the dataframe that describes the physical capabilities of the DERs
            technology_summary_df(DataFrame): maps DER type to user inputted name that indexes the size df

        Returns: DataFrame with 2 columns - 'Outage Length (hrs)' and 'Load Coverage Probability (%)'

        """
        start = time.time()

        # initialize a list to track the frequency of the results of the simulate_outage method
        frequency_simulate_outage = np.zeros(int(self.max_outage_duration / self.dt) + 1)

        # 1) simulate an outage that starts at every timestep
        # check to see if there is enough fuel generation to meet the load as offset by the amount of PV
        # generation you are confident will be delivered (usually 20% of PV forecast)
        reliability_check = self.critical_load.copy()
        demand_left = self.critical_load.copy()

        data_length = len(self.critical_load.index)

        # collect information required to call simulate_outage
        tech_specs = {}
        soc = None

        ess_names = technology_summary_df.loc[technology_summary_df['Type'] is 'ESS']
        if len(ess_names.index):
            ess_properties = [[size_df.loc[name, 'Charge Rating (kW)'],  # charge max
                              size_df.loc[name, 'Discharge Rating (kW)'],  # discharge max
                              size_df.loc[name, 'Round Trip Efficiency (%)'],  # rte
                              size_df.loc[name, 'Energy Rating (kWh)'] * size_df.loc[name, 'Lower Limit on SOC (%)'],  # operation SOE min
                              size_df.loc[name, 'Energy Rating (kWh)'] * size_df.loc[name, 'Upper Limit on SOC (%)']]   # 'operation SOE max'
                              for name in ess_names.index]
            ess_agg_prop = {
                'charge max': np.sum(ess_properties[0]),
                'discharge max': np.sum(ess_properties[1]),
                'rte list': ess_properties[2],
                'operation SOE min': np.sum(ess_properties[3]),
                'operation SOE max': np.sum(ess_properties[4])
            }
            tech_specs['ess_properties'] = ess_agg_prop
            # save the state of charge
            soc = results_df.loc[:, 'Aggregated State of Energy (kWh)'].values

        pv_names = technology_summary_df.loc[technology_summary_df['Type'] == 'PV']
        if len(pv_names.index):
            combined_pv_max = np.zeros(data_length)
            for name in pv_names.index:
                combined_pv_max += results_df.loc[:, f'{name}: PV Maximum (kW)']
            reliability_check -= self.nu * combined_pv_max
            demand_left -= combined_pv_max

        ice_names = technology_summary_df.loc[technology_summary_df['Type'] == 'ICE']
        num_ice = len(ice_names.index)
        if num_ice:
            combined_ice_rating = 0  # for multiple ICE
            if self.n_2:
                name = ice_names.index.loc[0]
                if num_ice == 1:
                    combined_ice_rating += np.max([size_df.loc[name, 'Quantity']-1, 0]) * size_df.loc[name, 'Power Capacity (kW)']
                else:
                    u_logger.error(f'{len(ice_names.index)} ice instances included, n-2 coverage probability algorithm assumes only 1')
                    return
            else:
                for name in ice_names:
                    combined_ice_rating += size_df.loc[name, 'Quantity'] * size_df.loc[name, 'Power Capacity (kW)']
            max_ice_power = np.repeat(combined_ice_rating, data_length)
            reliability_check -= max_ice_power
            demand_left -= max_ice_power

        end = time.time()
        u_logger.info(f'Critical Load Coverage Curve overhead time: {end - start}')
        # simulate outage starting on every timestep
        start = time.time()
        outage_init = 0
        while outage_init < len(self.critical_load):
            if soc is not None:
                tech_specs['init_soc'] = soc[outage_init]
            longest_outage = self.simulate_outage(reliability_check[outage_init:], demand_left[outage_init:], self.max_outage_duration, **tech_specs)
            # record value of foo in frequency count
            frequency_simulate_outage[int(longest_outage / self.dt)] += 1
            # start outage on next timestep
            outage_init += 1
        # 2) calculate probabilities
        load_coverage_prob = []
        length = self.dt
        while length <= self.max_outage_duration:
            scenarios_covered = frequency_simulate_outage[int(length / self.dt):].sum()
            total_possible_scenarios = len(self.critical_load) - (length / self.dt) + 1
            percentage = scenarios_covered / total_possible_scenarios
            load_coverage_prob.append(percentage)
            length += self.dt
        # 3) build DataFrame to return
        outage_lengths = list(np.arange(0, self.max_outage_duration + self.dt, self.dt))
        outage_coverage = {'Outage Length (hrs)': outage_lengths,
                           # '# of simulations where the outage lasts up to and including': frequency_simulate_outage,
                           'Load Coverage Probability (%)': [1] + load_coverage_prob}  # first index is prob of covering outage of 0 hours (P=100%)
        end = time.time()
        u_logger.info(f'Critical Load Coverage Curve calculation time: {end - start}')
        return pd.DataFrame(outage_coverage)

    def simulate_outage(self, reliability_check, demand_left, outage_left, ess_properties=None, init_soe=None):
        """ Simulate an outage that starts with lasting only1 hour and will either last as long as MAX_OUTAGE_LENGTH
        or the iteration loop hits the end of any of the array arguments.
        Updates and tracks the SOC throughout the outage

        Args:
            reliability_check (np.ndarray): the amount of load minus fuel generation and a percentage of PV generation
            demand_left (np.ndarray): the amount of load minus fuel generation and all of PV generation
            init_soe (float, None): the soc of the ESS (if included in analysis) at the beginning of time t
            outage_left (int): the length of outage yet to be simulated
            ess_properties (dict): dictionary that describes the physical properties of the ess in the analysis
                includes 'charge max', 'discharge max, 'operation SOE min', 'operation SOE max', 'rte'

        Returns: the length of the outage that starts at the beginning of the array that can be reliably covered

        """
        # base case: when to terminate recursion
        if outage_left == 0 or not len(reliability_check):
            return 0
        current_reliability_check = reliability_check[0]
        current_demand_left = demand_left[0]
        if 0 >= current_reliability_check:
            # check to see if there is space to storage energy in the ESS to save extra generation
            if ess_properties is not None and ess_properties['operation SOE max'] >= init_soe:
                # the amount we can charge based on its current SOC
                random_rte = ess_properties['rte'][random.randrange(0, len(ess_properties['rte'])-1)]
                charge_possible = (ess_properties['operation SOE max'] - init_soe) / (random_rte * self.dt)
                charge = min(charge_possible, -current_demand_left, ess_properties['charge max'])
                # update the state of charge of the ESS
                next_soe = init_soe + (charge * ess_properties['rte'] * self.dt)
            else:
                # there is no space to save the extra generation, so the ess will not do anything
                next_soe = init_soe
            # can reliably meet the outage in that timestep: jump to SIMULATE OUTAGE IN NEXT TIMESTEP
        else:
            # check that there is enough SOC in the ESS to satisfy worst case
            if ess_properties is not None and 0 >= (current_reliability_check * self.gamma) - init_soe:
                # so discharge to meet the load offset by all generation
                discharge_possible = (init_soe - ess_properties['operation SOE min']) / self.dt
                discharge = min(discharge_possible, current_demand_left, ess_properties['discharge max'])
                if discharge < current_demand_left:
                    # can't discharge enough to meet demand
                    return 0
                # update the state of charge of the ESS
                next_soe = init_soe - (discharge * self.dt)
                # we can reliably meet the outage in that timestep: jump to SIMULATE OUTAGE IN NEXT TIMESTEP
            else:
                # an outage cannot be reliably covered at this timestep, nor will it be covered beyond
                return 0
        # SIMULATE OUTAGE IN NEXT TIMESTEP
        return self.dt + self.simulate_outage(reliability_check[1:], demand_left[1:], outage_left - 1, ess_properties, next_soe)