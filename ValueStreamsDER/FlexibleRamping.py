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

        # forecasted movement value from time-series input
        self.ramp_load = params['forecasted_movement']
        self.rampup_load = pd.Series(index=self.ramp_load.index)
        self.rampdown_load = pd.Series(index=self.ramp_load.index)
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

        # TODO: need to be clear about getting paid for Ramping Up/Down services
        #  as well as interaction between Forecast Movement (its definition?) and Ramping Up/Down reservation capabilities

        masked_up_price = cvx.Parameter(size, value=self.flexr_up_price.loc[mask].values, name='flexr_up_price')
        masked_do_price = cvx.Parameter(size, value=self.flexr_do_price.loc[mask].values, name='flexr_do_price')
        masked_price = cvx.Parameter(size, value=self.price.loc[mask].values, name='price')

        rampup_charge_payment = cvx.sum(variables['flexr_up_c'] * - masked_up_price) * annuity_scalar
        rampup_charge_settlement = cvx.sum(variables['flexr_up_c'] * - masked_price) * self.dt * self.kru_avg * annuity_scalar

        rampup_dis_payment = cvx.sum(variables['regu_d'] * -p_regu) * annuity_scalar
        rampup_dis_settlement = cvx.sum(variables['regu_d'] * -p_ene) * self.dt * self.kru_avg * annuity_scalar

        rampdown_charge_payment = cvx.sum(variables['regd_c'] * -p_regd) * annuity_scalar
        rampdown_charge_settlement = cvx.sum(variables['regd_c'] * p_ene) * self.dt * self.krd_avg * annuity_scalar

        rampdown_dis_payment = cvx.sum(variables['regd_d'] * -p_regd) * annuity_scalar
        rampdown_dis_settlement = cvx.sum(variables['regd_d'] * p_ene) * self.dt * self.krd_avg * annuity_scalar

        return {'rampup_payment': rampup_charge_payment + rampup_dis_payment,
                'rampdown_payment': rampdown_charge_payment + rampdown_dis_payment,
                'flexR_energy_settlement': rampup_dis_settlement + rampdown_dis_settlement + rampup_charge_settlement + rampdown_charge_settlement}

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