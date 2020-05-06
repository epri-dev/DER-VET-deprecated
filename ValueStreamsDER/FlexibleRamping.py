"""
FlexibleRamping.py

This Python class contains methods and attributes specific for service analysis within StorageVet.
"""

__author__ = 'Miles Evans and Evan Giarta'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani', 'Thien Nguyen']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Evan Giarta', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'egiarta@epri.com', 'mevans@epri.com']
__version__ = '2.1.1.1'

from ValueStreams.ValueStream import ValueStream
import storagevet
import cvxpy as cvx
import numpy as np
import pandas as pd
import logging

try:
    import Constraint as Const
    import Library as Lib
except ModuleNotFoundError:
    import storagevet.Constraint as Const
    import storagevet.Library as Lib

u_logger = logging.getLogger('User')
e_logger = logging.getLogger('Error')


class FlexibleRamping(storagevet.ValueStream):
    """ Flexible Ramping market service, inheriting ValueStream class.

    """

    def __init__(self, params, tech, dt):
        """
        Args:
            params (dict): input parameters
            tech (Technology): technology object
            dt (float): optimization time-step (hours)

        """

        ValueStream.__init__(self, tech, 'FlexR', dt)

        self.combined_market = params['CombinedMarket']  # boolean: true if ramp up is equal to ramp down
        self.growth = params['growth']

        # forecasted movement value from time-series input
        self.ramp_load = params['forecasted_movement']

        self.price = params['energy_price']  # TODO: require RT market price instead of DA price
        self.flexr_up_price = params['flexr_up_price']
        self.flexr_do_price = params['flexr_do_price']

        # max/min resource uncertainties in upward/downward direction
        self.variable_names = {'flexr_up_c', 'flexr_do_c', 'flexr_up_d', 'flexr_do_d'}
        self.variables = pd.DataFrame(columns=self.variable_names)