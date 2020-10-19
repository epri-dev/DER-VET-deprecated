"""
CT Sizing class

This Python class contains methods and attributes specific for technology analysis within StorageVet.
"""

__author__ = 'Andrew Etringer'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'mevans@epri.com']
__version__ = 'beta'  # beta version

import cvxpy as cvx
from MicrogridDER.RotatingGeneratorSizing import RotatingGeneratorSizing
import pandas as pd
import storagevet.Library as Lib
import numpy as np
from ErrorHandelling import *
from DERVETParams import ParamsDER


class CT(RotatingGeneratorSizing):
    """ An Combustion Turbine (CT) generator, with sizing optimization

    """

    def __init__(self, params):
        """ Initialize all technology with the following attributes.

        Args:
            params (dict): Dict of parameters for initialization
        """
        TellUser.debug(f"Initializing {__name__}")
        super().__init__(params)

        self.tag = 'CT'
        self.heat_rate = 1e-3 * params['heat_rate']  # MMBtu/MWh ---> MMBtu/kWh
