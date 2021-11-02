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
Rotating Generator sizing class

This Python class contains methods and attributes specific for technology analysis within StorageVet.
"""
import cvxpy as cvx
from dervet.MicrogridDER.DERExtension import DERExtension
from dervet.MicrogridDER.ContinuousSizing import ContinuousSizing
from storagevet.Technology.RotatingGenerator import RotatingGenerator
from storagevet.ErrorHandling import *
import numpy as np


class RotatingGeneratorSizing(RotatingGenerator, DERExtension, ContinuousSizing):
    """ An rotating generator, with sizing optimization

    """

    def __init__(self, params):
        """ Initialize all technology with the following attributes.

        Args:
            params (dict): Dict of parameters for initialization
        """
        TellUser.debug(f"Initializing {__name__}")
        RotatingGenerator.__init__(self, params)
        DERExtension.__init__(self, params)
        ContinuousSizing.__init__(self, params)
        self.max_rated_power = params['max_rated_capacity']
        self.min_rated_power = params['min_rated_capacity']
        if not self.rated_power:
            self.rated_power = cvx.Variable(integer=True, name=f'{self.name} rating')
            self.size_constraints += [cvx.NonPos(-self.rated_power)]
            if self.min_rated_power:
                self.size_constraints += [cvx.NonPos(self.min_rated_power - self.rated_power)]
            if self.max_rated_power:
                self.size_constraints += [cvx.NonPos(self.rated_power - self.max_rated_power)]

    def discharge_capacity(self, solution=False):
        """

        Returns: the maximum discharge that can be attained

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

    def get_capex(self, solution=False):
        capex = super().get_capex()
        if solution:
            try:
                capex = capex.value
            except AttributeError:
                capex = capex
        return capex

    def constraints(self, mask):
        """ Builds the master constraint list for the subset of timeseries data being optimized.

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set

        Returns:
            A list of constraints that corresponds the generator's physical constraints and its service constraints
        """
        # parent constraints
        parent_constraints = super().constraints(mask)
        # drop the last constraint from the parent class when sizing
        constraint_list = parent_constraints[:-1]
        if not self.being_sized():
            # add the last constraint from the parent class
            constraint_list += [parent_constraints[-1]]
        else:
            power_out = self.variables_dict['elec']
            on = self.variables_dict['on']
            # cover the constraint that was removed
            if self.max_rated_power:
                constraint_list += [cvx.NonPos(power_out - self.max_rated_power * self.n * on)]
            constraint_list += [cvx.NonPos(power_out - self.discharge_capacity())]

        constraint_list += self.size_constraints
        return constraint_list

    def objective_function(self, mask, annuity_scalar=1):
        """ Generates the objective function related to a technology. Default includes O&M which can be 0

        Args:
            mask (Series): Series of booleans used, the same length as case.power_kw
            annuity_scalar (float): a scalar value to be multiplied by any yearly cost or benefit that helps capture the cost/benefit over
                        the entire project lifetime (only to be set iff sizing)

        Returns:
            self.costs (Dict): Dict of objective costs
        """
        costs = super().objective_function(mask, annuity_scalar)
        costs.update(self.sizing_objective())
        return costs

    def set_size(self):
        """ Save value of size variables of DERs

        """
        self.rated_power = self.name_plate_capacity(True)

    def sizing_summary(self):
        """

        Returns: A dictionary describe this DER's size and captial costs.

        """
        sizing_results = {
            'DER': self.name,
            'Power Capacity (kW)': self.name_plate_capacity(True),
            'Capital Cost ($)': self.capital_cost_function[0],
            'Capital Cost ($/kW)': self.capital_cost_function[1],
            'Quantity': self.n}
        return sizing_results

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

    def sizing_error(self):
        """

        Returns: True if there is an input error

        """
        if self.min_rated_power < self.p_min:
            TellUser.error(f'{self.unique_tech_id()} would not be able to have a rating less than {self.p_min}. ' +
                           f'Please update min_rated_power to reflect this constraint.')
            return True
        return False

    def replacement_cost(self):
        """

        Returns: the cost of replacing this DER

        """
        return np.dot(self.replacement_cost_function, [self.n, self.discharge_capacity(True)])

    def max_p_schedule_down(self):
        # ability to provide regulation down through discharging less
        if isinstance(self.rated_power, cvx.Variable):
            max_discharging_range = np.inf
        else:
            max_discharging_range = self.discharge_capacity() - self.p_min
        return max_discharging_range

    def max_power_out(self):
        """

        Returns: the maximum power that can be outputted by this genset

        """
        power_out = self.n * self.rated_power
        return power_out

