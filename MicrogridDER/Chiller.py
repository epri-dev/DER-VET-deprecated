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
import storagevet.Library as Lib
from storagevet.Technology.DistributedEnergyResource import DER
from MicrogridDER.DERExtension import DERExtension
from MicrogridDER.ContinuousSizing import ContinuousSizing
from ErrorHandelling import *


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

        self.technology_type = 'thermal'
        self.tag = 'Chiller'

        # cop is the ratio of cooling provided to the power input
        #   ( BTU/hr of cooling / BTU/hr of [electricity|natural gas|heat] )
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
            self.fuel_type = 'gas'
            self.is_fuel = True
        else:
            self.fuel_type = None

        self.is_cold = True

        # For now, no, chiller just serves the cooling load and consumes some power to do so.
        # Since the cooling load is fixed, the chiller has no opportunity to provide market services.
        self.can_participate_in_market_services = False

        # time series inputs
        self.site_cooling_load = params.get('site_cooling_load')    # BTU/hr

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
            self.site_cooling_load = Lib.fill_extra_data(self.site_cooling_load, years, 0, frequency)
            # TODO use a non-zero growth rate of cooling load? --AE
            self.site_cooling_load = Lib.drop_extra_data(self.site_cooling_load, years)

    def initialize_variables(self, size):
        # TODO -- add rated_capacity sizing optimization variable here, when sizing
        # NOTE: this is handled by size_constraints
        self.variables_dict = {
            'cold': cvx.Variable(shape=size, name=f'{self.name}-coldP', nonneg=True),
        }

    def constraints(self, mask, **kwargs):
        constraint_list = super().constraints(mask)
        cold = self.variables_dict['cold']

        # limit the cold power of the chiller to at most its rated power
        constraint_list += [cvx.NonPos(cold - self.rated_power)]

        ## conditional constraints that depend on the power source of the chiller
        #if self.power_source == 'electricity':
        #    # TODO -- add the additional electricl load
        #    constraint_list += [cvx.Zero(cold / self.cop)]
        #
        #elif self.power_source == 'natural gas':
        #    # TODO -- add the additional NG use
        #    constraint_list += [cvx.Zero(cold / self.cop)]
        #
        #elif self.power_source == 'heat':
        #    # TODO -- add the additional heat load
        #    constraint_list += [cvx.Zero(cold / self.cop)]

        constraint_list += self.size_constraints
        return constraint_list

    def get_cold_recovered(self, mask):
        # thermal power is recovered in a Chiller whenever electric power is being generated
        # it is proportional to the electric power generated at a given time
        return self.variables_dict['cold']


    def objective_function(self, mask, annuity_scalar=1):
        # TODO -- this needs fixes
        costs = super().objective_function(mask, annuity_scalar)
        costs.update(self.sizing_objective())

        # TODO -- fix this ? use power_in ?
        total_out = self.variables_dict['cold']

        costs.update({
            self.name + ' fixed': self.fixed_om * annuity_scalar,
            self.name + ' variable': cvx.sum(self.variable_om * self.dt * annuity_scalar * total_out)
        })

        if self.power_source == 'electricity':
            print('')
        elif self.power_source == 'natural gas':
            # add fuel cost in $/kWh
            fuel_exp = cvx.sum(total_out * self.cop * self.fuel_cost * self.dt * annuity_scalar)
            costs.update({self.name + ' fuel_cost': fuel_exp})
        elif self.power_source == 'heat':
            print('')

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
        if variable_cost is not None:
            self.fixed_om = fixed_om_cost

        ccost_kw = input_dict.get('ccost_kW')
        if ccost_kw is not None:
            self.capital_cost_function[1] = ccost_kw

    def discharge_capacity(self, solution=False):
        """ Returns: the maximum discharge that can be attained
        """
        if not solution or not self.being_sized():
            return super().discharge_capacity()
        else:
            try:
                rated_power = self.rated_power.value
            except AttributeError:
                rated_power = self.rated_power
            return rated_power * self.n

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

    def max_power_out(self):
        """ Returns: the maximum power that can be outputted by this genset
        """
        power_out = self.n * self.rated_power
        return power_out

    def get_capex(self):
        """ Returns the capex of a given technology
        """
        return np.dot(self.capital_cost_function, [self.n, self.discharge_capacity()])

    #def qualifying_capacity(self, event_length):

    def timeseries_report(self):
        tech_id = self.unique_tech_id()
        results = super().timeseries_report()
        # results = pd.DataFrame(index=self.variables_df.index)

        results[tech_id + ' Cold Generation (kW)'] = self.variables_df['cold']
        if self.site_cooling_load is not None:
            results[tech_id + ' Site Cooling Thermal Load (BTU/hr)'] = self.site_cooling_load

    # def proforma_report(self, opt_years, results):
        # TODO -- fill this in

    #def get_discharge(self, mask):


