"""
BatteryTech.py

This Python class contains methods and attributes specific for technology analysis within StorageVet.
"""

__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'mevans@epri.com']
__version__ = 'beta'  # beta version

import cvxpy as cvx
from storagevet.Technology import BatteryTech
from MicrogridDER.ESSSizing import ESSSizing
from ErrorHandelling import *

DEBUG = False


class Battery(BatteryTech.Battery, ESSSizing):
    """ Battery class that inherits from Storage.

    """

    def __init__(self, params):
        """ Initializes a battery class that inherits from the technology class.
        It sets the type and physical constraints of the technology.

        Args:
            params (dict): params dictionary from dataframe for one case
        """
        super().__init__(params)  # BatteryTech.Battery->ESSizing->EnergyStorage->DER->Sizing

        self.user_duration = params['duration_max']

        if self.user_duration:
            # if self.is_discharge_sizing() and self.is_energy_sizing():
            #     TellUser.error("Cannot set a")
            self.size_constraints += [cvx.NonPos(self.ene_max_rated - self.user_duration*self.dis_max_rated)]

    def constraints(self, mask):
        """ Builds the master constraint list for the subset of timeseries data being optimized.

        Args:
            mask (DataFrame): A boolean array that is true for indices corresponding to time_series data included
                in the subs data set

        Returns:
            A list of constraints that corresponds the battery's physical constraints and its service constraints
        """

        constraint_list = super().constraints(mask)  # BatteryTech.Battery->ESSSizing->EnergyStorage
        return constraint_list
