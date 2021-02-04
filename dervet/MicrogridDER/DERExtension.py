"""
Defines an class that extends DERs beyond their definition in StorageVET
for the purpose of DER-VET functionallty

"""

__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani', 'Micah Botkin-Levy', 'Yekta Yazar']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Evan Giarta', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'egiarta@epri.com', 'mevans@epri.com']
__version__ = 'beta'

import numpy as np
import pandas as pd
from storagevet.ErrorHandelling import *


class DERExtension:
    """ This class is to be inherited by DER classes that want to allow the DER our generic
    DER model to extend beyond that in StorageVET

    """

    def __init__(self, params):
        """

        """
        TellUser.debug(f"Initializing {__name__}")
        # try to look for DERVET specific user inputs that are shared by all DERs
        self.nsr_response_time = params['nsr_response_time']
        self.sr_response_time = params['sr_response_time']
        self.startup_time = params['startup_time']  # startup time, default value of 0, units in minutes

        # CBA terms shared by all DERs
        self.macrs = params.get('macrs_term')
        self.construction_year = params.get('construction_year')
        self.operation_year = params.get('operation_year')
        self.decommission_cost = params['decommissioning_cost']
        self.salvage_value = params['salvage_value']
        self.expected_lifetime = params['expected_lifetime']
        self.replaceable = params['replaceable']
        self.escalation_rate = params['ter'] / 100
        self.ecc_perc = params['ecc%'] / 100
        self.replacement_construction_time = params.get('replacement_construction_time', 1)  # years

        self.replacement_cost_function = []
        rcost = params.get('rcost')
        if rcost is not None:
            self.replacement_cost_function.append(rcost)
        rcost_kW = params.get('rcost_kW')
        if rcost_kW is not None:
            self.replacement_cost_function.append(rcost_kW)
        rcost_kWh = params.get('rcost_kWh')
        if rcost_kWh is not None:
            self.replacement_cost_function.append(rcost_kWh)

        self.last_operation_year = pd.Period(year=0, freq='y')  # set this value w/ set_failure_years
        self.failure_preparation_years = []

    def set_failure_years(self, end_year, equipment_last_year_operation=None, time_btw_replacement=None):
        """ Gets the year(s) that this instance will fail and saves the information
         as an attribute of itself

        Args:
            end_year (pd.Period): the last year the project is operational
            equipment_last_year_operation (int): if a failed year was determined, then indicated here
            time_btw_replacement (int): number of years in between replacement installments (default is expected lifetime)

        Returns: list of year(s) that this equipement fails. if replaceable, then there might
        be more than one year (depending on when the end_year is and the lifetime of the DER)

        """
        if time_btw_replacement is None:
            time_btw_replacement = self.expected_lifetime
        if equipment_last_year_operation is None:
            equipment_last_year_operation = self.operation_year.year + time_btw_replacement - 1

        if equipment_last_year_operation <= end_year.year:
            self.failure_preparation_years.append(equipment_last_year_operation)
        if self.replaceable:
            equipment_last_year_operation += time_btw_replacement
            while equipment_last_year_operation < end_year.year:
                self.failure_preparation_years.append(equipment_last_year_operation)
                equipment_last_year_operation += time_btw_replacement

        self.last_operation_year = pd.Period(equipment_last_year_operation)
        self.failure_preparation_years = list(set(self.failure_preparation_years))
        return self.failure_preparation_years

    def operational(self, year):
        """

        Args:
            year (int):

        Returns: a boolean, indicating if this DER is operational during the given year

        """
        return self.last_operation_year.year >= year >= self.operation_year.year

    def update_for_evaluation(self, input_dict):
        """ Updates price related attributes with those specified in the input_dictionary

        Args:
            input_dict: hold input data, keys are the same as when initialized

        """
        macrs_term = input_dict.get('macrs_term')
        if macrs_term is not None:
            self.macrs = macrs_term

        ccost = input_dict.get('ccost')
        if ccost is not None:
            self.capital_cost_function[0] = ccost

        ccost_kw = input_dict.get('ccost_kw')
        if ccost_kw is not None:
            self.capital_cost_function[1] = ccost_kw

        ccost_kwh = input_dict.get('ccost_kwh')
        if ccost_kwh is not None:
            self.capital_cost_function[2] = ccost_kwh

    def update_price_signals(self, id_str, monthly_data=None, time_series_data=None):
        """ Updates attributes related to price signals with new price signals that are saved in
        the arguments of the method. Only updates the price signals that exist, and does not require all
        price signals needed for this service.

        Args:
            monthly_data (DataFrame): monthly data after pre-processing
            time_series_data (DataFrame): time series data after pre-processing

        """
        pass

    def replacement_cost(self):
        """

        Returns: the cost of replacing this DER

        """
        return 0

    def replacement_report(self, end_year, escalation_func):
        """ Replacement costs occur YEr F

        Args:
            end_year (pd.Period): the last year of analysis
            escalation_func

        Returns:

        """
        report = pd.Series()
        if self.replaceable:
            replacement_yrs = pd.Index([pd.Period(year+1-self.replacement_construction_time, freq='y') for year in self.failure_preparation_years if year < end_year.year])
            report = pd.DataFrame({f"{self.unique_tech_id()} Replacement Costs": np.repeat(-self.replacement_cost(), len(replacement_yrs))},
                                  index=replacement_yrs)
            report = report.fillna(value=0)
            report = escalation_func(report, self.escalation_rate, self.operation_year.year)

        return report

    def put_capital_cost_on_construction_year(self, indx):
        """ If the construction year of the DER is the start year of the project or after,
        the apply the capital cost on the year of construction.

        Args:
            indx:

        Returns: dataframe with the capex cost on the correct project year

        """
        start_year = indx[1]
        if self.construction_year.year < start_year.year:
            return pd.DataFrame(index=indx)
        capex_df = pd.DataFrame({self.zero_column_name(): np.zeros(len(indx))}, index=indx)
        capex = -self.get_capex()
        capex_df.loc[self.construction_year, self.zero_column_name()] = capex
        return capex_df

    def decommissioning_report(self, last_year):
        """ Returns the cost of decommissioning a DER and the year the cost will be incurred

        Returns: dataframe index by year that the cost applies to. if the year

        """
        cost = self.decommission_cost
        year = min(last_year, self.last_operation_year+1)
        return pd.DataFrame({f"{self.unique_tech_id()} Decommissioning Cost": -cost}, index=[year])

    def calculate_salvage_value(self, last_year):
        """ Decode the user's input and return the salvage value
        (1) "Sunk Cost" this option means that there is no end of analysis value
            (salvage value = 0)
        (2) "Linear Salvage Value" which will calculate salvage value by multiplying
            the technology's capital cost by (remaining life/total life)
        (3) a number (in $) for the salvage value of the technology
            (User-specified Salvage Value)

        Args:
            last_year:

        Returns: the salvage value of the technology

        """
        if self.salvage_value == 'sunk cost':
            return 0

        # If the a technology has a life shorter (or equal to) than the analysis window with no replacement, then no salvage value applies.
        if self.last_operation_year+1 <= last_year:
            return 0

        # If it has a life shorter than the analysis window but is replaced, a salvage value will be applied.
        # If it has a life longer than the analysis window, then a salvage value will apply.
        years_beyond_project = self.last_operation_year.year - last_year.year

        if years_beyond_project < 0:
            return 0

        if self.salvage_value == "linear salvage value":
            return self.get_capex() * (years_beyond_project/self.expected_lifetime)
        else:
            return self.salvage_value

    def salvage_value_report(self, end_year):
        """ Returns the salvage value a DER and the year it will be incurred

        Args:
                end_year: last year of project

        Returns: dataframe index by year that the value applies to.

        """
        # collect salvage value
        salvage_value = self.calculate_salvage_value(end_year)
        # dataframe
        salvage_pd = pd.DataFrame({f"{self.unique_tech_id()} Salvage Value": salvage_value}, index=[end_year])
        return salvage_pd

    def economic_carrying_cost_report(self, i, end_year, escalation_func):
        """ assumes length of project is the lifetime expectancy of this DER

        Args:
            i (float): inflation rate
            end_year (pd.Period): end year of the project
            escalation_func

        Returns: dataframe report of yearly economic carrying cost
        NOTES: in ECC mode we have assumed 1 DER and the end of analysis is the last year of operation
        """
        # annual-ize capital costs
        yr_incurred_capital = self.construction_year.year
        yr_last_operation = self.operation_year.year + self.expected_lifetime - 1
        if self.construction_year == self.operation_year:
            yr_start_payments = yr_incurred_capital
        else:
            yr_start_payments = yr_incurred_capital + 1
        year_ranges = pd.period_range(yr_start_payments, yr_last_operation, freq='y')
        inflation_factor = [(1+i) ** (t.year - self.construction_year.year) for t in year_ranges]
        ecc_capex = np.multiply(inflation_factor, -self.get_capex() * self.ecc_perc)
        ecc = pd.DataFrame({f"{self.unique_tech_id()} Capex (incurred {yr_incurred_capital})": ecc_capex}, index=year_ranges)

        # annual-ize replacement costs
        if self.replaceable:
            replacement_costs_df = self.replacement_report(end_year, escalation_func)
            for year in replacement_costs_df.index:
                yr_start_operating_new_equipment = year.year + self.replacement_construction_time
                yr_last_operation = yr_start_operating_new_equipment + self.expected_lifetime - 1
                temp_year_range = pd.period_range(yr_start_operating_new_equipment, yr_last_operation, freq='y')
                inflation_factor = [(1+i) ** (t.year - self.construction_year.year) for t in temp_year_range]
                ecc_replacement = np.multiply(inflation_factor, replacement_costs_df.loc[year].values[0] * self.ecc_perc)
                temp_df = pd.DataFrame({f"{self.unique_tech_id()} Replacement (incurred {year.year})": ecc_replacement}, index=temp_year_range)
                ecc = pd.concat([ecc, temp_df], axis=1)

        # replace NaN values with 0 and cut off any payments beyond the project lifetime
        ecc.fillna(value=0, inplace=True)
        ecc = ecc.loc[:end_year, :]
        ecc[f'{self.unique_tech_id()} Carrying Cost'] = ecc.sum(axis=1)
        return ecc, ecc.loc[:, f'{self.unique_tech_id()} Carrying Cost']

    def tax_contribution(self, depreciation_schedules, project_length):
        macrs_yr = self.macrs
        if macrs_yr is None:
            return
        tax_schedule = depreciation_schedules[macrs_yr]
        # extend/cut tax schedule to match length of project
        if len(tax_schedule) < project_length:
            tax_schedule = tax_schedule + list(np.zeros(project_length - len(tax_schedule)))
        else:
            tax_schedule = tax_schedule[:project_length]
        return np.multiply(tax_schedule, self.get_capex() / 100)
