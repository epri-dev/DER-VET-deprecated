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
        #   ( BTU/hr of cooling / BTU/hr of [electricity|natural_gas|heat] )
        self.cop = params['coefficient_of_performance']
        self.power_source = params['power_source']  # electricity, natural_gas, heat

        self.rated_power = KW_PER_TON * params['rated_capacity']  # tons/chiller

        self.ccost = params['ccost']  # $/chiller
        self.ccost_ton = params['ccost_ton'] / KW_PER_TON  # $/tons-chiller
        #self.capital_cost_function = [params['ccost'],
        #                              params['ccost_ton']]

        self.fixed_om_cost = params['fixed_om_cost'] / KW_PER_TON  # $ / ton-year

        self.n = params['n']  # number of chillers (integer)

        self.is_cold = True
        self.is_fuel = True

        # time series inputs
        self.site_cooling_load = params.get('site_cooling_load')    # BTU/hr

        self.max_rated_power = KW_PER_TON * params['max_rated_capacity']  # tons/chiller
        self.min_rated_power = KW_PER_TON * params['min_rated_capacity'] # tons/chiller
        if not self.rated_power:
            self.rated_power = cvx.Variable(integer=True, name=f'{self.name}rating')
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
        self.variables_dict = {
            'cold': cvx.Variable(shape=size, name=f'{self.name}-coldP', nonneg=True),
        }

    #def discharge_capacity(self, solution=False):
    #def name_plate_capacity(self, solution=False):


    def constraints(self, mask, **kwargs):
        constraint_list = super().constraints(mask)
        cold = self.variables_dict['cold']

        if self.power_source == 'electricity':
            # TODO -- add the additional electricl load
            constraint_list += [cvx.Zero(cold / self.cop)]

        elif self.power_source == 'natural_gas':
            # TODO -- add the additional NG use
            constraint_list += [cvx.Zero(cold / self.cop)]

        elif self.power_source == 'heat':
            # TODO -- add the additional heat load
            constraint_list += [cvx.Zero(cold / self.cop)]

        constraint_list += self.size_constraints
        return constaint_list

    def objective_function(self, mask, annuity_scalar=1):
        costs = super().objective_function(mask, annuity_scalar)
        costs.update(self.sizing_objective())
        return costs

    #def update_for_evaluation(self, input_dict):

    #def set_size(self):
    #def sizing_summary(self):
    #def sizing_error(self):
    #def replacement_cost(self):
    #def max_p_schedule_down(self):
    #def max_power_out(self):

    def get_capex(self):
        """ Returns the capex of a given technology
        """
        return self.capital_cost_function

