"""
CAESSizing.py

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

u_logger = logging.getLogger('User')
e_logger = logging.getLogger('Error')


class CAESSizing(CAESTech.CAES, Sizing):
    """ CAES class that inherits from StorageVET. this object does not size.

    """

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
        if sizing_dict['Duration (hours)'] > 24:
            u_logger.error(f'The duration of {self.name} is greater than 24 hours!')

        return sizing_dict




