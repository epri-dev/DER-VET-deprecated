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
import pandas as pd


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

        self.nu = params['nu'] / 100
        self.gamma = params['gamma'] / 100
        self.curtail = params['curtail']
        self.max_rated_capacity = params['max_rated_capacity']
        self.min_rated_capacity = params['min_rated_capacity']
        self.ppa = params['PPA']
        self.ppa_cost = params['PPA_cost']
        self.ppa_inflation = params['PPA_inflation_rate']

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

    def get_capex(self, solution=False):
        capex = super().get_capex()
        if solution:
            try:
                capex = capex.value
            except AttributeError:
                capex = capex
        return capex

    def constraints(self, mask, **kwargs):
        """ Builds the master constraint list for the subset of timeseries data being optimized.

        Returns:
            A list of constraints that corresponds the battery's physical constraints and its service constraints
        """
        constraints = super().constraints(mask, **kwargs)
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

    def maximum_generation(self,  label_selection=None,sizing=False):
        """ The most that the PV system could discharge.

        Args:
            label_selection: A single label, e.g. 5 or 'a',
                a list or array of labels, e.g. ['a', 'b', 'c'],
                a boolean array of the same length as the axis being sliced, e.g. [True, False, True]
                a callable function with one argument (the calling Series or DataFrame)

        Returns: valid array output for indexing (one of the above) of the max generation profile

        """
        PV_gen = super().maximum_generation(label_selection,sizing)
        if sizing:
            try:
                PV_gen = PV_gen.value
            except AttributeError:
                pass
        return PV_gen

    def set_size(self):
        """ Save value of size variables of DERs

        """
        self.rated_capacity = self.get_rated_capacity(solution=True)
        self.inv_max = self.inv_rated_capacity(sizing=True)

    def inv_rated_capacity(self, sizing=False):
        """

        Returns: the maximum energy times two for PV inverter rating

        """
        if not sizing:
            return self.rated_capacity
        else:
            try:
                max_rated = self.rated_capacity.value
            except AttributeError:
                max_rated = self.rated_capacity
            return max_rated

    def get_rated_capacity(self, solution=False):
        """

        Returns: the maximum energy that can be attained

        """
        if not solution:
            return self.rated_capacity
        else:
            try:
                max_rated = self.rated_capacity.value
            except AttributeError:
                max_rated = self.rated_capacity
            return max_rated

    def maximum_generation(self, label_selection=None):
        """ The most that the PV system could discharge.

        Args:
            label_selection: A single label, e.g. 5 or 'a',
                a list or array of labels, e.g. ['a', 'b', 'c'],
                a boolean array of the same length as the axis being sliced, e.g. [True, False, True]
                a callable function with one argument (the calling Series or DataFrame)

        Returns: valid array output for indexing (one of the above) of the max generation profile

        """
        max_generation = super(IntermittentResourceSizing, self).maximum_generation(label_selection)
        try:
            max_generation = max_generation.value
        except AttributeError:
            pass
        return max_generation

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

    def proforma_report(self, inflation_rate, apply_inflation_rate_func, fill_forward_func, results):
        """ Calculates the proforma that corresponds to participation in this value stream

        Args:
            inflation_rate (float):
            apply_inflation_rate_func:
            fill_forward_func:
            results (pd.DataFrame):

        Returns: A DateFrame of with each year in opt_year as the index and
            the corresponding value this stream provided.

            Creates a dataframe with only the years that we have data for. Since we do not label the column,
            it defaults to number the columns with a RangeIndex (starting at 0) therefore, the following
            DataFrame has only one column, labeled by the int 0

        """
        if self.ppa:
            analysis_years = self.variables_df.index.year.unique()
            pro_forma = pd.DataFrame()

            ppa_label = f"{self.unique_tech_id()} PPA"
            # for each year of analysis
            for year in analysis_years:
                subset_max_production = self.maximum_generation(results.index.year == year)
                # sum up total annual solar production (kWh)
                total_annual_production = subset_max_production.sum() * self.dt
                # multiply with Solar PPA Cost ($/kWh), and set at YEAR's value
                pro_forma.loc[pd.Period(year, freq='y'), ppa_label] = total_annual_production * -self.ppa_cost
            # apply PPA inflation rate
            pro_forma = apply_inflation_rate_func(pro_forma, self.ppa_inflation, min(analysis_years))
            # fill forward
            pro_forma = fill_forward_func(pro_forma, self.ppa_inflation)
        else:
            pro_forma = super().proforma_report(inflation_rate, apply_inflation_rate_func, fill_forward_func, results)
        return pro_forma

    def tax_contribution(self, depreciation_schedules, project_length):
        if not self.ppa:
            return super().tax_contribution(depreciation_schedules, project_length)
