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

import storagevet
import logging
import pandas as pd

u_logger = logging.getLogger('User')
e_logger = logging.getLogger('Error')


class CAESSizing(storagevet.CAESTech):
    """ CAES class that inherits from Storage.

    """

    def __init__(self, name,  params):
        """ Initializes CAES class that inherits from the technology class.
        It sets the type and physical constraints of the technology.

        Args:
            name (string): name of technology
            params (dict): params dictionary from dataframe for one case
        """

        # create generic storage object
        storagevet.CAESTech.__init__(self, name,  params)

        self.size_constraints = []

        self.optimization_variables = {}

    def sizing_summary(self):
        """
        TODO: CAESSizing is waiting to be implemented, it is currently mimicking BatterySizing's method

        Returns: A datafram indexed by the terms that describe this DER's size and captial costs.

        """
        # obtain the size of the CAES, these may or may not be optimization variable
        # therefore we check to see if it is by trying to get its value attribute in a try-except statement.
        # If there is an error, then we know that it was user inputted and we just take that value instead.
        try:
            energy_rated = self.ene_max_rated.value
        except AttributeError:
            energy_rated = self.ene_max_rated

        try:
            ch_max_rated = self.ch_max_rated.value
        except AttributeError:
            ch_max_rated = self.ch_max_rated

        try:
            dis_max_rated = self.dis_max_rated.value
        except AttributeError:
            dis_max_rated = self.dis_max_rated

        index = pd.Index([self.name], name='DER')
        sizing_results = pd.DataFrame({'CAES Energy Rating (kWh)': energy_rated,
                                       'CAES Charge Rating (kW)': ch_max_rated,
                                       'CAES Discharge Rating (kW)': dis_max_rated,
                                       'CAES Duration (hours)': energy_rated / dis_max_rated,
                                       'CAES Capital Cost ($)': self.ccost,
                                       'CAES Capital Cost ($/kW)': self.ccost_kw,
                                       'CAES Capital Cost ($/kWh)': self.ccost_kwh}, index=index)
        return sizing_results

    def being_sized(self):
        """ checks itself to see if this instance is being sized

        Returns: true if being sized, false if not being sized

        """
        return bool(len(self.size_constraints))



