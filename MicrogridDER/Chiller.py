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

        self.technology_type = 'thermal'
        self.tag = 'Chiller'

        # cop is the ratio of cooling provided to the power input
        #   ( BTU/hr of cooling / BTU/hr of [electricity|natural_gas|heat] )
        self.cop = params['coefficient_of_performance']
        self.power_source = params['power_source']  # electricity, natural_gas, heat

        self.rated_capacity = params['rated_capacity']  # tons/chiller

        self.ccost = params['ccost']  # $/chiller
        self.ccost_ton = params['ccost_ton']  # $/tons-chiller
        #self.capital_cost_function = [params['ccost'],
        #                              params['ccost_ton']]

        self.fixed_om_cost = params['fixed_om_cost']  # $ / ton-year

        self.n = params['n']  # number of chillers (integer)

        self.is_cold = True
        self.is_fuel = True

        # time series inputs
        self.site_cooling_load = params.get('site_cooling_load')    # BTU/hr


    def grow_drop_data(self, years, frequency, load_growth):
        if self.site_cooling_load is not None:
            self.site_cooling_load = Lib.fill_extra_data(self.site_cooling_load, years, 0, frequency)
            # TODO use a non-zero growth rate of cooling load? --AE
            self.site_cooling_load = Lib.drop_extra_data(self.site_cooling_load, years)

    def initialize_variables(self, size):
    #    # rotating generation
    #    super().initialize_variables(size)
        # plus cooling
        self.variables_dict.update({
            'cold': cvx.Variable(shape=size, name=f'{self.name}-coldP', nonneg=True),
        })

    #def discharge_capacity(self, solution=False):
    #def name_plate_capacity(self, solution=False):


    #def constraints(self, mask, **kwargs):
    #def objective_function(self, mask, annuity_scalar=1):
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

