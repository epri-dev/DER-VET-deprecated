"""
ICE Sizing class

This Python class contains methods and attributes specific for technology analysis within StorageVet.
"""

__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'mevans@epri.com']
__version__ = 'beta'  # beta version

import cvxpy as cvx
from MicrogridDER.CombustionTurbine import CT
import storagevet.Library as Lib
from ErrorHandelling import *


class CHP(CT):
    """ Combined Heat and Power (CHP) Technology, with sizing optimization

    """

    def __init__(self, params):
        """ Initialize all technology with the following attributes.

        Args:
            params (dict): Dict of parameters for initialization
        """
        TellUser.debug(f"Initializing {__name__}")
        # base class is CT
        super().__init__(params)

        # overrides
        self.tag = 'CHP'
        self.is_hot = True

        self.electric_heat_ratio = params['electric_heat_ratio']    # elec/heat (generation)

    def initialize_variables(self, size):
        # rotating generation
        super().initialize_variables(size)
        # plus heat
        self.variables_dict.update({
            'heat': cvx.Variable(shape=size, name=f'{self.name}-heat', nonneg=True),
        })

    def constraints(self, mask):
        constraint_list = super(CHP, self).constraints(mask)
        elec = self.variables_dict['elect']
        heat = self.variables_dict['heat']

        constraint_list += [cvx.NonPos(heat * self.electric_heat_ratio - elec)]

    def timeseries_report(self):

        tech_id = self.unique_tech_id()
        results = super().timeseries_report()

        results[tech_id + ' Heat Generation (kW)'] = self.variables_df['heat']

        return results

