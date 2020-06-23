"""
Finances.py

This Python class contains methods and attributes vital for completing financial analysis given optimal dispathc.
"""

__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'mevans@epri.com']
__version__ = 'beta'  # beta version

import logging
from storagevet.Finances import Financial
import numpy as np
import copy
import pandas as pd


SATURDAY = 5

u_logger = logging.getLogger('User')
e_logger = logging.getLogger('Error')


class CostBenefitAnalysis(Financial):
    """ This Cost Benefit Analysis Module

    """

    def __init__(self, financial_params):
        """ Initialize CBA model and edit any attributes that the user denoted a separate value
        to evaluate the CBA with

        Args:
            financial_params (dict): parameter dictionary as the Params class created
        """
        super().__init__(financial_params)
        self.horizon_mode = financial_params['analysis_horizon_mode']
        self.location = financial_params['location']
        self.ownership = financial_params['ownership']
        self.state_tax_rate = financial_params['state_tax_rate']/100
        self.federal_tax_rate = financial_params['federal_tax_rate']/100
        self.property_tax_rate = financial_params['property_tax_rate']/100

        self.Scenario = financial_params['CBA']['Scenario']
        self.Finance = financial_params['CBA']['Finance']
        self.valuestream_values = financial_params['CBA']['valuestream_values']
        self.ders_values = financial_params['CBA']['ders_values']
        if 'Battery' in self.ders_values.keys():
            self.ders_values['Battery'] = self.ders_values.pop('Battery')
        if 'CAES' in self.ders_values.keys():
            self.ders_values['CAES'] = self.ders_values.pop('CAES')

        self.value_streams = {}
        self.ders = {}

        self.macrs_depreciation = {
            3: [33.33, 44.45, 14.81, 7.41],
            5: [20, 32, 19.2, 11.52, 11.52, 5.76],
            7: [14.29, 24.49, 17.49, 12.49, 8.93, 8.92, 8.93, 4.46],
            10: [10, 18, 14.4, 11.52, 9.22, 7.37, 6.55, 6.55, 6.56, 6.55,
                 3.28],
            15: [5, 9.5, 8.55, 7.7, 6.83, 6.23, 5.9, 5.9, 5.91, 5.9,
                 5.91, 5.9, 5.91, 5.9, 5.91, 2.95],
            20: [3.75, 7.219, 6.677, 6.177, 5.713, 5.285, 4.888, 4.522, 4.462, 4.461,
                 4.462, 4.461, 4.462, 4.461, 4.462, 4.461, 4.462, 4.461, 4.462, 4.461,
                 2.231]
        }

    @staticmethod
    def annuity_scalar(start_year, end_year, opt_years, **kwargs):
        """Calculates an annuity scalar, used for sizing, to convert yearly costs/benefits
        this method is sometimes called before the class is initialized (hence it has to be
        static)

        Args:
            start_year (pd.Period): First year of project (from model parameter input)
            end_year (pd.Period): Last year of project (from model parameter input)
            opt_years (list): List of years that the user wants to optimize--should be length=1

        Returns: the NPV multiplier

        """
        n = end_year.year - start_year.year
        dollar_per_year = np.ones(n)
        base_year = min(opt_years)
        yr_index = base_year - start_year.year
        while yr_index < n - 1:
            dollar_per_year[yr_index + 1] = dollar_per_year[yr_index] * (1 + kwargs['inflation_rate'] / 100)
            yr_index += 1
        yr_index = base_year - start_year.year
        while yr_index > 0:
            dollar_per_year[yr_index - 1] = dollar_per_year[yr_index] * (100 / (1 + kwargs['inflation_rate']))
            yr_index -= 1
        lifetime_npv_alpha = np.npv(kwargs['npv_discount_rate']/100, [0] + dollar_per_year)
        return lifetime_npv_alpha

    def preform_cost_benefit_analysis(self, technologies, value_streams, results):
        """ this function calculates the proforma, cost-benefit, npv, and payback using the optimization variable results
        saved in results and the set of technology and service instances that have (if any) values that the user indicated
        they wanted to use when evaluating the CBA.

        Instead of using the technologies and services as they are passed in from the call in the Results class, we will pass
        the technologies and services with the values the user denoted to be used for evaluating the CBA.

        Args:
            technologies (Dict): all active technologies (provided access to ESS, generators, renewables to get capital and om costs)
            value_streams (Dict): Dict of all services to calculate cost avoided or profit
            results (DataFrame): DataFrame of all the concatenated timseries_report() method results from each DER
                and ValueStream

        """
        self.initiate_cost_benefit_analysis(technologies, value_streams)
        super().preform_cost_benefit_analysis(self.ders, self.value_streams, results)

    def initiate_cost_benefit_analysis(self, technologies, valuestreams):
        """ Prepares all the attributes in this instance of cbaDER with all the evaluation values.
        This function should be called before any finacial methods so that the user defined evaluation
        values are used

        Args:
            technologies (list): the management point of all active technology to access (needed to get capital and om costs)
            valuestreams (Dict): Dict of all services to calculate cost avoided or profit

        """
        # we deep copy because we do not want to change the original ValueStream objects
        self.value_streams = copy.deepcopy(valuestreams)
        self.ders = copy.deepcopy(technologies)

        self.place_evaluation_data()

    def place_evaluation_data(self):
        """ Place the data specified in the evaluation column into the correct places. This means all the monthly data,
        timeseries data, and single values are saved in their corresponding attributes within whatever ValueStream and DER
        that is active and has different values specified to evaluate the CBA with.

        """
        try:
            monthly_data = self.Scenario['monthly_data']
        except KeyError:
            monthly_data = None

        try:
            time_series = self.Scenario['time_series']
        except KeyError:
            time_series = None

        if time_series is not None or monthly_data is not None:
            for value_stream in self.value_streams.values():
                value_stream.update_price_signals(monthly_data, time_series)

        if 'customer_tariff' in self.Finance:
            self.tariff = self.Finance['customer_tariff']

        if 'User' in self.value_streams.keys():
            self.update_with_evaluation(self.value_streams['User'], self.valuestream_values['User'], self.verbose)

        for der_tag, instance_dict in self.ders_values.items():
            for id_str, der_instance in instance_dict.items():
                self.ders[der_tag][id_str].update_for_evaluation(der_instance)
                # self.update_with_evaluation(self.ders[der_tag][id_str], der_instance, self.verbose)

    @staticmethod
    def update_with_evaluation(param_object, evaluation_dict, verbose):
        """Searches through the class variables (which are dictionaries of the parameters with values to be used in the CBA)
        and saves that value

        Args:
            param_object (DER, ValueStream): the actual object that we want to edit
            evaluation_dict (dict, None): keys are the string representation of the attribute where value is saved, and values
                are what the attribute value should be
            verbose (bool): true or fla

        Returns: the param_object with attributes set to the evaluation values instead of the optimization values

        """
        if evaluation_dict:  # evaluates true if dict is not empty and the value is not None
            for key, value in evaluation_dict.items():
                try:
                    setattr(param_object, key, value)
                    print('attribute (' + param_object.name + ': ' + key + ') set: ' + str(value)) if verbose else None
                except KeyError:
                    print('No attribute ' + param_object.name + ': ' + key) if verbose else None

    def proforma_report(self, technologies, valuestreams, results):
        """ Calculates and returns the proforma

        Args:
            technologies (list): list of technologies (needed to get capital and om costs)
            valuestreams (Dict): Dict of all services to calculate cost avoided or profit
            results (DataFrame): DataFrame of all the concatenated timseries_report() method results from each DER
                and ValueStream

        Returns: dataframe proforma
        """
        proforma = super().proforma_report(technologies, valuestreams, results)
        proforma_w_taxes = self.calculate_taxes(proforma, technologies, valuestreams, results)
        return proforma_w_taxes

    def calculate_taxes(self, proforma, technologies, valuestreams, results):
        """ takes the proforma and adds cash flow columns that represent any tax that was received or paid
        as a result

        Args:
            proforma (DataFrame): Pro-forma DataFrame that was created from each ValueStream or DER active
            technologies (Dict): Dict of technologies (needed to get capital and om costs)
            valuestreams (Dict): Dict of all services to calculate cost avoided or profit
            results (DataFrame): DataFrame of all the concatenated timseries_report() method results from each DER
                and ValueStream

        Returns:

        """
        proj_years = len(proforma) - 1
        yearly_net = proforma.iloc[1:, -1].values

        # 1) Redistribute capital cost columns according to the DER's MACRS value
        capital_costs = np.zeros(proj_years)
        for der_inst in technologies:
            macrs_yr = der_inst.macrs
            if macrs_yr is None:
                continue
            tax_schedule = self.macrs_depreciation[macrs_yr]
            # extend/cut tax schedule to match length of project
            if len(tax_schedule) < proj_years:
                tax_schedule = tax_schedule + list(np.zeros(proj_years - len(tax_schedule)))
            else:
                tax_schedule = tax_schedule[:proj_years]
            capital_costs += np.multiply(tax_schedule, proforma.loc['CAPEX Year', der_inst.zero_column_name])
        yearly_net += capital_costs

        # 2) Calculate State tax based on the net cash flows in each year
        state_tax = yearly_net * self.state_tax_rate

        # 3) Calculate Federal tax based on the net cash flow in each year minus State taxes from that year
        yearly_net_post_state_tax = yearly_net - state_tax
        federal_tax = yearly_net_post_state_tax * self.federal_tax_rate

        # 4) Add the overall tax burden (= state tax + federal tax) to proforma, make sure columns are ordered s.t. yrly net is last
        overall_tax_burden = state_tax + federal_tax
        # drop yearly net value column
        proforma_taxes = proforma.iloc[:, :-1]
        proforma_taxes['Overall Tax Burden'] = np.insert(overall_tax_burden, 0, 0)
        # calculate the net (sum of the row's columns)
        proforma_taxes['Yearly Net Value'] = proforma_taxes.sum(axis=1)
        # save new proforma
        self.pro_forma = proforma_taxes
        return proforma_taxes

    def payback_report(self, proforma):
        """ calculates and saves the payback period and discounted payback period in a dataframe

        Args:
            proforma (DataFrame): Pro-forma DataFrame that was created from each ValueStream or DER active

        Returns:

        """
        self.payback = pd.DataFrame({'Payback Period': [self.payback_period(proforma), 0, 0],
                                     'Discounted Payback Period': [self.discounted_payback_period(proforma), 0, 0],
                                     'Net Present Value': [0] + self.npv['Lifetime Present Value'] + [0],
                                     'Internal Rate of Return': [0, 0, self.internal_rate_of_return(proforma)],
                                     'Cost-Benefit Ratio': [0, 0, self.cost_benefit_ratio(self.cost_benefit)]},
                                    index=pd.Index(['Years', '$', '-']))

    @staticmethod
    def internal_rate_of_return(proforma):
        """ calculates the discount rate that would return lifetime NPV= 0

        Args:
            proforma (DataFrame): Pro-forma DataFrame that was created from each ValueStream or DER active

        Returns: internal rate of return

        """
        return np.irr(proforma['Yearly Net Value'].values)

    @staticmethod
    def cost_benefit_ratio(cost_benefit):
        """ calculate the cost-benefit ratio

        Args:
            cost_benefit (DataFrame):

        Returns: discounted cost/discounted benefit

        """
        lifetime_discounted_cost = cost_benefit.loc['Lifetime Present Value', 'Cost ($)']
        lifetime_discounted_benefit = cost_benefit.loc['Lifetime Present Value', 'Benefit ($)']
        return lifetime_discounted_cost/lifetime_discounted_benefit
