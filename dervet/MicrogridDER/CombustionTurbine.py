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
CT Sizing class

This Python class contains methods and attributes specific for technology analysis within StorageVet.
"""
import cvxpy as cvx
from dervet.MicrogridDER.RotatingGeneratorSizing import RotatingGeneratorSizing
import pandas as pd
import storagevet.Library as Lib
import numpy as np
from storagevet.ErrorHandling import *
from dervet.DERVETParams import ParamsDER


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
        self.natural_gas_price = Lib.fill_extra_data(self.natural_gas_price, years, 0, frequency)
        # TODO: change growth rate of fuel prices (user input?)
        self.natural_gas_price = Lib.drop_extra_data(self.natural_gas_price, years)

    def objective_function(self, mask, annuity_scalar=1):
        costs = super().objective_function(mask, annuity_scalar)

        total_out = self.variables_dict['elec'] + self.variables_dict['udis']

        # natural gas fuel costs in $/kW
        costs[self.name + ' naturalgas_fuel_cost'] = cvx.sum(cvx.multiply(total_out, self.heat_rate *
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
        tech_id = self.unique_tech_id()
        fuel_col_name = tech_id + ' Natural Gas Costs'

        elec = self.variables_df['elec']
        analysis_years = self.variables_df.index.year.unique()
        fuel_costs_df = pd.DataFrame()
        for year in analysis_years:
            elec_sub = elec.loc[elec.index.year == year]
            # add diesel fuel costs in $/kW
            fuel_costs_df.loc[pd.Period(year=year, freq='y'), fuel_col_name] = -np.sum(self.heat_rate * self.natural_gas_price * self.dt * elec_sub)

        # fill forward
        fuel_costs_df = fill_forward_func(fuel_costs_df, None)
        # apply inflation rates
        # fuel_costs_df = apply_inflation_rate_func(fuel_costs_df, None, min(analysis_years))
        # append will super class's proforma
        pro_forma = pd.concat([pro_forma, fuel_costs_df], axis=1)

        return pro_forma
