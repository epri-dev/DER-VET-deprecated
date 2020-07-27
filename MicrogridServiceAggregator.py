__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani', 'Micah Botkin-Levy', 'Thien Nguyen', 'Yekta Yazar']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Evan Giarta', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'egiarta@epri.com', 'mevans@epri.com']
__version__ = "x.x.x"

from storagevet.ServiceAggregator import ServiceAggregator
from ErrorHandelling import *


class MicrogridServiceAggregator(ServiceAggregator):
    """ The entity that tracks the value streams and bids the Microgrid's capabilities
    into energy markets

    """
    def post_facto_reliability_only(self):
        """

        Returns: A boolean that is true if Reliability is doing post facto calculations only

        """
        return len(self.value_streams.keys()) == 1 and 'Reliability' in self.value_streams.keys() and self.value_streams['Reliability'].post_facto_only

    def is_whole_sale_market(self):
        """

        Returns: boolean, interect btw list of market services

        """
        return {'SR', 'NSR', 'FR', 'LF'} & set(self.value_streams.keys())

    def does_wholesale_markets_have_max_defined(self):
        """

        Returns:

        """
        error = False
        for vs_name in {'LF', 'SR', 'NSR', 'FR'}:
            vs = self.value_streams.get(vs_name, False)
            if vs and not vs.u_ts_constraints and not vs.d_ts_constraints:
                TellUser.error('Trying to size the power of the system to maximize profits ' +
                               f'in wholesale markets, but {vs_name} time-series constraints is not applied.')
                error = True
        return error

    def any_max_participation_constraints_not_included(self):
        return bool(sum([1 if not vs.max_participation_is_defined() else 0 for vs in self.value_streams]))
