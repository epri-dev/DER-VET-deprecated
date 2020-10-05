"""
Intermittent Resource sizing class

This Python class contains methods and attributes specific for technology analysis within StorageVet.
"""

__author__ = 'Andrew Etringer and Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'mevans@epri.com']
__version__ = 'beta'  # beta version

import cvxpy as cvx
from MicrogridDER.DERExtension import DERExtension
from MicrogridDER.ContinuousSizing import ContinuousSizing
from storagevet.Technology import PVSystem
from ErrorHandelling import *
import numpy as np


class IntermittentResourceSizing(PVSystem.PV, DERExtension, ContinuousSizing):
    """ An intermittent resource, with sizing optimization

    """

    def __init__(self, params):
        """ Initialize all technology with the following attributes.

        Args:
            params (dict): Dict of parameters for initialization
        """
        TellUser.debug(f"Initializing {__name__}")
        PVSystem.PV.__init__(self, params)
        DERExtension.__init__(self, params)
        ContinuousSizing.__init__(self, params)

        self.curtail = params['curtail']
        self.max_rated_capacity = params['max_rated_capacity']
        self.min_rated_capacity = params['min_rated_capacity']
        if not self.rated_capacity:
            self.rated_capacity = cvx.Variable(name=f'{self.name}rating', integer=True)
            self.inv_max = self.rated_capacity
            self.size_constraints += [cvx.NonPos(-self.rated_capacity)]
            if self.min_rated_capacity:
                self.size_constraints += [cvx.NonPos(self.min_rated_capacity - self.rated_capacity)]
            if self.max_rated_capacity:
                self.size_constraints += [cvx.NonPos(self.rated_capacity - self.max_rated_capacity)]

    def get_discharge(self, mask):
        """ The effective discharge of this DER
        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set

        Returns: the discharge as a function of time for the

        """
        if self.being_sized():
            return cvx.Parameter(shape=sum(mask), name=f'{self.name}/rated gen', value=self.gen_per_rated.loc[mask].values) * self.rated_capacity
        else:
            return super().get_discharge(mask)

    def constraints(self, mask):
        """ Builds the master constraint list for the subset of timeseries data being optimized.

        Returns:
            A list of constraints that corresponds the battery's physical constraints and its service constraints
        """
        constraints = super().constraints(mask)
        constraints += self.size_constraints
        return constraints

    def objective_function(self, mask, annuity_scalar=1):
        """ Generates the objective function related to a technology. Default includes O&M which can be 0

        Args:
            mask (Series): Series of booleans used, the same length as case.power_kw
            annuity_scalar (float): a scalar value to be multiplied by any yearly cost or benefit that helps capture the cost/benefit over
                    the entire project lifetime (only to be set iff sizing, else alpha should not affect the aobject function)

        Returns:
            self.costs (Dict): Dict of objective costs
        """
        costs = super().objective_function(mask, annuity_scalar)
        costs.update(self.sizing_objective())
        return costs

    def timeseries_report(self):
        """ Summaries the optimization results for this DER.

        Returns: A timeseries dataframe with user-friendly column headers that summarize the results
            pertaining to this instance

        """
        results = super().timeseries_report()
        if self.being_sized() and not self.curtail:
            # convert expressions into values
            tech_id = self.unique_tech_id()
            results[tech_id + ' Electric Generation (kW)'] = self.maximum_generation()
            results[tech_id + ' Maximum (kW)'] = self.maximum_generation()
        return results

    def set_size(self):
        """ Save value of size variables of DERs

        """
        try:
            rated_capacity = self.rated_capacity.value
        except AttributeError:
            rated_capacity = self.rated_capacity
        self.rated_capacity = rated_capacity

    def sizing_summary(self):
        """

        Returns: A dictionary describe this DER's size and captial costs.

        """
        try:
            rated_capacity = self.rated_capacity.value
        except AttributeError:
            rated_capacity = self.rated_capacity

        sizing_results = {
            'DER': self.name,
            'Power Capacity (kW)': rated_capacity,
            'Capital Cost ($/kW)': self.capital_cost_function}

        # warn about tight sizing margins
        if isinstance(self.rated_capacity, cvx.Variable):
            sizing_margin1 = (abs(self.rated_capacity.value - self.max_rated_capacity) - 0.05 * self.max_rated_capacity)
            sizing_margin2 = (abs(self.rated_capacity.value - self.min_rated_capacity) - 0.05 * self.min_rated_capacity)
            if (sizing_margin1 < 0).any() or (sizing_margin2 < 0).any():
                TellUser.warning(f"Difference between the optimal {self.name} rated capacity and user upper/lower "
                                 "bound constraints is less than 5% of the value of user upper/lower bound constraints")

        return sizing_results

    def update_for_evaluation(self, input_dict):
        """ Updates price related attributes with those specified in the input_dictionary

        Args:
            input_dict: hold input data, keys are the same as when initialized

        """
        super().update_for_evaluation(input_dict)
        cost_per_kw = input_dict.get('ccost_kW')
        if cost_per_kw is not None:
            self.capital_cost_function = cost_per_kw

    def sizing_error(self):
        """

        Returns: True if there is an input error

        """
        if self.min_rated_capacity > self.max_rated_capacity:
            TellUser.error(f'{self.unique_tech_id()} requires min_rated_capacity < max_rated_capacity.')
            return True

    def max_power_defined(self):
        return self.is_power_sizing() and not self.max_rated_capacity

    def replacement_cost(self):
        """

        Returns: the capex of this DER for optimization

        """
        try:
            rated_capacity = self.rated_capacity.value
        except AttributeError:
            rated_capacity = self.rated_capacity
        return np.dot(self.replacement_cost_function, [rated_capacity])
