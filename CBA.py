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
        self.report_annualized_values = False
        self.equipment_lifetime_report = pd.DataFrame()

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

    def find_end_year(self, project_start_year, user_given_end_year, der_list):
        """ This method looks at the analysis horizon mode and sets up the CBA class
        for the indicated mode

        Args:
            project_start_year (pd.Period): the first year the project is operational
            user_given_end_year (pd.Period): the user given last year the project is operations
            der_list (list): list of DERs initialized with user values

        Returns: pandas Period representation of the year that DERVET will end CBA analysis

        """
        # (1) User-defined (this should continue to be default)
        if self.horizon_mode == 1:
            return user_given_end_year
        # (2) Auto-calculate based on shortest equipment lifetime. (No size optimization)
        if self.horizon_mode == 2:
            shortest_lifetime = 1000  # no technology should last 1000 years -- so this is safe to hardcode
            for der_instance in der_list:
                shortest_lifetime = min(der_instance.expected_lifetime, shortest_lifetime)
                if der_instance.being_sized():
                    e_logger.error("Analysis horizon mode == 'Auto-calculate based on shortest equipment lifetime', DER-VET will not size any DERs " +
                                   f"when this horizon mode is selected. {der_instance.name} is being sized. Please resolve and rerun.")
                    return pd.Period(year=0, freq='y')  # cannot preform size optimization with mode==2
            return project_start_year + shortest_lifetime-1
        # (3) Auto-calculate based on longest equipment lifetime. (No size optimization)
        if self.horizon_mode == 3:
            longest_lifetime = 0
            for der_instance in der_list:
                longest_lifetime = max(der_instance.expected_lifetime, longest_lifetime)
                if der_instance.being_sized():
                    e_logger.error("Analysis horizon mode == 'Auto-calculate based on longest equipment lifetime', DER-VET will not size any DERs " +
                                   f"when this horizon mode is selected. {der_instance.name} is being sized. Please resolve and rerun.")
                    return pd.Period(year=0, freq='y')  # cannot preform size optimization with mode==3
            return project_start_year + longest_lifetime-1
        # (4) Carrying Cost (single technology only)
        if self.horizon_mode == 4:
            self.report_annualized_values = True
            if len(der_list) > 1:
                e_logger.error("Analysis horizon mode == 'Carrying cost', DER-VET cannot convert all value streams into annualized values " +
                               f"when more than one DER has been selected. There are {len(der_list)} active. Please resolve and rerun.")
                return pd.Period(year=0, freq='y')
            else:
                # require that e < d
                only_tech = der_list[0]
                if only_tech.escalation_rate >= self.npv_discount_rate:
                    e_logger.error(f"The technology escalation rate ({only_tech.escalation_rate}) cannot be greater " +
                                   f"than the project discount rate ({self.npv_discount_rate}). Please edit the 'ter' value for {only_tech.name}.")
                    return pd.Period(year=0, freq='y')
                return project_start_year + only_tech.expected_lifetime-1

    @staticmethod
    def get_years_after_failures(start_year, end_year, der_list):
        """ The optimization should be re-run for every year an 'unreplacable' piece of equipment fails before the
        lifetime of the longest-lived equipment. No need to re-run the optimization if equipment fails in some
        year and is replaced.

        Args:
            start_year (pd.Period): the first year the project is operational
            end_year (pd.Period): the last year the project is operational
            der_list (list): list of DERs initialized with user values

        Returns: list of the year(s) after an 'unreplacable' DER fails/reaches its end of life

        """
        rerun_opt_on = []
        for der_instance in der_list:
            yrs_failed = der_instance.set_failure_years(end_year)
            if not der_instance.replaceable:
                rerun_opt_on += yrs_failed
        # increase the year by 1 (this will be the years that the operational DER mix will change)
        diff_der_mix_yrs = [year+1 for year in rerun_opt_on if year < end_year.year]
        return list(set(diff_der_mix_yrs))  # get rid of any duplicates

    def annuity_scalar(self, start_year, end_year, opt_years):
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
            dollar_per_year[yr_index + 1] = dollar_per_year[yr_index] * (1 + self.inflation_rate)
            yr_index += 1
        yr_index = base_year - start_year.year
        while yr_index > 0:
            dollar_per_year[yr_index - 1] = dollar_per_year[yr_index] * (1 / (1 + self.inflation_rate))
            yr_index -= 1
        lifetime_npv_alpha = np.npv(self.npv_discount_rate, [0] + dollar_per_year)
        return lifetime_npv_alpha

    def calculate(self, technologies, value_streams, results, start_year, end_year, opt_years):
        """ this function calculates the proforma, cost-benefit, npv, and payback using the optimization variable results
        saved in results and the set of technology and service instances that have (if any) values that the user indicated
        they wanted to use when evaluating the CBA.

        Instead of using the technologies and services as they are passed in from the call in the Results class, we will pass
        the technologies and services with the values the user denoted to be used for evaluating the CBA.

        Args:
            technologies (Dict): Dict of technologies (needed to get capital and om costs)
            value_streams (Dict): Dict of all services to calculate cost avoided or profit
            results (DataFrame): DataFrame of all the concatenated timseries_report() method results from each DER
                and ValueStream
            start_year (Period)
            end_year (Period)
            opt_years (list)

        """
        self.initiate_cost_benefit_analysis(technologies, value_streams)
        super().calculate(self.ders, self.value_streams, results, start_year, end_year, opt_years)
        tech_list = [item for sublist in [list(instance_dict.values()) for instance_dict in self.ders.values()] for item in sublist]
        self.create_equipment_lifetime_report(tech_list)

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

    def proforma_report(self, technologies, valuestreams, results, start_year, end_year, opt_years):
        """ Calculates and returns the proforma

        Args:
            technologies (list): list of technologies (needed to get capital and om costs)
            valuestreams (Dict): Dict of all services to calculate cost avoided or profit
            results (DataFrame): DataFrame of all the concatenated timseries_report() method results from each DER
                and ValueStream
            start_year (Period)
            end_year (Period)
            opt_years (list)

        Returns: dataframe proforma
        """
        proforma = super().proforma_report(technologies, valuestreams, results, start_year, end_year, opt_years)
        proforma_wo_yr_net = proforma.iloc[:, :-1]
        proforma = self.replacement_costs(proforma_wo_yr_net, technologies, end_year)
        proforma = self.zero_out_dead_der_costs(proforma, technologies, end_year)
        proforma = self.update_capital_cost_construction_year(proforma, technologies)
        der_eol = self.calculate_end_of_life_value(proforma, technologies, start_year, end_year)
        # add decommissioning costs to proforma
        proforma = proforma.join(der_eol)
        proforma = self.calculate_taxes(proforma, technologies)

        if self.report_annualized_values:
            # already checked to make sure there is only 1 DER
            tech = technologies[0]
            # replace capital cost columns with economic_carrying cost
            ecc_df = tech.economic_carrying_cost(self.npv_discount_rate, proforma.index)
            # drop original Capital Cost
            proforma = proforma.drop(columns=[tech.zero_column_name()])
            # add the ECC to the proforma
            proforma = proforma.join(ecc_df)
        # sort alphabetically
        proforma.sort_index(axis=1, inplace=True)
        # recalculate the net (sum of the row's columns)
        proforma['Yearly Net Value'] = proforma.sum(axis=1)
        return proforma

    @staticmethod
    def replacement_costs(proforma, technologies, end_year):
        """ takes the proforma and adds cash flow columns that represent any tax that was received or paid
        as a result

        Args:
            proforma (DataFrame): Pro-forma DataFrame that was created from each ValueStream or DER active
            technologies (list): Dict of technologies (needed to get capital and om costs)
            end_year (Period)

        """
        for der_inst in technologies:
            replacement_df = der_inst.replacement_report(end_year)
            proforma = proforma.join(replacement_df)
            proforma = proforma.fillna(value=0)
        return proforma

    @staticmethod
    def zero_out_dead_der_costs(proforma, technologies, end_year):
        """ Determines years of the project that a DER is past its expected lifetime, then
        zeros out the costs for those years (for each DER in the project)

        Args:
            proforma:
            technologies:
            end_year (Period)

        Returns: updated proforma

        """
        for der_isnt in technologies:
            if not der_isnt.replaceable:
                last_operating_year = der_isnt.last_operation_year
                if end_year > last_operating_year:
                    column_mask = proforma.columns.str.contains(der_isnt.unique_tech_id(), regex=False)
                    proforma.loc[last_operating_year + 1:, column_mask] = 0
        return proforma

    @staticmethod
    def update_capital_cost_construction_year(proforma, technologies):
        """ Determines years of the project that a DER is past its expected lifetime, then
        zeros out the costs for those years (for each DER in the project)

        Args:
            proforma:
            technologies:

        Returns: updated proforma

        """
        for der_isnt in technologies:
            capex_df = der_isnt.put_capital_cost_on_construction_year(proforma.index)
            proforma.update(capex_df)
        return proforma

    @staticmethod
    def calculate_end_of_life_value(proforma, technologies, start_year, end_year):
        """ takes the proforma and adds cash flow columns that represent any tax that was received or paid
        as a result

        Args:
            proforma (DataFrame): Pro-forma DataFrame that was created from each ValueStream or DER active
            technologies (list): Dict of technologies (needed to get capital and om costs)
            start_year (Period)
            end_year (Period)

        """
        end_of_life_costs = pd.DataFrame(index=proforma.index)
        for der_inst in technologies:
            # collect the decommissioning costs at the technology's end of life
            decommission_pd = der_inst.decommissioning_report(end_year)
            end_of_life_costs = end_of_life_costs.join(decommission_pd)
            # collect salvage value
            salvage_value = der_inst.calculate_salvage_value(start_year, end_year)
            # add tp EOL dataframe
            salvage_pd = pd.DataFrame({f"{der_inst.unique_tech_id()} Salvage Value": salvage_value}, index=[end_year])
            end_of_life_costs = end_of_life_costs.join(salvage_pd)
        end_of_life_costs = end_of_life_costs.fillna(value=0)

        return end_of_life_costs

    def calculate_taxes(self, proforma, technologies):
        """ takes the proforma and adds cash flow columns that represent any tax that was received or paid
        as a result, then recalculates the Yearly Net Value column

        Args:
            proforma (DataFrame): Pro-forma DataFrame that was created from each ValueStream or DER active
            technologies (list): Dict of technologies (needed to get capital and om costs)

        Returns: proforma considering the 'Overall Tax Burden'

        """
        proj_years = len(proforma) -1
        yearly_net = proforma.iloc[1:, :].sum(axis=1).values

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
            capital_costs += np.multiply(tax_schedule, proforma.loc['CAPEX Year', der_inst.zero_column_name()])
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
        return proforma_taxes

    def payback_report(self, proforma, opt_years):
        """ calculates and saves the payback period and discounted payback period in a dataframe

        Args:
            proforma (DataFrame): Pro-forma DataFrame that was created from each ValueStream or DER active
            opt_years (list)

        """
        super().payback_report(proforma, opt_years)
        npv_df = pd.DataFrame({'Lifetime Net Present Value':  self.npv['Lifetime Present Value'].values},
                              index=pd.Index(['$'], name="Unit"))
        other_metrics = pd.DataFrame({'Internal Rate of Return': self.internal_rate_of_return(proforma),
                                     'Cost-Benefit Ratio': self.cost_benefit_ratio(self.cost_benefit)},
                                     index=pd.Index(['-'], name='Unit'))
        self.payback = pd.merge(self.payback, npv_df, how='outer', on='Unit')
        self.payback = pd.merge(self.payback, other_metrics, how='outer', on='Unit')

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

    def create_equipment_lifetime_report(self, der_lst):
        """

        Args:
            der_lst:

        """
        data = {der_inst.unique_tech_id(): [der_inst.construction_year, der_inst.operation_year, der_inst.last_operation_year]
                for der_inst in der_lst}
        self.equipment_lifetime_report = pd.DataFrame(data, index=['Beginning of Life', 'Operation Begins', 'End of Life'])
