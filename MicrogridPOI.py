"""
MicrogridPOI.py

"""

__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani',
               'Micah Botkin-Levy', "Thien Nguyen", 'Yekta Yazar']
__license__ = 'EPRI'
__maintainer__ = ['Evan Giarta', 'Miles Evans']
__email__ = ['egiarta@epri.com', 'mevans@epri.com']


import pandas as pd
from storagevet.POI import POI
import cvxpy as cvx
from ErrorHandelling import *
import numpy as np


class MicrogridPOI(POI):
    """
        This class holds the load data for the case described by the user defined model parameter. It will also
        impose any constraints that should be opposed at the microgrid's POI.
    """

    def __init__(self, params, technology_inputs_map, technology_class_map):
        super().__init__(params, technology_inputs_map, technology_class_map)
        self.is_sizing_optimization = self.check_if_sizing_ders()
        if self.is_sizing_optimization:
            self.error_checks_on_sizing()

        # add thermal site load time series
        # NOTE: these loads can come from different technologies
        self.site_cooling_load = None
        self.site_steam_load = None
        self.site_hotwater_load = None
        for der in self.active_ders:
            try:
                self.site_steam_load = der.site_steam_load
            except AttributeError:
                pass
            try:
                self.site_hotwater_load = der.site_hotwater_load
            except AttributeError:
                pass
            try:
                self.site_cooling_load = der.site_cooling_load
            except AttributeError:
                pass

    def check_if_sizing_ders(self):
        """ This method will iterate through the initialized DER instances and return a logical OR of all of their
        'being_sized' methods.

        Returns: True if ANY DER is getting sized

        """
        for der_instance in self.der_list:
            try:
                solve_for_size = der_instance.being_sized()
            except AttributeError:
                solve_for_size = False
            if solve_for_size:
                return True
        return False

    def grab_active_ders(self, indx):
        """ drops DER that are not considered active in the optimization window's horizon

        """
        year = indx.year[0]
        active_ders = [der_instance for der_instance in self.der_list if der_instance.operational(year)]
        self.active_ders = active_ders

    def error_checks_on_sizing(self):
        # perform error checks on DERs that are being sized
        # collect errors and raise if any were found
        errors_found = [1 if der.sizing_error() else 0 for der in self.der_list]
        if sum(errors_found):
            raise ParameterError(f'Sizing of DERs has an error. Please check error log.')

    def is_any_sizable_der_missing_power_max(self):
        return bool(sum([1 if not der_inst.max_power_defined else 0 for der_inst in self.der_list]))

    def is_dcp_error(self, is_binary_formulation):
        """ If trying to sizing power of batteries (or other DERs) AND using the binary formulation (of ESS)
        our linear model will not be linear anymore

        Args:
            is_binary_formulation (bool):

        Returns: a boolean

        """
        solve_for_size = False
        for der_instance in self.der_list:
            if der_instance.tag == 'Battery':
                solve_for_size = solve_for_size or (der_instance.is_power_sizing() and is_binary_formulation)
        return solve_for_size

    def sizing_summary(self):
        rows = list(map(lambda der: der.sizing_summary(), self.der_list))
        sizing_df = pd.DataFrame(rows)
        sizing_df.set_index('DER')
        return sizing_df

    def merge_reports(self, index):
        """ Collects and merges the optimization results for all DERs into
        Builds extends StorageVET's method to take into account types of technologies added by DERVET

        Returns: A timeseries dataframe with user-friendly column headers that summarize the results
            pertaining to this instance

        """
        results = pd.DataFrame(index=index)
        monthly_data = pd.DataFrame()

        # initialize all the data columns that will ALWAYS be present in our results
        results.loc[:, 'Total Original Load (kW)'] = 0
        results.loc[:, 'Total Load (kW)'] = 0
        results.loc[:, 'Total Generation (kW)'] = 0
        results.loc[:, 'Total Storage Power (kW)'] = 0
        results.loc[:, 'Aggregated State of Energy (kWh)'] = 0

        for der_instance in self.der_list:
            report_df = der_instance.timeseries_report()
            results = pd.concat([report_df, results], axis=1)
            if der_instance.technology_type in ['Generator', 'Intermittent Resource']:
                results.loc[:, 'Total Generation (kW)'] += results[f'{der_instance.unique_tech_id()} Electric Generation (kW)']
            if der_instance.technology_type == 'Energy Storage System':
                results.loc[:, 'Total Storage Power (kW)'] += results[f'{der_instance.unique_tech_id()} Power (kW)']
                results.loc[:, 'Aggregated State of Energy (kWh)'] += results[f'{der_instance.unique_tech_id()} State of Energy (kWh)']
            if der_instance.technology_type == 'Load':
                results.loc[:, 'Total Original Load (kW)'] += results[f'{der_instance.unique_tech_id()} Original Load (kW)']
                if der_instance.tag == "ControllableLoad":
                    results.loc[:, 'Total Load (kW)'] += results[f'{der_instance.unique_tech_id()} Load (kW)']
                else:
                    results.loc[:, 'Total Load (kW)'] += results[f'{der_instance.unique_tech_id()} Original Load (kW)']
            if der_instance.technology_type == 'Electric Vehicle':
                results.loc[:, 'Total Load (kW)'] += results[f'{der_instance.unique_tech_id()} Charge (kW)']
                if der_instance.tag == 'ElectricVehicle1':
                    results.loc[:, 'Aggregated State of Energy (kWh)'] += results[f'{der_instance.unique_tech_id()} State of Energy (kWh)']
            report = der_instance.monthly_report()
            monthly_data = pd.concat([monthly_data, report], axis=1, sort=False)
            # assumes the orginal net load only does not contain the Storage system

            # net load is the load see at the POI
            results.loc[:, 'Net Load (kW)'] = results.loc[:, 'Total Load (kW)'] - results.loc[:, 'Total Generation (kW)'] - results.loc[:, 'Total Storage Power (kW)']
        return results, monthly_data

    def get_state_of_system(self, mask):
        """ POI method to measure the state of POI depending on available types of DERs. used in SET_UP_OPTIMIZATION
        Extends StorageVET's method to take into account types of technologies added by DERVET, and thermal recovery

        Args:
            mask (DataFrame): DataFrame of booleans used, the same length as time_series. The value is true if the
                        corresponding column in time_series is included in the data to be optimized.

        Returns:
            aggregation of loads
            aggregation of generation from variable resources
            aggregation of generation from other sources
            total net power from ESSs
            total state of energy stored in the system
            aggregation of all the power flows into the POI
            aggregation of all the power flows out if the POI

            aggregation of steam thermal heating power (heat recovered)
            aggregation of hotwater thermal heating power (heat recovered)
            aggregation of thermal cooling power (cold recovered)
        """
        # get values from storagevet/poi method
        load_sum, var_gen_sum, gen_sum, tot_net_ess, total_soe, agg_power_flows_in, agg_power_flows_out, agg_steam_heating_power, agg_hotwater_heating_power, agg_thermal_cooling_power = super().get_state_of_system(mask)

        # dervet-specific
        for der_instance in self.active_ders:
            # add to aggregate values for dervet-specific technology-types
            if der_instance.technology_type == 'Electric Vehicle':
                load_sum += der_instance.get_charge(mask)
                # total_soe += der_instance.get_state_of_energy(mask)

            # thermal power recovered: hot (steam/hotwater) and cold
            if der_instance.is_hot:
                if self.site_steam_load is None and self.site_hotwater_load is None:
                    TellUser.warning(f'A heat source technology is active ({der_instance.unique_tech_id()}), but you have set the scenario parameter incl_thermal_load to False. Any thermal load will be ignored.')
                else:
                    if self.site_steam_load is not None:
                      TellUser.debug(f'adding heat (steam) recovered from this DER: {der_instance.unique_tech_id()}')
                      agg_steam_heating_power += der_instance.get_steam_recovered(mask)
                    if self.site_hotwater_load is not None:
                      TellUser.debug(f'adding heat (hotwater) recovered from this DER: {der_instance.unique_tech_id()}')
                      agg_hotwater_heating_power += der_instance.get_hotwater_recovered(mask)
            if der_instance.is_cold:
                if self.site_cooling_load is None:
                    TellUser.warning(f'A cold source technology is active ({der_instance.unique_tech_id()}), but you have set the scenario parameter incl_thermal_load to False. Any thermal load will be ignored.')
                else:
                    TellUser.debug(f'adding cold recovered from this DER: {der_instance.unique_tech_id()}')
                    agg_thermal_cooling_power += der_instance.get_cold_recovered(mask)

        return load_sum, var_gen_sum, gen_sum, tot_net_ess, total_soe, agg_power_flows_in, agg_power_flows_out, agg_steam_heating_power, agg_hotwater_heating_power, agg_thermal_cooling_power

    def optimization_problem(self, mask, power_in, power_out, steam_in, hotwater_in, cold_in, ignore_der_costs, annuity_scalar=1):
        """ Builds the master POI constraint list for the subset of time series data being optimized.
            Due to VS power reservations, control constraints, import/export constraints, and energy throughput requirements
            Builds onto storagevet method to add thermal balance constraints for dervet

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set
            power_in (cvx.Expression):
            power_out (cvx.Expression):
            steam_in (cvx.Expression):
            hotwater_in (cvx.Expression):
            cold_in (cvx.Expression):
            annuity_scalar (float): a scalar value to be multiplied by any yearly cost or benefit that helps capture
                the cost/benefit over the entire project lifetime (only to be set iff sizing)
            ignore_der_costs (bool): flag to indicate if we do not want to consider to economics of operating the DERs in our optimization
                (this flag will never be TRUE if the user indicated the desire to size the DER mix)

        Returns:
            A dictionary with the portion of the objective function that it affects, labeled by the expression's key.
            A list of constraints being set by the POI: power reservations, control constraints requirements,
                max import, max export, etc.
        """
        obj_expression, constraint_list = super().optimization_problem(mask, power_in, power_out, steam_in, hotwater_in, cold_in, ignore_der_costs, annuity_scalar=1)

        # thermal power balance constraints
        if self.site_steam_load is not None:
            if steam_in.variables():
                TellUser.debug('adding steam thermal power balance constraint')
                constraint_list += [cvx.NonPos(-1 * steam_in + self.site_steam_load)]
        if self.site_hotwater_load is not None:
            if hotwater_in.variables():
                TellUser.debug('adding hot water thermal power balance constraint')
                constraint_list += [cvx.NonPos(-1 * hotwater_in + self.site_hotwater_load)]
        if self.site_cooling_load is not None:
            if cold_in.variables():
                TellUser.debug('adding thermal cooling power balance constraint')
                constraint_list += [cvx.NonPos(-1 * cold_in + self.site_cooling_load)]

        return obj_expression, constraint_list
