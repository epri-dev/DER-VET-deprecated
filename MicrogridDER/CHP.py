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
from storagevet.Technology.DER import DER

# thermal load unit is BTU/h
BTU_H_PER_KW = 3412.14  # 1kW = 3412.14 BTU/h


class CHP(DER):
    """ Combined Heat and Power generation technology system

    """

    def __init__(self, name, params):
        """ Initializes a CHP class, inherited from DER class.

        Args:
            name (str): A unique string name for the technology being added, also works as category.
            params (dict): Dict of parameters for initialization
        """
        # create generic generator object
        DER.__init__(self, params['name'], 'CHP', params)

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
        self.variable_names = {'chp_elec', 'chp_therm', 'chp_on'}
        self.capital_cost = params['ccost']        # $     (fixed capitol cost)
        self.ccost_kw = params['ccost_kW']         # $/kW  (capitol cost per kW of electric power capacity)

    def add_vars(self, size):
        """ Adds optimization variables to dictionary

        Variables added:
            chp_elec (float Variable): A cvxpy variable for CHP electricity generation
            chp_therm (float Variable): A cvxpy variable for CHP thermal generation
            chp_on (boolean Variable): A cvxpy variable for CHP on/off flag

        Args:
            size (Int): Length of optimization variables to create

        Returns:
            Dictionary of optimization variables
        """

        variables = {'chp_elec': cvx.Variable(shape=size, name='chp_elec', nonneg=True),
                     'chp_therm': cvx.Variable(shape=size, name='chp_therm', nonneg=True),
                     'chp_on': cvx.Variable(shape=size, boolean=True, name='chp_on')}

        # CHP power reservation that can contribute to the POI
        variables.update({'chp_pow_res_C_min': cvx.Variable(shape=size, name='charge_up_potential', nonneg=True),
                          'chp_pow_res_C_max': cvx.Variable(shape=size, name='charge_down_potential', nonneg=True),
                          'chp_pow_res_D_min': cvx.Variable(shape=size, name='discharge_down_potential', nonneg=True),
                          'chp_pow_res_D_max': cvx.Variable(shape=size, name='discharge_up_potential', nonneg=True)})

        return variables

    def objective_function(self, variables, mask, annuity_scalar=1):
        """ Generates the objective function related to a CHP system.

        Args:
            variables (Dict): dictionary of variables being optimized
            mask (Series): time series (indices) of booleans used
            annuity_scalar (float): a scalar value to be multiplied by any yearly cost or benefit
                                    that helps capture the cost/benefit over the entire project lifetime
                                    (only to be set iff sizing)

        Returns:
            self.costs (Dict): Dict of objective costs
        """

        chp_elec = variables['chp_elec']
        # natural gas price has unit of $/MMBTU
        # OMExpenses has unit of $/MWh
        self.costs = {'chp_fuel': cvx.sum(cvx.multiply(chp_elec, self.heat_rate * (self.natural_gas_price[mask]*1000000)
                                                       * self.dt * annuity_scalar)),
                      'chp_variable': cvx.sum(cvx.multiply(chp_elec, (self.OMExpenses/1000) * self.dt * annuity_scalar))
                      }

        # add startup objective costs
        if self.startup:
            self.costs.update({'chp_startup': cvx.sum(variables['chp_on']) * self.p_startup * annuity_scalar})

        return self.costs

    def objective_constraints(self, variables, mask, reservations, mpc_ene=None):
        """ Builds the master constraint list for the subset of timeseries data being optimized.

        Args:
            variables (Dict): Dictionary of variables being optimized
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set
            reservations (Dict): Dictionary of energy and power reservations required by the services being
                performed with the current optimization subset
            mpc_ene (float): value of energy at end of last opt step (for mpc opt)

        Returns:
            A list of constraints that corresponds to any physical generator constraints and its service constraints
        """

        chp_elec = variables['chp_elec']
        chp_therm = variables['chp_therm']
        chp_on = variables['chp_on']
        constraint_list = []

        constraint_list += [cvx.NonPos(-chp_therm + (self.thermal_load[mask]/BTU_H_PER_KW))]
        constraint_list += [cvx.Zero(cvx.multiply(chp_therm, self.electric_heat_ratio) - chp_elec)]

        # # POI will handle the power reservations for technology, these 4 constraints will eventually move to
        # # Scenario via POI class
        # constraint_list += [cvx.NonPos(reservations['D_max'] - (self.electric_power_capacity * chp_on))]
        # constraint_list += [cvx.NonPos(reservations['D_max'] - (self.electric_power_capacity - chp_elec))]
        # constraint_list += [cvx.NonPos(reservations['D_min'] - chp_elec)]

        # CHP physical/inverter constraints
        constraint_list += [cvx.NonPos(-chp_elec)]
        constraint_list += [cvx.NonPos(chp_elec - self.electric_power_capacity * chp_on)]

        discharge_down_potential = variables['chp_pow_res_D_min']
        discharge_up_potential = variables['chp_pow_res_D_max']

        # power reservation contributed by CHP technology has different meaning and should be separate from that
        # contributed by service/value stream
        # reservation potential should be the technology system capacity to measure how much it can discharge less or
        # how much it can flexibly discharge more
        constraint_list += [cvx.NonPos(discharge_up_potential - (self.electric_power_capacity * chp_on))]
        constraint_list += [cvx.NonPos(discharge_up_potential - (self.electric_power_capacity - chp_elec))]
        constraint_list += [cvx.Zero(discharge_down_potential - chp_elec)]

        # testing symmetric reservation for combined market
        # constraint_list += [cvx.Zero(discharge_down_potential - discharge_up_potential)]

        return constraint_list

    def timeseries_report(self):
        """ Summaries the optimization results for this generator.

        Returns: A timeseries dataframe with user-friendly column headers that summarize the results
            pertaining to this instance

        """

        results = pd.DataFrame(index=self.variables.index)
        results[self.name + ' CHP Generation (kW)'] = self.variables['chp_elec']
        results[self.name + ' CHP Thermal Generation (BTU)'] = self.variables['chp_therm']
        results[self.name + ' CHP on (y/n)'] = self.variables['chp_on']
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
        pro_forma = super().proforma_report(opt_years, results)
        fuel_col_name = self.name + ' Natural Gas Costs'
        variable_col_name = self.name + ' Variable O&M Costs'
        chp_elec = self.variables['chp_elec']

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
