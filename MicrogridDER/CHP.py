"""
Diesel

This Python class contains methods and attributes specific for technology analysis within StorageVet.
"""

__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2019. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani',
               'Micah Botkin-Levy', "Thien Nguyen", 'Yekta Yazar']
__license__ = 'EPRI'
__maintainer__ = ['Evan Giarta', 'Miles Evans']
__email__ = ['egiarta@epri.com', 'mevans@epri.com']

import cvxpy as cvx
import numpy as np
import pandas as pd
from storagevet.Technology.DistributedEnergyResource import DER
from MicrogridDER.Sizing import Sizing
from storagevet import Library as Lib


# thermal load unit is BTU/h
BTU_H_PER_KW = 3412.14  # 1kW = 3412.14 BTU/h


class CHP(DER, Sizing):
    """ Combined Heat and Power generation technology system

    """

    def __init__(self, params):
        """ Initializes a CHP class, inherited from DER class.

        Args:
            params (dict): Dict of parameters for initialization
        """
        # create generic generator object
        DER.__init__(self, 'CHP', 'Generator', params)
        Sizing.__init__(self)

        # input params, UNITS ARE COMMENTED TO THE RIGHT
        self.electric_heat_ratio = params['electric_heat_ratio']
        self.electric_power_capacity = params['electric_power_capacity']   # kW
        self.electric_ramp_rate = params['electric_ramp_rate']             # MW/min
        self.heat_rate = params['heat_rate']                               # BTU/kWh
        self.startup = params['startup']                                   # boolean
        self.p_startup = params['p_startup']                               # $
        self.OMExpenses = params['OMexpenses']                             # $/MWh
        self.natural_gas_price = params['natural_gas_price']               # $/MillionBTU
        self.thermal_load = params['thermal_load']                         # BTU/hr
        self.variable_names = {'chp_elec', 'chp_therm', 'chp_on', 'udis'}
        # self.capital_cost = params['ccost']        # $     (fixed capitol cost)
        # self.ccost_kw = params['ccost_kW']         # $/kW  (capitol cost per kW of electric power capacity)
        self.capital_cost_function = [params['ccost'], params['ccost_kw']]

    def get_capex(self) -> cvx.Variable or float:
        """

        Returns: the capex of this DER

        """
        return np.dot(self.capital_cost_function, [1, self.electric_power_capacity])

    def grow_drop_data(self, years, frequency, load_growth):
        """ Adds data by growing the given data OR drops any extra data that might have slipped in.
        Update variable that hold timeseries data after adding growth data. These method should be called after
        add_growth_data and before the optimization is run.

        Args:
            years (List): list of years for which analysis will occur on
            frequency (str): period frequency of the timeseries data
            load_growth (float): percent/ decimal value of the growth rate of loads in this simulation

        """
        self.thermal_load = Lib.fill_extra_data(self.thermal_load, years, load_growth, frequency)
        self.thermal_load = Lib.drop_extra_data(self.thermal_load, years)

        self.natural_gas_price = Lib.fill_extra_data(self.natural_gas_price, years, 0, frequency)  # TODO: change growth rate of fuel prices (user input?)
        self.natural_gas_price = Lib.drop_extra_data(self.natural_gas_price, years)

    def discharge_capacity(self):
        """

        Returns: the maximum discharge that can be attained

        """
        return self.electric_power_capacity

    def qualifying_capacity(self, event_length):
        """ Describes how much power the DER can discharge to qualify for RA or DR. Used to determine
        the system's qualifying commitment.

        Args:
            event_length (int): the length of the RA or DR event, this is the
                total hours that a DER is expected to discharge for

        Returns: int/float

        """
        return self.electric_power_capacity

    def initialize_variables(self, size):
        """ Adds optimization variables to dictionary

        Variables added:

        Args:
            size (Int): Length of optimization variables to create

        Returns:
            Dictionary of optimization variables
        """

        self.variables_dict = {
            'chp_elec': cvx.Variable(shape=size, name=f'{self.name}-P', nonneg=True),
            'chp_therm': cvx.Variable(shape=size, name=f'{self.name}-thermalP', nonneg=True),
            'chp_on': cvx.Variable(shape=size, boolean=True, name=f'{self.name}-on'),
            'udis': cvx.Variable(shape=size, name=f'{self.name}-udis', nonneg=True),
        }

    def get_discharge(self, mask):
        """
        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set

        Returns: the discharge as a function of time for the

        """
        return self.variables_dict['chp_elec']

    def get_discharge_up_schedule(self, mask):
        """ the amount of discharge power in the up direction (supplying power up into the grid) that
        this DER can schedule to reserve

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                    in the subs data set

        Returns: CVXPY parameter/variable

        """
        return cvx.multiply(self.variables_dict['chp_on'], self.electric_power_capacity - self.variables_dict['chp_elec'])

    def get_discharge_down_schedule(self, mask):
        """ the amount of discharging power in the up direction (pulling power down from the grid) that
        this DER can schedule to reserve

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                    in the subs data set

        Returns: CVXPY parameter/variable

        """
        return cvx.multiply(self.variables_dict['chp_on'], self.variables_dict['chp_elec'])

    def get_energy_option_down(self, mask):
        """ the amount of energy in a timestep that is taken from the distribution grid

        Returns: the energy throughput in kWh for this technology

        """
        return self.dt * self.variables_dict['udis']

    def objective_function(self, mask, annuity_scalar=1):
        """ Generates the objective function related to a technology. Default includes O&M which can be 0

        Args:
            mask (Series): Series of booleans used, the same length as case.power_kw
            annuity_scalar (float): a scalar value to be multiplied by any yearly cost or benefit that helps capture the cost/benefit over
                the entire project lifetime (only to be set iff sizing)

        Returns:
            costs (Dict): Dict of objective costs
        """

        # natural gas price has unit of $/MMBTU
        # OMExpenses has unit of $/MWh
        costs = {'chp_fuel': cvx.sum(cvx.multiply(self.variables_dict['chp_elec'], self.heat_rate * (self.natural_gas_price.loc[mask]*1000000)
                                                  * self.dt * annuity_scalar)),
                 'chp_variable': cvx.sum(self.variables_dict['chp_elec'] * (self.OMExpenses/1000) * self.dt * annuity_scalar)
                 }

        # add startup objective costs
        if self.startup:
            # TODO this is NOT how you would calculate the start up cost of a CHP. pls look at formulation doc and revise --HN
            costs.update({'chp_startup': cvx.sum(self.variables_dict['chp_on']) * self.p_startup * annuity_scalar})

        return costs

    def constraints(self, mask):
        """Default build constraint list method. Used by services that do not have constraints.

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                    in the subs data set

        Returns:
            A list of constraints that corresponds the battery's physical constraints and its service constraints
        """
        constraint_list = []

        constraint_list += [cvx.NonPos(-self.variables_dict['chp_therm'] + (self.thermal_load.loc[mask]/BTU_H_PER_KW))]
        constraint_list += [cvx.Zero(self.variables_dict['chp_therm'] * self.electric_heat_ratio - self.variables_dict['chp_elec'])]

        # CHP physical/inverter constraints
        constraint_list += [cvx.NonPos(self.variables_dict['chp_elec'] - self.electric_power_capacity * self.variables_dict['chp_on'])]

        return constraint_list

    def timeseries_report(self):
        """ Summaries the optimization results for this generator.

        Returns: A timeseries dataframe with user-friendly column headers that summarize the results
            pertaining to this instance

        """
        tech_id = self.unique_tech_id()
        results = pd.DataFrame(index=self.variables_df.index)
        results[tech_id + ' CHP Generation (kW)'] = self.variables_df['chp_elec']
        results[tech_id + ' CHP Thermal Generation (kW)'] = self.variables_df['chp_therm']
        results[tech_id + ' CHP on (y/n)'] = self.variables_df['chp_on']
        results[tech_id + ' Energy Option (kWh)'] = self.variables_df['udis'] * self.dt

        return results

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
        variable_col_name = tech_id + ' Variable O&M Costs'
        chp_elec = self.variables_df['chp_elec']

        for year in opt_years:
            chp_elec_sub = chp_elec.loc[chp_elec.index.year == year]
            # add variable costs
            pro_forma.loc[pd.Period(year=year, freq='y'), variable_col_name] = -np.sum(self.OMExpenses * self.dt
                                                                                       * chp_elec_sub)
            # add fuel costs
            pro_forma.loc[pd.Period(year=year, freq='y'), fuel_col_name] = -np.sum(self.heat_rate
                                                                                   * self.natural_gas_price * self.dt * chp_elec_sub)

        return pro_forma

    def sizing_summary(self):
        """

        Returns: A dataframe indexed by the terms that describe this DER's size and capital costs.

        """

        index = pd.Index([self.name], name='DER')
        sizing_results = pd.DataFrame({'Power Rating (kW)': self.electric_power_capacity}, index=index)

        return sizing_results
