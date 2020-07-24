"""
CT: (Combustion Turbine) or gas turbine
    - natural-gas fuel prices from monthly CSV

"""

__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani', 'Micah Botkin-Levy', 'Yekta Yazar']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Evan Giarta', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'egiarta@epri.com', 'mevans@epri.com']
__version__ = '2.1.1.1'

import cvxpy as cvx
import numpy as np
import pandas as pd
from .RotatingGenerator import RotatingGenerator


class CT(RotatingGenerator):
    """ CT Technology

    """

    def __init__(self, params):
        """ Initialize all technology with the following attributes.

        Args:
            params (dict): Dict of parameters for initialization
        """

        # create generic technology object
        super().__init__('CT', params)

        self.heat_rate = params['heat_rate']                    # BTU/kWh
        self.natural_gas_price = params['natural_gas_price']    # $/MillionBTU

    def objective_function(self, mask, annuity_scalar=1):
        """ Generates the objective function related to a technology. Default includes O&M which can be 0

        Args:
            mask (Series): Series of booleans used, the same length as case.power_kw
            annuity_scalar (float): a scalar value to be multiplied by any yearly cost or benefit that helps capture the cost/benefit over
                        the entire project lifetime (only to be set iff sizing)

        Returns:
            self.costs (Dict): Dict of objective costs
        """
        costs = super().objective_function(mask, annuity_scalar)

        total_out = self.variables_dict['elec'] + self.variables_dict['udis']

        # natural gas fuel costs in $/kW
        costs[self.name + ' naturalgas_fuel'] = cvx.sum(cvx.multiply(total_out,
                self.heat_rate * (self.natural_gas_price.loc[mask] * 1e6) * self.dt * annuity_scalar))

        return costs

    def proforma_report(self, opt_years, results):
        """ Calculates the proforma that corresponds to participation in this value stream

        Args:
            opt_years (list): list of years the optimization problem ran for
            results (DataFrame): DataFrame with all the optimization variable solutions

        Returns: A DateFrame of with each year in opt_year as the index and
            the corresponding value this stream provided.

            Creates a dataframe with only the years that we have data for. Since we do not label the column,
            it defaults to number the columns with a RangeIndex (starting at 0) therefore, the following
            DataFrame has only one column, labeled by the int 0

        """
        tech_id = self.unique_tech_id()
        pro_forma = super().proforma_report(opt_years, results)
        fuel_col_name = tech_id + ' Natural Gas Costs'

        elec = self.variables_df['elec']

        for year in opt_years:
            elec_sub = elec.loc[elec.index.year == year]

            # add natural gas fuel costs in $/MillionBTU
            pro_forma.loc[pd.Period(year=year, freq='y'), fuel_col_name] = -np.sum(self.heat_rate
                    * self.natural_gas_price * self.dt * elec_sub)

        return pro_forma

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
