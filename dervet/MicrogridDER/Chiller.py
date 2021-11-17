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
Chiller Sizing class

A Chiller can be powered by:
  - electricity (electric chiller)
  - natural gas (natural gas powered chiller)
  - heat (from a local heat source: CHP, boiler, etc.)

A Chiller can serve a cooling load.
A Chiller cannot serve a heating load, nor an electric load.
"""

__author__ = 'Andrew Etringer'
__copyright__ = 'Copyright 2020. Electric Power Research Institute (EPRI). All Rights Reserved.'
__license__ = 'EPRI'
__maintainer__ = ['Andrew Etringer']
__email__ = ['aetringer@epri.com']
__version__ = 'beta'  # beta version

import cvxpy as cvx
import numpy as np
import pandas as pd
import storagevet.Library as Lib
from storagevet.Technology.DistributedEnergyResource import DER
from dervet.MicrogridDER.DERExtension import DERExtension
from dervet.MicrogridDER.ContinuousSizing import ContinuousSizing
from storagevet.ErrorHandling import *


class Chiller(DER, ContinuousSizing, DERExtension):
    """ A Chiller technology, with sizing optimization

    """

    def __init__(self, params):
        """ Initialize all technology with the following attributes.

        Args:
            params (dict): Dict of parameters for initialization
        """
        TellUser.debug(f"Initializing {__name__}")
        # create generic technology object
        DER.__init__(self, params)
        ContinuousSizing.__init__(self, params)
        DERExtension.__init__(self, params)

        KW_PER_TON = 3.5168525  # unit conversion (1 ton in kW)

        self.technology_type = 'Thermal'
        self.tag = 'Chiller'

        # cop is the ratio of cooling provided to the power input
        #   ( Btu/hr of cooling / Btu/hr of [electricity|natural gas|heat] )
        self.cop = params['coefficient_of_performance']
        self.power_source = params['power_source']  # electricity, natural gas, heat

        self.rated_power = KW_PER_TON * params['rated_capacity']  # tons/chiller

        self.ccost = params['ccost']  # $/chiller
        self.ccost_kW = params['ccost_ton'] / KW_PER_TON  # $/tons-chiller
        self.capital_cost_function = [self.ccost, self.ccost_kW]

        self.fixed_om = params['fixed_om_cost'] / KW_PER_TON  # $ / ton-year

        # since there is no min_power input for chillers, set the number of chillers to 1
        self.n = 1 # number of chillers (integer)

        # let the power_source input control the fuel_type
        if self.power_source == 'natural gas':
            # a natural-gas-powered chiller
            self.fuel_type = 'gas'
            self.is_fuel = True
        elif self.power_source == 'heat':
            # a chiller powered by a local heat source (CHP, Boiler, etc.)
            self.is_hot = True
            self.fuel_type = None
            self.is_fuel = False
        elif self.power_source == 'electricity':
            # an electric chiller
            self.is_electric = True
            self.fuel_type = None
            self.is_fuel = False

        self.is_cold = True

        # For now, no, chiller just serves the cooling load and consumes some power to do so.
        # Since the cooling load is fixed, the chiller has no opportunity to provide market services.
        self.can_participate_in_market_services = False

        # time series inputs
        self.site_cooling_load = params.get('site_cooling_load')    # input as tons, but converted to kW in DERVETParams.py

        self.max_rated_power = KW_PER_TON * params['max_rated_capacity']  # tons/chiller
        self.min_rated_power = KW_PER_TON * params['min_rated_capacity'] # tons/chiller
        if not self.rated_power:
            self.rated_power = cvx.Variable(integer=True, name=f'{self.name} rating')
            self.size_constraints += [cvx.NonPos(-self.rated_power)]
            if self.min_rated_power:
                self.size_constraints += [cvx.NonPos(self.min_rated_power - self.rated_power)]
            if self.max_rated_power:
                self.size_constraints += [cvx.NonPos(self.rated_power - self.max_rated_power)]

    def grow_drop_data(self, years, frequency, load_growth):
        if self.site_cooling_load is not None:
            self.site_cooling_load = Lib.fill_extra_data(self.site_cooling_load, years, load_growth, frequency)
            self.site_cooling_load = Lib.drop_extra_data(self.site_cooling_load, years)

    def initialize_variables(self, size):
        self.variables_dict = {
            'cold': cvx.Variable(shape=size, name=f'{self.name}-coldP', nonneg=True),
        }

    def get_charge(self, mask):
        # when powered by electricity, return the electrical load
        #   this is cooling-load / cop
        if self.is_electric:
            return cvx.Parameter(value=self.site_cooling_load[mask].values / self.cop, shape=sum(mask), name=f'{self.name}-elecP')
        else:
            # returns all zeroes (from base class)
            return super().get_charge(mask)

    def constraints(self, mask, **kwargs):
        constraint_list = super().constraints(mask)
        cold = self.variables_dict['cold']

        # limit the cold power of the chiller to at most its rated power
        constraint_list += [cvx.NonPos(cold - self.rated_power)]

        constraint_list += self.size_constraints
        return constraint_list

    def get_cold_generated(self, mask):
        # thermal power is recovered in a Chiller whenever electric power is being generated
        # it is proportional to the electric power generated at a given time
        return self.variables_dict['cold']

    def objective_function(self, mask, annuity_scalar=1):
        costs = super().objective_function(mask, annuity_scalar)
        costs.update(self.sizing_objective())

        total_out = self.variables_dict['cold']

        costs.update({
            self.name + ' fixed': self.fixed_om * annuity_scalar,
            self.name + ' variable': cvx.sum(self.variable_om * self.dt * annuity_scalar * total_out)
        })

        print(f'{self.name}--power_source: {self.power_source}')
        #if self.power_source == 'electricity':
        #    # this manifests as an increase in the electricity bill and is handled in storagevet POI.
        #    # agg_power_flows_in accumulates elec power from a chiller with get_charge()
        if self.power_source == 'natural gas':
            # add fuel cost in $/kWh
            fuel_exp = cvx.sum(total_out * self.cop * self.fuel_cost * self.dt * annuity_scalar)
            costs.update({self.name + ' fuel_cost': fuel_exp})
        #elif self.power_source == 'heat':
        #    # the chiller consumes heat
        #    # the fuel cost should show up in the boiler/CHP's fuel cost output.
        #    # add to thermal energy balance (hotwater) in dervetPOI

        return costs

    def update_for_evaluation(self, input_dict):
        """ Updates price related attributes with those specified in the input_dictionary

        Args:
            input_dict: hold input data, keys are the same as when initialized

        """
        super().update_for_evaluation(input_dict)

        variable_cost = input_dict.get('variable_om_cost')
        if variable_cost is not None:
            self.variable_om = variable_cost

        fixed_om_cost = input_dict.get('fixed_om_cost')
        if fixed_om_cost is not None:
            self.fixed_om = fixed_om_cost

        fuel_cost = input_dict.get(f'fuel_price_{self.fuel_type}')
        if fuel_cost is not None:
            self.fuel_cost = fuel_cost

    def name_plate_capacity(self, solution=False):
        """ Returns the value of 1 generator in a set of generators

        Args:
            solution:

        Returns:

        """
        if not solution:
            return self.rated_power
        else:
            try:
                rated_power = self.rated_power.value
            except AttributeError:
                rated_power = self.rated_power
            return rated_power

    def set_size(self):
        """ Save value of size variables of DERs
        """
        self.rated_power = self.name_plate_capacity(True)

    def sizing_summary(self):
        """ Returns: A dictionary describe this DER's size and captial costs.
        """
        sizing_results = {
            'DER': self.name,
            'Power Capacity (kW)': self.name_plate_capacity(True),
            'Capital Cost ($)': self.capital_cost_function[0],
            'Capital Cost ($/kW)': self.capital_cost_function[1],
            'Quantity': self.n}
        return sizing_results

    #def sizing_error(self):
        # handled in the parent class  (will NOT error)
        # min_power is not specified with this technology,
        #   meaning we allow chillers to operate anywhere between 0 tons and their rated capacity

    def replacement_cost(self):
        """ Returns: the cost of replacing this DER
        """
        return np.dot(self.replacement_cost_function, [self.n, self.discharge_capacity(True)])

    def max_p_schedule_down(self):
        # TODO -- is this needed in a thermal technology ?
        # ability to provide regulation down through discharging less
        if isinstance(self.rated_power, cvx.Variable):
            max_discharging_range = np.inf
        else:
            max_discharging_range = self.discharge_capacity()
        return max_discharging_range

    def get_capex(self, **kwargs):
        """ Returns the capex of a given technology
        """
        return np.dot(self.capital_cost_function, [self.n, self.discharge_capacity()])

    def timeseries_report(self):
        tech_id = self.unique_tech_id()
        results = super().timeseries_report()
        # results = pd.DataFrame(index=self.variables_df.index)

        results[tech_id + ' Cold Generation (kW)'] = self.variables_df['cold']
        if self.site_cooling_load is not None:
            results[tech_id + ' Site Cooling Thermal Load (kW)'] = self.site_cooling_load

        return results

    def proforma_report(self, apply_inflation_rate_func, fill_forward_func, results):
        #super().proforma_report()
        # TODO -- fill this in, using an example from the cba code
        # FIXME: is this right?
        if not self.zero_column_name():
            return None

        pro_forma = pd.DataFrame({self.zero_column_name(): -self.get_capex(solution=True)}, index=['CAPEX Year'])

        return pro_forma
