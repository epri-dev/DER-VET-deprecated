"""
CHP Sizing class

This Python class contains methods and attributes specific for technology analysis within StorageVet.
"""

__author__ = 'Andrew Etringer'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'mevans@epri.com']
__version__ = 'beta'  # beta version

import cvxpy as cvx
import numpy as np
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

        self.electric_ramp_rate = params['electric_ramp_rate']      # MW/min # TODO this is not being used? --AE
        self.electric_heat_ratio = params['electric_heat_ratio']    # elec/heat (generation)
        self.max_steam_ratio = params['max_steam_ratio']           # steam/hotwater relative ratio
        # time series inputs
        self.site_steam_load = params.get('site_steam_load')    # BTU/hr
        self.site_hotwater_load = params.get('site_hotwater_load')    # BTU/hr

    def grow_drop_data(self, years, frequency, load_growth):
        if self.site_steam_load is not None:
            self.site_steam_load = Lib.fill_extra_data(self.site_steam_load, years, 0, frequency)
            # TODO use a non-zero growth rate of steam load? --AE
            self.site_steam_load = Lib.drop_extra_data(self.site_steam_load, years)
        if self.site_hotwater_load is not None:
            self.site_hotwater_load = Lib.fill_extra_data(self.site_hotwater_load, years, 0, frequency)
            # TODO use a non-zero growth rate of hotwater load? --AE
            self.site_hotwater_load = Lib.drop_extra_data(self.site_hotwater_load, years)

    def initialize_variables(self, size):
        # rotating generation
        super().initialize_variables(size)
        # plus heat (steam and hotwater)
        self.variables_dict.update({
            'steam': cvx.Variable(shape=size, name=f'{self.name}-steamP', nonneg=True),
            'hotwater': cvx.Variable(shape=size, name=f'{self.name}-hotwaterP', nonneg=True),
        })

    def constraints(self, mask):
        constraint_list = super().constraints(mask)
        elec = self.variables_dict['elec']
        steam = self.variables_dict['steam']
        hotwater = self.variables_dict['hotwater']

        # to ensure that CHP never produces more steam than it can
        constraint_list += [cvx.NonPos(steam - self.max_steam_ratio * hotwater)]

        constraint_list += [cvx.Zero((steam + hotwater) * self.electric_heat_ratio - elec)]

        # to ensure that the upper limit on CHP size in the size optimization
        #     will be the smallest system that can meet both hotwater and steam loads
        if self.being_sized():
            constraint_list += [cvx.NonPos(elec - self.size_upper_limit())]

        return constraint_list

    def get_steam_recovered(self, mask):
        # thermal power is recovered in a CHP plant whenever electric power is being generated
        # it is proportional to the electric power generated at a given time
        return self.variables_dict['steam']

    def get_hotwater_recovered(self, mask):
        # thermal power is recovered in a CHP plant whenever electric power is being generated
        # it is proportional to the electric power generated at a given time
        return self.variables_dict['hotwater']

    def size_upper_limit(self):
        # determine the smallest sized system that can meet both hotwater and steam loads
        site_thermal_load_ratio = self.site_steam_load / self.site_hotwater_load
        ul_mask = (site_thermal_load_ratio > self.max_steam_ratio)
        size_needed_to_meet_thermal_loads = np.where(ul_mask,
            # (where ul_mask is true)
            #   steam load is too large, so the system throws away hotwater.
            #   thus the total thermal energy is steam load plus the amount of hotwater produced
            #   as a result of steam generation
            self.electric_heat_ratio*(self.site_steam_load / self.max_steam_ratio + self.site_steam_load),
            # (where ul_mask is false)
            self.electric_heat_ratio*(self.site_steam_load + self.site_hotwater_load)
        )
        upper_limit = size_needed_to_meet_thermal_loads.max()
        print(f'CHP size_upper_limit = {upper_limit}')
        return upper_limit

    def timeseries_report(self):

        tech_id = self.unique_tech_id()
        results = super().timeseries_report()

        results[tech_id + ' Steam Generation (kW)'] = self.variables_df['steam']
        results[tech_id + ' Hot Water Generation (kW)'] = self.variables_df['hotwater']
        if self.site_steam_load is not None:
            results[tech_id + ' Site Steam Thermal Load (BTU/hr)'] = self.site_steam_load
        if self.site_hotwater_load is not None:
            results[tech_id + ' Site Hot Water Thermal Load (BTU/hr)'] = self.site_hotwater_load

        return results

    def objective_function(self, mask, annuity_scalar=1):

        costs = super().objective_function(mask, annuity_scalar)

#        # add startup objective costs
#        if self.startup:
#            # TODO this is NOT how you would calculate the start up cost of a CHP. pls look at formulation doc and revise --HN
#            # TODO This can be easily fixed, but let's do it some other time, when everything else works --AC
#            costs[self.name + 'startup': cvx.sum(self.variables_dict['on']) * self.p_startup * annuity_scalar]

        return costs
