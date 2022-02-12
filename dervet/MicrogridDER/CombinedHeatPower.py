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
CHP Sizing class

This Python class contains methods and attributes specific for technology analysis within StorageVet.
"""
import cvxpy as cvx
import numpy as np
from dervet.MicrogridDER.CombustionTurbine import CT
import storagevet.Library as Lib
from storagevet.ErrorHandling import *


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
        self.max_steam_ratio = params['max_steam_ratio']           # steam/hotwater relative ratio
        # time series inputs
        self.site_steam_load = params.get('site_steam_load')    # input as MMBtu/hr, but converted to kW in DERVETParams.py
        self.site_hotwater_load = params.get('site_hotwater_load')   # input as MMBtu/hr, but converted to kW in DERVETParams.py
        # thermal site load booleans
        self.site_thermal_load_exists = (self.site_steam_load is not None and self.site_hotwater_load is not None)
        self.steam_only = False
        self.hotwater_only = False
        if self.site_thermal_load_exists:
            self.steam_only = (self.site_hotwater_load.max() == 0)
            self.hotwater_only = (self.site_steam_load.max() == 0)


    def grow_drop_data(self, years, frequency, load_growth):
        if self.site_thermal_load_exists:
            self.site_steam_load = Lib.fill_extra_data(self.site_steam_load, years, load_growth, frequency)
            self.site_steam_load = Lib.drop_extra_data(self.site_steam_load, years)
            self.site_hotwater_load = Lib.fill_extra_data(self.site_hotwater_load, years, load_growth, frequency)
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

        # electric energy and heat (steam + hotwater) energy generated are proportional
        #   and defined by electric_heat_ratio
        constraint_list += [cvx.Zero(elec - self.electric_heat_ratio * (steam  + hotwater))]

        # to ensure that CHP never produces more steam than it can (no excess steam)
        if not self.steam_only and not self.hotwater_only:
            constraint_list += [cvx.NonPos(steam - self.max_steam_ratio * hotwater)]

        # to ensure that the upper limit on CHP size in the size optimization
        #     will be the smallest system that can meet both howater and steam loads
        #     use smallest_size_system_needed()
        if self.being_sized() and self.site_thermal_load_exists:
            constraint_list += [cvx.NonPos(elec - self.smallest_size_system_needed())]

        return constraint_list

    def get_steam_generated(self, mask):
        # thermal power is recovered in a CHP plant whenever electric power is being generated
        # it is proportional to the electric power generated at a given time
        return self.variables_dict['steam']

    def get_hotwater_generated(self, mask):
        # thermal power is recovered in a CHP plant whenever electric power is being generated
        # it is proportional to the electric power generated at a given time
        return self.variables_dict['hotwater']

    def smallest_size_system_needed(self):
        """ Returns the smallest sized system (in kW) that can mmet the thermal load
              (both hotwater and steam loads).
            It is used in a constraint to limit the size of CHP.
            It checks each time in the time series.
        """
        if self.steam_only or self.hotwater_only:
            minimum_size_needed = (self.site_steam_load + self.sitte_hotwater_load).max()
        else:
            site_thermal_load_ratio = self.site_steam_load / self.site_hotwater_load
            ul_mask = (site_thermal_load_ratio > self.max_steam_ratio)
            size_needed_to_meet_thermal_loads = np.where(ul_mask,
                # (where ul_mask is True)
                #     steam load is too large, so the system throws away hotwater.
                #     thus the total thermal energy is steam load plus the amount of
                #     hotwater produced as a results of steam generation
                self.site_steam_load + self.site_steam_load / self.max_steam_ratio,
                # (where ul_mask is False)
                self.site_steam_load + self.site_hotwater_load
            )
            minimum_size_needed = size_needed_to_meet_thermal_loads.max()

        minimum_size_needed = self.electric_heat_ratio * minimum_size_needed
        TellUser.warning(f'CHP constraint: smallest_size_system_needed (kW) = {minimum_size_needed}')

        return minimum_size_needed

    def timeseries_report(self):

        tech_id = self.unique_tech_id()
        results = super().timeseries_report()

        results[tech_id + ' Steam Generation (kW)'] = self.variables_df['steam']
        results[tech_id + ' Hot Water Generation (kW)'] = self.variables_df['hotwater']
        #if self.site_thermal_load_exists:
        #    results['THERMAL LOAD:' + ' Site Steam Thermal Load (kW)'] = self.site_steam_load
        #    results['THERMAL LOAD:' + ' Site Hot Water Thermal Load (kW)'] = self.site_hotwater_load

        return results

    def objective_function(self, mask, annuity_scalar=1):

        costs = super().objective_function(mask, annuity_scalar)

#        # add startup objective costs
#        if self.startup:
#            # TODO this is NOT how you would calculate the start up cost of a CHP. pls look at formulation doc and revise --HN
#            # TODO This can be easily fixed, but let's do it some other time, when everything else works --AC
#            costs[self.name + 'startup': cvx.sum(self.variables_dict['on']) * self.p_startup * annuity_scalar]

        return costs
