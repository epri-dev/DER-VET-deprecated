"""
MicrogridPOI.py

"""

__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani',
               'Micah Botkin-Levy', "Thien Nguyen", 'Yekta Yazar']
__license__ = 'EPRI'
__maintainer__ = ['Evan Giarta', 'Miles Evans']
__email__ = ['egiarta@epri.com', 'mevans@epri.com']


import logging
import pandas as pd
from storagevet.POI import POI
import cvxpy as cvx

e_logger = logging.getLogger('Error')
u_logger = logging.getLogger('User')


class MicrogridPOI(POI):
    """
        This class holds the load data for the case described by the user defined model parameter. It will also
        impose any constraints that should be opposed at the microgrid's POI.
    """

    def __init__(self, params, technology_inputs_map, technology_class_map):
        super().__init__(params, technology_inputs_map, technology_class_map)
        self.is_sizing_optimization = self.check_if_sizing_ders()

    def check_if_sizing_ders(self):
        """ This method will iterate through the initialized DER instances and return a logical OR of all of their
        'being_sized' methods.

        Returns: True if ANY DER is getting sized

        """
        for der_instance in self.der_list:
            try:
                solve_for_size = der_instance.being_sized()
            except AttributeError:
                solve_for_size = False
            if solve_for_size:
                return True
        return False

    def grab_active_ders(self, indx):
        """ drops DER that are not considered active in the optimization window's horizon

        """
        year = indx.year[0]
        active_ders = [der_instance for der_instance in self.der_list if der_instance.operational(year)]
        self.active_ders = active_ders

    def is_dcp_error(self, is_binary_formulation):
        """ If trying to sizing power of batteries (or other DERs) AND using the binary formulation (of ESS)
        our linear model will not be linear anymore

        Args:
            is_binary_formulation (bool):

        Returns: a boolean

        """
        solve_for_size = False
        for der_instance in self.der_list:
            if der_instance.tag == 'Battery':
                power_being_sizing = isinstance(der_instance.dis_max_rated, cvx.Variable) or isinstance(der_instance.ch_max_rated, cvx.Variable)
                solve_for_size = solve_for_size or (power_being_sizing and is_binary_formulation)
        return solve_for_size

    def sizing_summary(self):
        rows = list(map(lambda der: der.sizing_summary(), self.der_list))
        sizing_df = pd.DataFrame(rows)
        sizing_df.set_index('DER')
        return sizing_df
