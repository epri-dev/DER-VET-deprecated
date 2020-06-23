"""
Sizing Module

"""

__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani', 'Micah Botkin-Levy', 'Yekta Yazar']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Evan Giarta', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'egiarta@epri.com', 'mevans@epri.com']
__version__ = 'beta'

import numpy as np


class Sizing:
    """ This class is to be inherited by DER classes that want to also define the ability
    to optimal size of itself

    """

    def __init__(self):
        self.size_constraints = []

    def being_sized(self):
        """ checks itself to see if this instance is being sized

        Returns: true if being sized, false if not being sized

        """
        return bool(len(self.size_constraints))

    def sizing_summary(self):
        """ Creates the template for sizing df that each DER must fill to report their size.

        Returns: A dictionary describe this DER's size and captial costs.

        """
        # sizing_dict = {
        #     'DER': np.nan,
        #     'Energy Rating (kWh)': np.nan,
        #     'Charge Rating (kW)': np.nan,
        #     'Discharge Rating (kW)': np.nan,
        #     'Round Trip Efficiency (%)': np.nan,
        #     'Lower Limit on SOC (%)': np.nan,
        #     'Upper Limit on SOC (%)': np.nan,
        #     'Duration (hours)': np.nan,
        #     'Capital Cost ($)': np.nan,
        #     'Capital Cost ($/kW)': np.nan,
        #     'Capital Cost ($/kWh)': np.nan,
        #     'Power Capacity (kW)': np.nan,
        #     'Quantity': 1,
        # }
        # return sizing_dict
