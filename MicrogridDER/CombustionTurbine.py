"""
CT Sizing class

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
from MicrogridDER.RotatingGeneratorSizing import RotatingGeneratorSizing
import pandas as pd
import storagevet.Library as Lib
import numpy as np
from ErrorHandelling import *
from DERVETParams import ParamsDER


class CT(RotatingGeneratorSizing):
    """ An Combustion Turbine (CT) generator, with sizing optimization

    """

    def __init__(self, params):
        """ Initialize all technology with the following attributes.

        Args:
            params (dict): Dict of parameters for initialization
        """
        TellUser.debug(f"Initializing {__name__}")
        super().__init__(params)

        self.tag = 'CT'
        self.heat_rate = params['heat_rate']                    # BTU/kWh

        # time series inputs
        self.natural_gas_price = params['natural_gas_price']    # $/MillionBTU

    def grow_drop_data(self, years, frequency, load_growth):
        """ Adds data by growing the given data OR drops any extra data that might have slipped in.
        Update variable that hold timeseries data after adding growth data. These method should be called after
        add_growth_data and before the optimization is run.

        Args:
            years (List): list of years for which analysis will occur on
            frequency (str): period frequency of the timeseries data
            load_growth (float): percent/ decimal value of the growth rate of loads in this simulation

        """
        self.natural_gas_price = Lib.fill_extra_data(self.natural_gas_price, years, 0, frequency)  # TODO: change growth rate of fuel prices (user input?)
        self.natural_gas_price = Lib.drop_extra_data(self.natural_gas_price, years)

    def objective_function(self, mask, annuity_scalar=1):
        costs = super().objective_function(mask, annuity_scalar)

        total_out = self.variables_dict['elec'] + self.variables_dict['udis']

        # natural gas fuel costs in $/kW
        costs[self.name + 'FuelCosts'] = cvx.sum(cvx.multiply(total_out, self.heat_rate *
                                                              (self.natural_gas_price.loc[mask] * 1e6) * self.dt * annuity_scalar))

        return costs

    def timeseries_report(self):
        """ Summaries the optimization results for this DER.

        Returns: A timeseries dataframe with user-friendly column headers that summarize the results
            pertaining to this instance

        """
        tech_id = self.unique_tech_id()
        results = super().timeseries_report()
        results[tech_id + ' Natural Gas Price ($/MillionBTU)'] = self.natural_gas_price
        return results

    def update_price_signals(self, id_str, monthly_data=None, time_series_data=None):
        """ Updates attributes related to price signals with new price signals that are saved in
        the arguments of the method. Only updates the price signals that exist, and does not require all
        price signals needed for this service.

        Args:
            monthly_data (DataFrame): monthly data after pre-processing
            time_series_data (DataFrame): time series data after pre-processing

        """
        if monthly_data is not None:
            freq = self.natural_gas_price.freq
            try:
                self.natural_gas_price = ParamsDER.monthly_to_timeseries(freq, monthly_data.loc[:, [f"Natural Gas Price ($/MillionBTU)/{id_str}"]]),
            except KeyError:
                try:
                    self.natural_gas_price = ParamsDER.monthly_to_timeseries(freq, monthly_data.loc[:, [f"Natural Gas Price ($/MillionBTU)"]]),
                except KeyError:
                    pass

    def proforma_report(self, opt_years, results):
        tech_id = self.unique_tech_id()
        pro_forma = super().proforma_report(opt_years, results)
        fuel_col_name = tech_id + ' Natural Gas Costs'

        elec = self.variables_df['elec']

        for year in opt_years:
            elec_sub = elec.loc[elec.index.year == year]

            # add natural gas fuel costs in $/MillionBTU
            pro_forma.loc[pd.Period(year=year, freq='y'), fuel_col_name] = -np.sum(self.heat_rate * self.natural_gas_price * self.dt * elec_sub)

        return pro_forma
