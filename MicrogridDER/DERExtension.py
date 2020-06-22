"""
Defines an class that extends DERs beyond their definition in StorageVET
for the purpose of DER-VET functionallty

"""

__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani', 'Micah Botkin-Levy', 'Yekta Yazar']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Evan Giarta', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'egiarta@epri.com', 'mevans@epri.com']
__version__ = 'beta'

import numpy as np
import pandas as pd
from storagevet.Technology import DistributedEnergyResource
import cvxpy as cvx


class DERExtension:
    """ This class is to be inherited by DER classes that want to allow the DER our generic
    DER model to extend beyond that in StorageVET.

    This class is meant to initialize a DER with the DER class defined in the StorageVET module
    -- so it will error if you try to write a class that inherits from this class ONLY.

    """

    def __init__(self, params):
        """

        """
        # try to look for DERVET specific user inputs that are shared by all DERs
        self.nsr_response_time = params['nsr_response_time']
        self.sr_response_time = params['sr_response_time']
        self.startup_time = params['startup_time']  # startup time, default value of 0, units in minutes
        self.nsr_max_ramp_rate = params['nsr_max_ramp_rate']  # MW/min
        self.sr_max_ramp_rate = params['sr_max_ramp_rate']  # MW/min
        self.lag_time = params['lag_time']  # basically the lag b/w generator signal and technology ramp rate
        self.fr_response_time = params['fr_response_time']  # mins, default = 10 mins
        self.fr_max_ramp_rate = params['fr_max_ramp_rate']  # kW/min

        self.macrs = params.get('macrs_term')
        self.construction_date = params.get('construction_date')
        self.operation_date = params.get('operation_date')
        self.variable_names |= {'nsr_max_capacity', 'sr_max_capacity', 'fr_max_regulation'}

    def initialize_variables(self, size):
        """ Adds optimization variables to dictionary
        Notes:
            CVX Parameters turn into Variable when the condition to include them is active

        Args:
            size (Int): Length of optimization variables to create

        """
        self.variables_dict.update({
            'sr_max_capacity': cvx.Variable(shape=size, name='sr_max_capacity'),
            'nsr_max_capacity': cvx.Variable(shape=size, name='nsr_max_capacity'),
            'fr_max_regulation': cvx.Variable(shape=size, name='fr_max_regulation')
        })

    def update_for_evaluation(self, input_dict):
        """ Updates price related attributes with those specified in the input_dictionary

        Args:
            input_dict: hold input data, keys are the same as when initialized

        """
        marcs_term = input_dict.get('macrs_term')
        if marcs_term is not None:
            self.macrs = marcs_term

        ccost = input_dict.get('ccost')
        if ccost is not None:
            self.capital_cost_function[0] = ccost

        ccost_kw = input_dict.get('ccost_kw')
        if ccost_kw is not None:
            self.capital_cost_function[1] = ccost_kw

        ccost_kwh = input_dict.get('ccost_kwh')
        if ccost_kwh is not None:
            self.capital_cost_function[2] = ccost_kwh

    def timeseries_report(self):
        """ Summaries the optimization results for this DER.

        Returns: A timeseries dataframe with user-friendly column headers that summarize the results
            pertaining to this instance

        """
        tech_id = self.unique_tech_id()
        results = pd.DataFrame(index=self.variables_df.index)
        # add timeseries_report stuff for nsr, sr, fr additions (above), which reports on the optimal values
        results[f'{tech_id} NSR Max Capacity (MW)'] = self.variables_df['nsr_max_capacity']
        results[f'{tech_id} SR Max Capacity (MW)'] = self.variables_df['sr_max_capacity']
        results[f'{tech_id} FR Max Regulation (kW)'] = self.variables_df['fr_max_regulation']
        return results
