"""
FlexibleRamping.py

This Python class contains methods and attributes specific for service analysis within StorageVet.
"""

__author__ = 'Miles Evans and Evan Giarta'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani', 'Thien Nguyen']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Evan Giarta', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'egiarta@epri.com', 'mevans@epri.com']
__version__ = '2.1.1.1'

from ValueStreams.ValueStream import ValueStream
import storagevet
import cvxpy as cvx
import numpy as np
import pandas as pd
import logging

try:
    import Constraint as Const
    import Library as Lib
except ModuleNotFoundError:
    import storagevet.Constraint as Const
    import storagevet.Library as Lib

u_logger = logging.getLogger('User')
e_logger = logging.getLogger('Error')


class FlexibleRamping(storagevet.ValueStream):
    """ Flexible Ramping market service, inheriting ValueStream class.

    """

    def __init__(self, params, tech, dt):
        """
        Args:
            params (dict): input parameters
            tech (Technology): technology object
            dt (float): optimization time-step (hours)

        """

        ValueStream.__init__(self, tech, 'FlexR', dt)

        self.combined_market = params['CombinedMarket']  # boolean: true if ramp up is equal to ramp down
        self.price_growth = params['growth']
        self.ku = params['ku']
        self.kd = params['kd']

        # forecasted movement value from time-series input
        self.ramp_load = params['forecasted_movement']
        self.rampup_load = pd.Series(index=self.ramp_load.index)
        self.rampdown_load = pd.Series(index=self.ramp_load.index)
        # split ramp_load into rampup_load and rampdown_load as rampup is positive load and rampdown is negative load
        for index, value in self.ramp_load.items():
            if value >= 0:
                self.rampup_load[index] = value
                self.rampdown_load[index] = 0
            else:
                self.rampup_load[index] = 0
                self.rampdown_load[index] = value

        self.price = params['energy_price']  # TODO: require RT market price instead of DA price
        self.flexr_up_price = params['flexr_up_price']
        self.flexr_do_price = params['flexr_do_price']

        # max/min resource uncertainties in upward/downward direction
        self.variable_names = {'flexr_up_c', 'flexr_do_c', 'flexr_up_d', 'flexr_do_d'}
        self.variables = pd.DataFrame(columns=self.variable_names)

        self.dt = dt
        if self.dt != 0.25 or self.dt != (5/60):
            e_logger.warning("WARNING: using Flexible Ramping Service and energy-dispatch interval is not 5 or 15 min.")
            u_logger.warning("WARNING: using Flexible Ramping Service and energy-dispatch interval is not 5 or 15 min.")

    @staticmethod
    def add_vars(size):
        """ Adds optimization variables to dictionary

        Variables added:
            flexr_up_c (Variable): A cvxpy variable for flexible ramping capacity to increase charging power
            flexr_do_c (Variable): A cvxpy variable for flexible ramping capacity to decrease charging power
            flexr_up_d (Variable): A cvxpy variable for flexible ramping capacity to increase discharging power
            flexr_do_d (Variable): A cvxpy variable for flexible ramping capacity to decrease discharging power

        Args:
            size (Int): Length of optimization variables to create

        Returns:
            Dictionary of optimization variables
        """
        return {'flexr_up_c': cvx.Variable(shape=size, name='flexr_up_c'),
                'flexr_do_c': cvx.Variable(shape=size, name='flexr_do_c'),
                'flexr_up_d': cvx.Variable(shape=size, name='flexr_up_d'),
                'flexr_do_d': cvx.Variable(shape=size, name='flexr_do_d')}

    def objective_function(self, variables, mask, load, generation, annuity_scalar=1):
        """ Generates the full objective function, including the optimization variables.

        Args:
            variables (Dict): dictionary of variables being optimized
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set
            load (list, Expression): the sum of load within the system
            generation (list, Expression): the sum of generation within the system
            annuity_scalar (float): a scalar value to be multiplied by any yearly cost or benefit that helps capture the cost/benefit over
                        the entire project lifetime (only to be set iff sizing)

        Returns:
            The portion of the objective function that it affects. This can be passed into the cvxpy solver. Returns costs - benefits

        """
        size = sum(mask)

        # TODO: might check for price settlement on forecasted_movement power?

        masked_up_price = cvx.Parameter(size, value=self.flexr_up_price.loc[mask].values, name='flexr_up_price')
        masked_do_price = cvx.Parameter(size, value=self.flexr_do_price.loc[mask].values, name='flexr_do_price')
        masked_price = cvx.Parameter(size, value=self.price.loc[mask].values, name='price')

        rampup_charge_payment = cvx.sum(variables['flexr_up_c'] * - masked_up_price) * annuity_scalar
        rampup_charge_settlement = cvx.sum(variables['flexr_up_c'] * - masked_price) * self.dt * self.ku * annuity_scalar

        rampup_dis_payment = cvx.sum(variables['flexr_up_d'] * - masked_up_price) * annuity_scalar
        rampup_dis_settlement = cvx.sum(variables['flexr_up_d'] * - masked_price) * self.dt * self.ku * annuity_scalar

        rampdown_charge_payment = cvx.sum(variables['flexr_do_c'] * - masked_do_price) * annuity_scalar
        rampdown_charge_settlement = cvx.sum(variables['flexr_do_c'] * masked_price) * self.dt * self.kd * annuity_scalar

        rampdown_dis_payment = cvx.sum(variables['flexr_do_d'] * - masked_do_price) * annuity_scalar
        rampdown_dis_settlement = cvx.sum(variables['flexr_do_d'] * masked_price) * self.dt * self.kd * annuity_scalar

        return {'rampup_payment': rampup_charge_payment + rampup_dis_payment,
                'rampdown_payment': rampdown_charge_payment + rampdown_dis_payment,
                'flexR_energy_settlement': rampup_dis_settlement + rampdown_dis_settlement +
                                           rampup_charge_settlement + rampdown_charge_settlement}

    def objective_constraints(self, variables, mask, load, generation, reservations=None):
        """Default build constraint list method. Used by services that do not have constraints.

        Args:
            variables (Dict): dictionary of variables being optimized
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set
            load (list, Expression): the sum of load within the system
            generation (list, Expression): the sum of generation within the system for the subset of time
                being optimized
            reservations (Dict): power reservations from dispatch services

        Returns:
            constraint_list (list): list of constraints

        """
        constraint_list = []
        constraint_list += [cvx.NonPos(-variables['flexr_up_c'])]
        constraint_list += [cvx.NonPos(-variables['flexr_do_c'])]
        constraint_list += [cvx.NonPos(-variables['flexr_up_d'])]
        constraint_list += [cvx.NonPos(-variables['flexr_do_d'])]

        if self.combined_market:
            constraint_list += [cvx.Zero(variables['flexr_do_d'] + variables['flexr_do_c']
                                         - variables['flexr_up_d'] - variables['flexr_up_c'])]

        return constraint_list

    def power_ene_reservations(self, opt_vars, mask):
        """ Determines power and energy reservations required at the end of each time-step for the service to be provided.
        Additionally keeps track of the reservations per optimization window so the values maybe accessed later.

        Args:
            opt_vars (Dict): dictionary of variables being optimized
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set

        Returns:
            A power reservation and a energy reservation array for the optimization window--
            C_max, C_min, D_max, D_min, E_upper, E, and E_lower (in that order)
        """
        # Note: self.storage had Load Technologies included when I wrote this, so I need to specify Storage
        #  for the dictionary, self.storage.rte gave Key Errors
        eta = self.storage['Storage'].rte

        # calculate reservations
        c_max = opt_vars['flexr_do_c']
        c_min = opt_vars['flexr_up_c']
        d_min = opt_vars['flexr_do_d']
        d_max = opt_vars['flexr_up_d']

        # worst case for upper level of energy throughput
        e_upper = self.kd * self.dt * opt_vars['flexr_do_d'] + self.kd * self.dt * opt_vars['flexr_do_c'] * eta - \
                  self.ku * self.dt * opt_vars['flexr_up_d'] - self.ku * self.dt * opt_vars['flexr_up_c'] * eta
        # energy throughput is result from combination of ene_throughput for
        # (+ down_discharge + down_charge - up_discharge - up_charge) + forecast_movement_power (ramp down/up values)
        e = cvx.multiply(self.dt, opt_vars['flexr_do_d']) + \
            cvx.multiply(self.dt * eta, opt_vars['flexr_do_c']) - \
            cvx.multiply(self.dt, opt_vars['flexr_up_d']) - \
            cvx.multiply(self.dt * eta, opt_vars['flexr_up_c']) + \
            self.dt * self.rampdown_load[mask].values + self.dt * self.rampup_load[mask].values
        # worst case for lower level of energy throughput
        e_lower = self.kd * self.dt * opt_vars['flexr_do_d'] + self.kd * self.dt * opt_vars['flexr_do_c'] * eta - \
                  self.ku * self.dt * opt_vars['flexr_up_d'] - self.ku * self.dt * opt_vars['flexr_up_c'] * eta

        # save reservation for optmization window
        self.e.append(e)
        self.e_lower.append(e_lower)
        self.e_upper.append(e_upper)
        self.c_max.append(c_max)
        self.c_min.append(c_min)
        self.d_max.append(d_max)
        self.d_min.append(d_min)
        return [c_max, c_min, d_max, d_min], [e_upper, e, e_lower]

    def estimate_year_data(self, years, frequency):
        """ Update variable that hold timeseries data after adding growth data. These method should be called after
        add_growth_data and before the optimization is run.

        Args:
            years (List): list of years for which analysis will occur on
            frequency (str): period frequency of the time-series data

        """
        data_year = self.price.index.year.unique()
        no_data_year = {pd.Period(year) for year in years} - {pd.Period(year) for year in data_year}  # which years do we not have data for

        if len(no_data_year) > 0:
            for yr in no_data_year:
                source_year = pd.Period(max(data_year))

                source_data = self.price[self.price.index.year == source_year.year]  # use source year data
                new_data = Lib.apply_growth(source_data, self.price_growth, source_year, yr, frequency)
                self.price = pd.concat([self.price, new_data], sort=True)  # add to existing

                source_data = self.flexr_up_price[self.flexr_up_price.index.year == source_year.year]  # use source year data
                new_data = Lib.apply_growth(source_data, self.price_growth, source_year, yr, frequency)
                self.flexr_up_price = pd.concat([self.flexr_up_price, new_data], sort=True)  # add to existing

                source_data = self.flexr_do_price[self.flexr_do_price.index.year == source_year.year]  # use source year data
                new_data = Lib.apply_growth(source_data, self.price_growth, source_year, yr, frequency)
                self.flexr_do_price = pd.concat([self.flexr_do_price, new_data], sort=True)  # add to existing

    def timeseries_report(self):
        """ Summaries the optimization results for this Value Stream.

        Returns: A timeseries dataframe with user-friendly column headers that summarize the results
            pertaining to this instance

        """
        report = pd.DataFrame(index=self.price.index)
        report.loc[:, "FlexR Energy Throughput with Forecast Movement (kWh)"] = self.ene_results['ene']
        report.loc[:, "FlexR Energy Throughput Up (Charging) (kWh)"] = self.ku * self.dt * self.storage.rte * self.variables['flexr_up_c']
        report.loc[:, "FlexR Energy Throughput Up (Discharging) (kWh)"] = self.ku * self.dt * self.variables['flexr_up_d']
        report.loc[:, "FlexR Energy Throughput Down (Charging) (kWh)"] = self.kd * self.dt * self.storage.rte * self.variables['flexr_do_c']
        report.loc[:, "FlexR Energy Throughput Down (Discharging) (kWh)"] = self.kd * self.dt * self.variables['flexr_do_d']
        report.loc[:, "FlexR Energy Settlement Price Signal ($/kWh)"] = self.price
        report.loc[:, 'FlexR Up (Charging) (kW)'] = self.variables['flexr_up_c']
        report.loc[:, 'FlexR Up (Discharging) (kW)'] = self.variables['flexr_up_d']
        report.loc[:, 'FlexR Up Price Signal ($/kW)'] = self.flexr_up_price
        report.loc[:, 'FlexR Down (Charging) (kW)'] = self.variables['flexr_do_c']
        report.loc[:, 'FlexR Down (Discharging) (kW)'] = self.variables['flexr_do_d']
        report.loc[:, 'FlexR Down Price Signal ($/kW)'] = self.flexr_do_price

        return report

    def proforma_report(self, opt_years, results):
        """ Calculates the proforma that corresponds to participation in this value stream

        Args:
            opt_years (list): list of years the optimization problem ran for
            results (DataFrame): DataFrame with all the optimization variable solutions

        Returns: A tuple of a DateFrame (of with each year in opt_year as the index and the corresponding
        value this stream provided), a list (of columns that remain zero), and a list (of columns that
        retain a constant value over the entire project horizon).

            Creates a dataframe with only the years that we have data for. Since we do not label the column,
            it defaults to number the columns with a RangeIndex (starting at 0) therefore, the following
            DataFrame has only one column, labeled by the int 0

        """
        proforma, _, _ = ValueStream.proforma_report(self, opt_years, results)

        flexr_up = results.loc[:, 'FlexR Up (Charging) (kW)'] + results.loc[:, 'FlexR Up (Discharging) (kW)']
        flexr_down = results.loc[:, 'FlexR Down (Charging) (kW)'] + results.loc[:, 'FlexR Down (Discharging) (kW)']

        energy_throughput = - results.loc[:, "FlexR Energy Throughput Down (Discharging) (kWh)"] \
                            - results.loc[:, "FlexR Energy Throughput Down (Charging) (kWh)"] / self.storage.rte \
                            + results.loc[:, "FlexR Energy Throughput Up (Discharging) (kWh)"] \
                            + results.loc[:, "FlexR Energy Throughput Up (Charging) (kWh)"] / self.storage.rte
        energy_through_prof = np.multiply(energy_throughput,
                                          results.loc[:, "FlexR Energy Settlement Price Signal ($/kWh)"])

        flexr_up_prof = np.multiply(flexr_up, self.flexr_up_price)
        flexr_down_prof = np.multiply(flexr_down, self.flexr_do_price)

        flexr_results = pd.DataFrame({'Energy': energy_through_prof,
                                    'FlexR Up': flexr_up_prof,
                                    'FlexR Down': flexr_down_prof}, index=results.index)
        for year in opt_years:
            year_monthly = flexr_results[flexr_results.index.year == year]
            proforma.loc[pd.Period(year=year, freq='y'), 'FlexR Energy Throughput'] = year_monthly['Energy'].sum()
            proforma.loc[pd.Period(year=year, freq='y'), 'FlexR Up'] = year_monthly['FlexR Up'].sum()
            proforma.loc[pd.Period(year=year, freq='y'), 'FlexR Down'] = year_monthly['FlexR Down'].sum()

        return proforma, None, None

    def update_price_signals(self, monthly_data, time_series_data):
        """ Updates attributes related to price signals with new price signals that are saved in
        the arguments of the method. Only updates the price signals that exist, and does not require all
        price signals needed for this service.

        Args:
            monthly_data (DataFrame): monthly data after pre-processing
            time_series_data (DataFrame): time series data after pre-processing

        """
        if self.combined_market:
            try:
                fr_price = time_series_data.loc[:, 'LF Price ($/kW)']
            except KeyError:
                pass
            else:
                self.price_lf_up = np.divide(fr_price, 2)
                self.price_lf_do = np.divide(fr_price, 2)

            try:
                self.price = time_series_data.loc[:, 'DA Price ($/kWh)']
            except KeyError:
                pass
        else:
            try:
                self.price_lf_do = time_series_data.loc[:, 'LF Down Price ($/kW)']
            except KeyError:
                pass

            try:
                self.price_lf_up = time_series_data.loc[:, 'LF Up Price ($/kW)']
            except KeyError:
                pass

            try:
                self.price = time_series_data.loc[:, 'DA Price ($/kWh)']
            except KeyError:
                pass
