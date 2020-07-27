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
from MicrogridDER.ESSSizing import ESSSizing
from ErrorHandelling import *


class CAES(CAESTech.CAES, ESSSizing):
    """ CAES class that inherits from StorageVET. this object does not size.

    """

    def __init__(self, params):
        """ Initialize all technology with the following attributes.

        Args:
            params (dict): Dict of parameters for initialization
        """
        TellUser.debug(f"Initializing {__name__}")
        super().__init__(params)  # CAESTech.CAES->ESSizing->EnergyStorage->DER->Sizing

        # warn the user that the power/energy is 0
        if not self.dis_max_rated:
            TellUser.error(f"{self.unique_tech_id()} has a discharge value of 0. Did you mean to do this?")
            raise ModelParameterError(f" Please check the size of {self.unique_tech_id()}")
        if not self.ch_max_rated:
            TellUser.error(f"{self.unique_tech_id()} has a charge value of 0. Did you mean to do this?")
            raise ModelParameterError(f" Please check the size of {self.unique_tech_id()}")
        if not self.ene_max_rated:
            TellUser.error(f"{self.unique_tech_id()} has a energy value of 0. Did you mean to do this?")
            raise ModelParameterError(f" Please check the size of {self.unique_tech_id()}")

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
        if self.being_sized():
            costs.update({self.name + 'capex': self.get_capex()})

    def update_for_evaluation(self, input_dict):
        """ Updates price related attributes with those specified in the input_dictionary

        Args:
            input_dict: hold input data, keys are the same as when initialized

        """
        super().update_for_evaluation(input_dict)

        heat_rate_high = input_dict.get('heat_rate_high')
        if heat_rate_high is not None:
            self.heat_rate_high = heat_rate_high
