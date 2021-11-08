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
EmissionReduction.py

This Python class contains methods and attributes specific for service analysis within DER-VET. The purpose of this
service is to provide the optimization with the objective to minimize emissions reduction.
"""
from storagevet.ValueStreams.ValueStream import ValueStream
from dervet.MicrogridResult import MicrogridResult
import cvxpy as cvx
import pandas as pd
import storagevet.Library as Lib
import numpy as np


class EmissionReduction(ValueStream):
    """ Emissions Reduction service. Can be extended to be defined for carbon, nox, or sox emissions.

    """

    def __init__(self, params):
        """ Initialize class with input parameters.

        Args:
            params (Dict): input parameters
        """
        ValueStream.__init__(self, 'Emission Reduction', params)
        self.pareto_analysis = params['pareto_analysis']  # TODO implement boolean
        self.number_of_pareto_iterations = params['number_of_pareto_iterations']
        self.marginal_emission_factor = params['mef']  # the marginal emission factor for a GHG (CO2, NOx, SO2)
        self.pareto_alpha = 0  # alpha value of the pareto curve; multiplied to the emissions objective (the first one is 0, this is the post-facto calculation)
        # fuel information -- TODO unhardcode grab from user, then convert following dict
        # self.fuel_combustion_info = params['fuel_emission_info']  # this matches up with fuel type with emission
        self.fuel_information = {
            'natural gas': {
                'hhv': 0.001026,  # mmBtu/scf
                'co2ef': 53.06,  # kg CO2/mmBtu
                'n20ef': 0.10,  # kg N2O/mmBtu
                'ch4ef': 1.0,  # kg CH4/mmBtu
            },
            'coal': {
                'hhv': 19.73,  # mmBtu/mmBtu
                'co2ef': 95.52,  # kg CO2/mmBtu
                'n20ef': 1.6,  # kg N2O/mmBtu
                'ch4ef': 11,  # kg CH4/mmBtu
            },
            'biodiesel': {
                'hhv': 0.128,  # mmBtu/gal
                'co2ef': 73.84,  # kg CO2/mmBtu
                'n20ef': 0.11,  # kg N2O/mmBtu
                'ch4ef': 1.1,  # kg CH4/mmBtu
            }
        }

        self.pareto_curve = dict()
        self.technologies = dict()  # TODO set this value to be able to get the fuel types and mass for the optimization
        self.total_emissions = pd.DataFrame()

    def pareto_values(self):
        """ Returns list of alpha values for pareto analysis.
        """
        # last value must be nan to indicate all values have been run
        base = [1,2,5]
        # foo = []
        # # exponential decay (of base) to 0
        # for to_power_of in range(-int(self.number_of_pareto_iterations/6), 0):
        #     foo = foo + list(np.multiply(base, 10 ** to_power_of))
        # # exponential growth (of base) from 1
        # for to_power_of in range(0, int(self.number_of_pareto_iterations/6)):
        #     foo = foo + list(np.multiply(base, 10 ** to_power_of))

        foo = [0.0005]
        for to_power_of in range(-2, 0):
            foo = foo + list(np.multiply(base, 10 ** to_power_of))
        # exponential growth (of base) from 1
        for to_power_of in range(2):
            foo = foo + list(np.multiply(base, 10 ** to_power_of))
        foo += [1e9]
        return foo + [np.nan]

    def grow_drop_data(self, years, frequency, load_growth):
        """ Adds data by growing the given data OR drops any extra data that might have slipped in.
        Update variable that hold timeseries data after adding growth data. These method should be called after
        add_growth_data and before the optimization is run.

        Args:
            years (List): list of years for which analysis will occur on
            frequency (str): period frequency of the timeseries data
            load_growth (float): percent/ decimal value of the growth rate of loads in this simulation


        """
        self.marginal_emission_factor = Lib.fill_extra_data(self.marginal_emission_factor, years, 0, frequency)
        self.marginal_emission_factor = Lib.drop_extra_data(self.marginal_emission_factor, years)

    def objective_function(self, mask, load_sum, tot_variable_gen, generator_out_sum, net_ess_power, annuity_scalar=1):
        """ Generates the full objective function, including the optimization variables.

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set
            tot_variable_gen (Expression): the sum of the variable/intermittent generation sources
            load_sum (list, Expression): the sum of load within the system
            generator_out_sum (list, Expression): the sum of conventional generation within the system
            net_ess_power (list, Expression): the sum of the net power of all the ESS in the system. [= charge - discharge]
            annuity_scalar (float): a scalar value to be multiplied by any yearly cost or benefit that helps capture the cost/benefit over
                        the entire project lifetime (only to be set iff sizing)

        Returns:
            A dictionary with the portion of the objective function that it affects, labeled by the expression's key. Default is to return {}.
        """
        print(f"using alpha {self.pareto_alpha}")
        if annuity_scalar != 1:
            print('Sizing with emissions reduction has not been tested/validated/proven. There might not be a solution. If there is, it might not be accurate.')
        # CALCULATE SYSTEM EMISSIONS
        # marginal emissions factors should be applied to the net load (pulling power from the grid is positive)
        # remove generator generation from load attributed to marginal emissions
        mef = cvx.Parameter(value=self.marginal_emission_factor.loc[mask].values, shape=sum(mask), name='MEF')
        load_price = cvx.multiply(mef, load_sum)
        ess_net_price = cvx.multiply(mef, net_ess_power)
        variable_gen_prof = cvx.multiply(-mef, tot_variable_gen)
        generator_prof = cvx.multiply(-mef, generator_out_sum)

        system_emissions = cvx.sum(load_price + ess_net_price + variable_gen_prof + generator_prof)
        # CALCULATE LOCAL EMISSIONS
        # TODO look if there are Generators (test this)
        generators_exist = bool(sum([1 if tech.technology_type == 'Generator' else 0 for tech in self.technologies]))
        local_emissions = 0
        if generators_exist:
            fuel_emission_info = self.fuel_information['biodiesel']  # TODO get technology fuel type
            # calculate total fuel volumne
            total_fuel = sum([tech.fuel_costs() if tech.technology_type in ['ICE', 'DieselGenset'] else 0 for tech in self.technologies])
            local_emissions = total_fuel * fuel_emission_info['hhv'] * fuel_emission_info['co2ef']

        cost = system_emissions + local_emissions
        return {self.name: cost * annuity_scalar * self.dt * self.pareto_alpha}

    def update_pareto_alpha(self, new_alpha):
        """ 
         Args:
            mask (float): value for the alpha used in the pareto analysis

        """
        print(f'updated value to {new_alpha}')
        self.pareto_alpha = new_alpha

    def save_objectives(self, key, scenario_instance):
        """ Save the objectives, and sometimes the results of the scenario instance.

        Args:
            key (int): the alpha value used to solve the scenario_instance 
            scenario_instance (Scenario.Scenario): the solved scenario instance

        """
        pareto_values = self.pareto_values()
        # MicrogridResult.add_instance(f"emissions-pareto-{self.pareto_alpha}", scenario_instance, True)
        results = MicrogridResult(scenario_instance)
        results.collect_results()
        results.create_drill_down_dfs()
        results.calculate_cba()
        if key == 0:
            results.save_as_csv('Economic Only', True)
        if key == max(pareto_values):
            results.save_as_csv('Emissions Mostly', True)
        self.pareto_curve[key] = results.cost_benefit_analysis.npv
        total = results.drill_down_dict['total_emissions']
        # total.index = [str(key)]
        self.total_emissions = pd.concat([self.total_emissions, total])

    def timeseries_report(self):
        """ Summaries the optimization results for this Value Stream.

        Returns: A timeseries dataframe with user-friendly column headers that summarize the results
            pertaining to this instance

        """
        report = pd.DataFrame(index=self.marginal_emission_factor.index)
        report.loc[:, 'MEF'] = self.marginal_emission_factor
        return report

    def drill_down_reports(self, monthly_data=None, time_series_data=None, technology_summary=None, **kwargs):
        """ Calculates any service related dataframe that is reported to the user.

        Returns: dictionary of DataFrames of any reports that are value stream specific
            keys are the file name that the df will be saved with

        """
        df_dict = dict()
        if len(self.pareto_curve):
            df_dict['emissions_pareto_curve'] = self.build_pareto_curve()
            df_dict['total_emissions'] = self.total_emissions
        else:
            df_dict['total_emissions'] = self.emissions_report(kwargs['der_list'], time_series_data)
        return df_dict

    def build_pareto_curve(self):
        """ builds a table where the index is the alpha value and the columns are the corrsponding values
        per value stream and emission (for which the MEF corresponds to)
        """
        for key, df in self.pareto_curve.items():
            df.index = pd.Index(data=[key], name='Weight on Emissions')
        temp = pd.concat([*self.pareto_curve.values()])
        temp = pd.concat([temp, self.total_emissions], axis=1)
        return temp

    def calculate_system_emissions(self, time_series_data):
        """ Calculate indirect emissions
        
        Args:
            time_series_data (pd.DataFrame): timeseries results dataframe
        """
        net_load = time_series_data.loc[:, 'Net Load (kW)']
        return np.multiply(self.marginal_emission_factor, net_load).sum()

    def calculate_base_case_system_emissions(self, time_series_data):
        """ Cacluate the emissions of the load behind the point of interconnection with the bulk power
        system. This assumes the base case has no DERs or controllable loads installed.
        
        Args:
            time_series_data (pd.DataFrame): timeseries results dataframe
        """
        original_load = time_series_data.loc[:, 'Total Load (kW)']
        return np.multiply(self.marginal_emission_factor, original_load).sum()

    def calculate_local_emissions(self, der_list):
        """ Calculate direct emissions of the ders in DER_LIST
        
        Args:
            der_list (list): list of DERs 
        """
        generators_exist = bool(sum([1 if tech.technology_type == 'Generator' else 0 for tech in der_list]))
        local_emissions = 0
        if generators_exist:
            fuel_emission_info = self.fuel_information['biodiesel']  # TODO get fuel type from DER class
            # calculate total fuel volumne
            total_fuel = sum([tech.fuel_costs() if tech.technology_type in ['ICE', 'DieselGenset'] else 0 for tech in
                              der_list])
            local_emissions = total_fuel * fuel_emission_info['hhv'] * fuel_emission_info['co2ef']
        return local_emissions

    def emissions_report(self, der_list, time_series_data):
        """ Calculates emissions with DERs and without DERs (only Load). The difference in the two is the
        change in emissions.
        
        Args:
            time_series_data (pd.DataFrame): timeseries results dataframe
            der_list (list): list of DERs
        """
        original_local_emissions = 'Original Direct Emissions'
        original_system_emissions = 'Original Indirect Emissions'
        optimized_local_emisions = 'Direct Emissions'
        optimized_system_emisions = 'Indirect Emissions'
        dct_temp = {
            optimized_local_emisions: self.calculate_local_emissions(der_list),
            optimized_system_emisions: self.calculate_system_emissions(time_series_data),
            original_local_emissions: 0,  # TODO account for any existing local emissions
            original_system_emissions: self.calculate_base_case_system_emissions(time_series_data),
        }
        dct_temp['Change in Direct Emissions'] = dct_temp[optimized_local_emisions] - dct_temp[original_local_emissions]
        dct_temp['Change in Indirect Emissions'] = dct_temp[optimized_system_emisions] - dct_temp[original_system_emissions]
        return pd.DataFrame(dct_temp, index=pd.Index(data=[self.pareto_alpha], name='Carbon Value'))
