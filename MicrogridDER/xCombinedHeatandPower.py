"""
CHP (Combined Heat and Power)
    - natural-gas fuel prices from monthly CSV
    - also includes heat recovery
"""

__author__ = 'Andrew Etringer'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani', 'Micah Botkin-Levy', 'Yekta Yazar']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Evan Giarta', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'egiarta@epri.com', 'mevans@epri.com']
__version__ = '2.1.1.1'

import cvxpy as cvx
import numpy as np
import pandas as pd
from .CombustionTurbine import CT

# thermal load unit is BTU/h
BTU_H_PER_KW = 3412.14  # 1kW = 3412.14 BTU/h

class CHP(CT):
    """ Combined Heat and Power (CHP) Technology

    """

    def __init__(self, params):
        """ Initialize all technology with the following attributes.

        Args:
            params (dict): Dict of parameters for initialization
        """

        # base class is CT
        super().__init__(params)

        # overrides
        self.tag = 'CHP'
        self.is_hot = True

        self.electric_heat_ratio = params['electric_heat_ratio']    # elec/heat (generation)
        self.startup = params['startup']                            # boolean
        self.p_startup = params['p_startup']                        # $
        self.electric_ramp_rate = params['electric_ramp_rate']      # MW/min # TODO use this ? --AE

    def grow_drop_data(self, years, frequency, load_growth):

        self.thermal_load = Lib.fill_extra_data(self.thermal_load, years, load_growth, frequency)
        self.thermal_load = Lib.drop_extra_data(self.thermal_load, years)

    def initialize_variables(self, size):

        super().initialize_variables(size)

        self.variables_dict.update({
            'heat': cvx.Variable(shape=size, name=f'{self.name}-heatP', nonneg=True),
            'udis': cvx.Variable(shape=size, name=f'{self.name}-udis'), # can go either up or down
        })

        self.variable_names = self.variables_dict.keys()

    def constraints(self, mask):

        elec = self.variables_dict['elect']
        heat = self.variables_dict['heat']

        constraint_list = [cvx.NonPos(heat * self.electric_heat_ratio - elec)]

        # add constraints from parent class after
        constraint_list += [i for i in super().constraints(mask)]

    def timeseries_report(self):

        tech_id = self.unique_tech_id()
        results = super().timeseries_report()

        results[tech_id + ' Heat Generation (kW)'] = self.variables_df['heat']

        return results

    def objective_function(self, mask, annuity_scalar=1):

        costs = super().objective_function(mask, annuity_scalar)

        # add startup objective costs
        if self.startup:
            # TODO this is NOT how you would calculate the start up cost of a CHP. pls look at formulation doc and revise --HN
            # TODO This can be easily fixed, but let's do it some other time, when everything else works --AC
            costs[self.name + 'startup': cvx.sum(self.variables_dict['on']) * self.p_startup * annuity_scalar]
