__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani', 'Micah Botkin-Levy', 'Thien Nguyen', 'Yekta Yazar']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Evan Giarta', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'egiarta@epri.com', 'mevans@epri.com']
__version__ = "x.x.x"

from storagevet.ServiceAggregator import ServiceAggregator


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

