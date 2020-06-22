"""
CAES.py

This Python class contains methods and attributes specific for technology analysis within StorageVet.
"""

__author__ = 'Thien Nguyen'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani', 'Thien Nguyen', 'Micah Botkin-Levy', 'Yekta Yazar']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'mevans@epri.com']
__version__ = 'beta'  # beta version

from storagevet.Technology import CAESTech
import logging
from MicrogridDER.Sizing import Sizing
from MicrogridDER.DERExtension import DERExtension
import pandas as pd
import cvxpy as cvx

u_logger = logging.getLogger('User')
e_logger = logging.getLogger('Error')


class CAES(CAESTech.CAES, Sizing, DERExtension, Sizing):
    """ CAES class that inherits from StorageVET. this object does not size.

    """
    def constraints(self, mask):
        """ Builds the master constraint list for the subset of timeseries data being optimized.

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set

        Returns:
            A list of constraints that corresponds the battery's physical constraints and its service constraints
        """

        constraint_list = super().constraints(mask)

        nsr_max_capacity = self.variables_dict['nsr_max_capacity']
        sr_max_capacity = self.variables_dict['sr_max_capacity']
        fr_max_regulation = self.variables_dict['fr_max_regulation']
        if self.incl_startup and self.incl_binary:
            # add ramp rate constraints here --> SR, NSR, FR (these include startup_time)
            # TODO: confirm that these newfound constraints adhere to the mathematical formulation!!!
            # TODO: for fr_max_regulation, make sure that you go back and do the up/down regulation part. Because FR is bidirectional --> Kunle
            # TODO: refer to Miles handout as well to make sure that your objective functions are in line w/ expectations --> Kunle
            constraint_list += [cvx.NonPos(sr_max_capacity - cvx.multiply(self.lag_time, self.sr_response_time) +
                                           cvx.multiply(self.sr_response_time, self.sr_max_ramp_rate) +
                                           cvx.multiply(self.startup_time, self.sr_max_ramp_rate))]
            constraint_list += [cvx.NonPos(nsr_max_capacity - cvx.multiply(self.lag_time, self.nsr_response_time) +
                                           cvx.multiply(self.nsr_response_time, self.nsr_max_ramp_rate) +
                                           cvx.multiply(self.startup_time, self.nsr_max_ramp_rate))]
            constraint_list += [cvx.NonPos(fr_max_regulation - cvx.multiply(self.lag_time, self.fr_response_time) +
                                           cvx.multiply(self.fr_response_time, self.fr_max_ramp_rate) +
                                           cvx.multiply(self.startup_time, self.fr_max_ramp_rate))]
        else:
            # add ramp rate constraints here --> SR, NSR, FR (these DON'T include startup_time)
            # TODO: confirm that these newfound constraints adhere to the mathematical formulation!!!
            # TODO: for fr_max_regulation, make sure that you go back and do the up/down regulation part. Because FR is bidirectional --> Kunle
            # TODO: refer to Miles handout as well to make sure that your objective functions are in line w/ expectations --> Kunle
            constraint_list += [cvx.NonPos(sr_max_capacity - cvx.multiply(self.lag_time, self.sr_response_time) +
                                           cvx.multiply(self.sr_response_time, self.sr_max_ramp_rate))]
            constraint_list += [cvx.NonPos(nsr_max_capacity - cvx.multiply(self.lag_time, self.nsr_response_time) +
                                           cvx.multiply(self.nsr_response_time, self.nsr_max_ramp_rate))]
            constraint_list += [cvx.NonPos(fr_max_regulation - cvx.multiply(self.lag_time, self.fr_response_time) +
                                           cvx.multiply(self.fr_response_time, self.fr_max_ramp_rate))]

        return constraint_list

    def sizing_summary(self):
        """

        Returns: A dictionary describe this DER's size and captial costs.

        """
        sizing_dict = {
            'DER': self.name,
            'Energy Rating (kWh)': self.ene_max_rated,
            'Charge Rating (kW)': self.ch_max_rated,
            'Discharge Rating (kW)': self.dis_max_rated,
            'Round Trip Efficiency (%)': self.rte,
            'Lower Limit on SOC (%)': self.llsoc,
            'Upper Limit on SOC (%)': self.ulsoc,
            'Duration (hours)': self.ene_max_rated / self.dis_max_rated,
            'Capital Cost ($)': self.capital_cost_function[0],
            'Capital Cost ($/kW)': self.capital_cost_function[1],
            'Capital Cost ($/kWh)': self.capital_cost_function[2]
        }
        if (sizing_dict['Duration (hours)'] > 24).any():
            print('The duration of an Energy Storage System is greater than 24 hours!')

        return sizing_dict

    def update_for_evaluation(self, input_dict):
        """ Updates price related attributes with those specified in the input_dictionary

        Args:
            input_dict: hold input data, keys are the same as when initialized

        """
        super().update_for_evaluation(input_dict)
        fixed_om = input_dict.get('fixedOM')
        if fixed_om is not None:
            self.fixedOM_perKW = fixed_om

        variable_om = input_dict.get('OMexpenses')
        if variable_om is not None:
            self.variable_om = variable_om * 100

        heat_rate_high = input_dict.get('heat_rate_high')
        if heat_rate_high is not None:
            self.heat_rate_high = heat_rate_high

        if self.incl_startup:
            p_start_ch = input_dict.get('p_start_ch')
            if p_start_ch is not None:
                self.p_start_ch = p_start_ch

            p_start_dis = input_dict.get('p_start_dis')
            if p_start_dis is not None:
                self.p_start_dis = p_start_dis

    def timeseries_report(self):
        """ Summaries the optimization results for this DER.

        Returns: A timeseries dataframe with user-friendly column headers that summarize the results
            pertaining to this instance

        """
        results = CAESTech.CAES.timeseries_report(self)
        more_results = DERExtension.timeseries_report(self)
        results = pd.concat([results, more_results], axis=1)
        return results
