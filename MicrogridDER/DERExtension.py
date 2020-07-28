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
from ErrorHandelling import *


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
        self.acr = params['acr'] / 100
        self.escalation_rate = params['ter'] / 100

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
        self.failure_years = []

    def set_failure_years(self, end_year):
        """ Gets the year(s) that this instance will fail and saves the information
         as an attribute of itself

        Args:
            end_year (pd.Period): the last year the project is operational

        Returns: list of year(s) that this equipement fails. if replaceable, then there might
        be more than one year (depending on when the end_year is and the lifetime of the DER)

        """
        fail_on = self.operation_year.year + self.expected_lifetime-1
        if self.replaceable:
            while fail_on <= end_year.year:
                self.failure_years.append(fail_on)
                fail_on += self.expected_lifetime
        else:
            if fail_on <= end_year.year:
                self.failure_years.append(fail_on)
        self.last_operation_year = pd.Period(fail_on)
        return self.failure_years

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

    def decommissioning_report(self, last_year):
        """ Returns the cost of decommissioning a DER and the year the cost will be incurred

        Returns: dataframe index by year that the cost applies to. if the year

        """
        cost = self.decommission_cost
        if self.replaceable:
            year = last_year
        else:
            year = pd.Period(self.operation_year.year + self.expected_lifetime-1)
        if year > last_year:
            year = last_year

        return pd.DataFrame({f"{self.unique_tech_id()} Decommissioning Cost": -cost}, index=[year])

    def calculate_salvage_value(self, start_year, last_year):
        """ Decode the user's input and return the salvage value
        (1) "Sunk Cost" this option means that there is no end of analysis value
            (salvage value = 0)
        (2) "Linear Salvage Value" which will calculate salvage value by multiplying
            the technology's capital cost by (remaining life/total life)
        (3) a number (in $) for the salvage value of the technology
            (User-specified Salvage Value)

        Args:
            start_year:
            last_year:

        Returns: the salvage value of the technology

        """
        if self.salvage_value == 'sunk cost':
            return 0
        last_decommission_year = start_year.year + self.expected_lifetime - 1

        # If the a technology has a life shorter than the analysis window with no replacement, then no salvage value applies.
        if last_decommission_year < last_year.year and not self.replaceable:
            return 0
        # else keep replacing, and update the DECOMMISSION_YEAR (assume installation occurs the year after)
        while self.replaceable and last_decommission_year < last_year.year:
            last_decommission_year += self.expected_lifetime

        # If it has a life shorter than the analysis window but is replaced, a salvage value will be applied.
        # If it has a life longer than the analysis window, then a salvage value will apply.
        years_beyond_project = last_decommission_year - last_year.year

        if years_beyond_project < 0:
            return 0

        if self.salvage_value == "linear salvage value":
            try:
                capex = self.get_capex().value
            except AttributeError:
                capex = self.get_capex()
            return capex * (years_beyond_project/self.expected_lifetime)
        else:
            return self.salvage_value

    def replacement_cost(self):
        """

        Returns: the cost of replacing this DER

        """
        return 0

    def replacement_report(self, end_year):
        """

        Args:
            end_year (pd.Period): the last year of analysis

        Returns:

        """
        report = pd.DataFrame()
        if self.replaceable:
            replacement_yrs = pd.Index([pd.Period(year+1, freq='y') for year in self.failure_years if year < end_year.year])
            report = pd.DataFrame({f"{self.unique_tech_id()} Replacement Costs": np.repeat(-self.replacement_cost(), len(replacement_yrs))},
                                  index=replacement_yrs)
        return report

    def economic_carrying_cost(self, d, indx):
        """ assumes length of project is the lifetime expectancy of this DER

        Args:
            d (float): discount rate
            indx

        Returns: dataframe report of yearly economic carrying cost

        """
        try:
            capex = self.get_capex().value
        except AttributeError:
            capex = self.get_capex()
        acr = self.acr * capex

        k_factor = [acr / ((1 + d)**k) for k in range(1, self.expected_lifetime + 1)]
        k_factor = sum(k_factor)

        time_factor = (1+self.escalation_rate)/(1+d)
        repalcement_factor = 1 / (1 - (time_factor**self.expected_lifetime))

        ecc_perc = k_factor * repalcement_factor * (d - self.escalation_rate)
        ecc = capex * ecc_perc
        per_yr = [-ecc*(time_factor**(k-1)) if not isinstance(year, str) and self.construction_year.year <= year.year <= self.last_operation_year.year
                  else 0 for k, year in enumerate(indx.values)]
        ecc_df = pd.DataFrame({f'{self.unique_tech_id()} Carrying Cost': per_yr}, index=indx)
        return ecc_df

    def put_capital_cost_on_construction_year(self, indx):
        """

        Args:
            indx:

        Returns:

        """
        start_year = indx[1]
        if self.construction_year.year < start_year.year:
            return pd.DataFrame(index=indx)
        capex_df = pd.DataFrame({self.zero_column_name(): np.zeros(len(indx))}, index=indx)
        try:
            capex = self.get_capex().value
        except AttributeError:
            capex = self.get_capex()
        capex_df.loc[self.construction_year, self.zero_column_name()] = capex
        return capex_df
