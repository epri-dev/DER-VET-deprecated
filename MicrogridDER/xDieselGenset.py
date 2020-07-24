"""
ICE (Internal Combustion Engine)
    - fuel_price fixed in Model Params CSV

"""

__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani', 'Micah Botkin-Levy', 'Yekta Yazar']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Evan Giarta', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'egiarta@epri.com', 'mevans@epri.com']
__version__ = '2.1.1.1'

import cvxpy as cvx
import numpy as np
import pandas as pd
from .InternalCombustionEngine import ICE


class DieselGenset(ICE):
    """ Diesel Genset Technology

    """

    def __init__(self, params):
        """ Initialize all technology with the following attributes.

        Args:
            params (dict): Dict of parameters for initialization
        """

        # base class is ICE
        super().__init__(params)

        # overrides
        self.tag = 'DieselGenset'
        self.self.can_participate_in_market_services = False
