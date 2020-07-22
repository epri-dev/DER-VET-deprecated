"""
ICE Sizing class

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
from storagevet.Technology import InternalCombustionEngine
from MicrogridDER.RotatingGeneratorSizing import RotatingGeneratorSizing


class ICE(RotatingGeneratorSizing, InternalCombustionEngine.ICE):
    """ An ICE generator, with sizing optimization

    """

    def __init__(self, params):
        """ Initialize all technology with the following attributes.

        Args:
            params (dict): Dict of parameters for initialization
        """
        RotatingGeneratorSizing.__init__(self, 'ICE', params)
        InternalCombustionEngine.ICE.__init__(self, params)

    def update_for_evaluation(self, input_dict):
        """ Updates price related attributes with those specified in the input_dictionary

        Args:
            input_dict: hold input data, keys are the same as when initialized

        """
        super().update_for_evaluation(input_dict)

        fuel_cost = input_dict.get('fuel_cost')
        if fuel_cost is not None:
            self.fuel_cost = fuel_cost

    def replacement_cost(self):
        """

        Returns: the cost of replacing this DER

        """
        return np.dot(self.replacement_cost_function, [self.number_of_generators(), self.discharge_capacity()])
