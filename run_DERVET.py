"""
runDERVET.py

This Python script serves as the initial launch point executing the Python-based version of DERVET
(AKA StorageVET 2.0 or SVETpy).
"""

__author__ = 'Halley Nathwani'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani', "Thien Nguyen", 'Kunle Awojinrin']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'mevans@epri.com']
__version__ = 'beta'  # beta version

import logging
import time
import argparse
import os
import sys

# ADD STORAGEVET TO PYTHONPATH BEFORE IMPORTING ANY LIBRARIES OTHERWISE IMPORTERROR

# dervet's directory path is the first in sys.path
# determine storagevet path (absolute path)
storagevet_path = os.path.join(sys.path[0], 'storagevet')

# add storagevet (source root) to PYTHONPATH
sys.path.insert(0, storagevet_path)


import storagevet
from MicrogridScenario import MicrogridScenario
from DERVETParams import ParamsDER
from MicrogridResult import MicrogridResult
from storagevet.Visualization import Visualization


e_logger = logging.getLogger('Error')
u_logger = logging.getLogger('User')


class DERVET:
    """ DERVET API. This will eventually allow StorageVET to be imported and used like any
    other python library.

    """

    @classmethod
    def load_case(cls, model_parameters_path, **kwargs):
        return cls(model_parameters_path, **kwargs)

    def __init__(self, model_parameters_path, verbose=False, **kwargs):
        """
            Constructor to initialize the parameters and data needed to run StorageVET\

            Args:
                model_parameters_path (str): Filename of the model parameters CSV or XML that
                    describes the optimization case to be analysed

            Notes: kwargs is in place for testing purposes
        """
        self.verbose = verbose

        # Initialize the Params Object from Model Parameters and Simulation Cases
        self.cases = ParamsDER.initialize(model_parameters_path, self.verbose)
        self.results = MicrogridResult.initialize(ParamsDER.results_inputs, ParamsDER.case_definitions)
        u_logger.info('Successfully initialized the Params class with the XML file.')

        if self.verbose:
            Visualization(ParamsDER).class_summary()

    def solve(self):
        starts = time.time()

        for key, value in self.cases.items():
            run = MicrogridScenario(value)
            run.set_up_poi_and_service_aggregator()
            run.initialize_cba()
            run.fill_and_drop_extra_data()
            continue_to_results = run.optimize_problem_loop()

            if continue_to_results:
                MicrogridResult.add_instance(key, run)
            else:
                raise ArithmeticError("Further calculations requires that economic dispatch is solved, but "
                                      + "no optimization was built or solved. Please check log files for more information. ")

        MicrogridResult.sensitivity_summary()

        ends = time.time()
        print("DERVET runtime: ") if self.verbose else None
        print(ends - starts) if self.verbose else None

        return MicrogridResult


if __name__ == '__main__':
    """
        This section is run when the file is called from the command line.
    """

    parser = argparse.ArgumentParser(prog='run_DERVET.py',
                                     description='The Electric Power Research Institute\'s energy storage system ' +
                                                 'analysis, dispatch, modelling, optimization, and valuation tool' +
                                                 '. Should be used with Python 3.6.x, pandas 0.19+.x, and CVXPY' +
                                                 ' 0.4.x or 1.0.x.',
                                     epilog='Copyright 2018. Electric Power Research Institute (EPRI). ' +
                                            'All Rights Reserved.')
    parser.add_argument('parameters_filename', type=str,
                        help='specify the filename of the CSV file defining the PARAMETERS dataframe')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='specify this flag for verbose output during execution')
    parser.add_argument('--gitlab-ci', action='store_true',
                        help='specify this flag for gitlab-ci testing to skip user input')
    arguments = parser.parse_args()

    case = DERVET(arguments.parameters_filename, verbose=arguments.verbose, ignore_cba_valuation=True)
    case.solve()

    # print("Program is done.")
