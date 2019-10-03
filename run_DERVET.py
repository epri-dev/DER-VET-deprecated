"""
runDERVET.py

This Python script serves as the initial launch point executing the Python-based version of DERVET
(AKA StorageVET 2.0 or SVETpy).
"""

__author__ = 'Miles Evans and Evan Giarta'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani',
               'Micah Botkin-Levy', "Thien Nguyen", 'Yekta Yazar']
__license__ = 'EPRI'
__maintainer__ = ['Evan Giarta', 'Miles Evans']
__email__ = ['egiarta@epri.com', 'mevans@epri.com']

import sys
from pathlib import Path
import os.path
import logging
import time
from datetime import datetime
import argparse
import pandas as pd

# ADD STORAGEVET TO PYTHONPATH BEFORE IMPORTING ANY LIBRARIES OTHERWISE IMPORTERROR

# dervet's directory path is the first in sys.path
# determine storagevet path (absolute path)
storagevet_path = os.path.join(sys.path[0], 'storagevet')

# add storagevet (source root) to PYTHONPATH
sys.path.insert(0, storagevet_path)
print(sys.path)

from ScenarioSizing import ScenarioSizing
from ParamsDER import ParamsDER as Params
from ResultDER import ResultDER as Result

# TODO: make multi-platform by using path combine functions

developer_path = '.\logs'  # TODO: move this path (XENDEE's server requires special access to perform these tasks
try:
    os.mkdir(developer_path)
except OSError:
    print("Creation of the developer/error_log directory %s failed. Possibly already created." % developer_path)
else:
    print("Successfully created the developer/error_log directory %s " % developer_path)

LOG_FILENAME1 = developer_path + '\\developer_log_' + datetime.now().strftime('%H_%M_%S_%m_%d_%Y.log')
handler = logging.FileHandler(Path(LOG_FILENAME1))
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
dLogger = logging.getLogger('Developer')
dLogger.setLevel(logging.DEBUG)
dLogger.addHandler(handler)
dLogger.info('Started logging...')


class DERVET:
    """ DERVET API. This will eventually allow storagevet to be imported and used like any
    other python library.

    """

    def __init__(self, model_parameters_path, schema_path):
        """
            Constructor to initialize the parameters and data needed to run StorageVET\

            Args:
                model_parameters_path (str): Filename of the model parameters CSV or XML that
                    describes the case to be analysed
                schema_path (str): relative path to the Schema.xml that storagevet uses
        """
        if model_parameters_path.endswith(".csv"):
            model_parameters_path = Params.csv_to_xml(model_parameters_path)

        # Initialize the Params Object from Model Parameters and Simulation Cases
        Params.initialize(model_parameters_path, schema_path)
        dLogger.info('Successfully initialized the Params class with the XML file.')

        self.p = Params
        self.save_path = ""
        # list of the Result objects (each object is for an instance of sensitivity analysis)
        self.results_list = dict()

        # data frame of all the sensitivity instances
        self.sensitivity_analysis = (not self.p.df_analysis.empty)
        if self.sensitivity_analysis:
            self.sens_df = self.p.df_analysis.loc[:, :]  # create a copy of the df, NOT a reference
            # edit the column names of the sensitivity df to be human readable
            human_readable_names = []
            for i, col_name in enumerate(self.sens_df.columns):
                human_readable_names.append(col_name[0] + ' ' + col_name[1])
            # self.sens_df = pd.DataFrame()
            self.sens_df.columns = human_readable_names
            self.sens_df.index.name = 'Case Number'

    def solve(self):
        verbose = self.p.instances[0].Scenario['verbose']
        if verbose:
            self.p.class_summary()
            # self.p.series_summary()
        self.p.validate()
        self.run()

    def run(self):
        starts = time.time()

        for key, value in self.p.instances.items():
            # this line can be removed after we finish developing the output files for sensitivity analysis - TN
            # for testing purposes
            value.instance_summary()

            ### MOVE THE FOLLOWING INTO STORAGEVET ABSTRACTION BARRIER ###
            # Move this u_logger path section to Params class - TN
            user_log_path = value.Results['dir_absolute_path']
            try:
                os.makedirs(user_log_path)
            except OSError:
                print("Creation of the user_log directory %s failed. Possibly already created." % user_log_path)
            else:
                print("Successfully created the user_log directory %s " % user_log_path)

            log_filename2 = user_log_path + "\\user_log.log"
            u_handler = logging.FileHandler(Path(log_filename2))
            u_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            u_logger = logging.getLogger('User')
            u_logger.setLevel(logging.DEBUG)
            u_logger.addHandler(u_handler)
            u_logger.info('Started logging...')

            ###############################################################

            if not value.other_error_checks():
                continue
            value.prepare_scenario()
            value.prepare_technology()
            value.prepare_services()
            value.prepare_finance()

            run = ScenarioSizing(value)
            run.add_technology()
            run.add_services()
            run.add_control_constraints()
            run.optimize_problem_loop()

            results = Result(run, value.Results)
            results.post_analysis()
            results.save_results_csv(str(key), self.sensitivity_analysis)

            if self.sensitivity_analysis:
                if not key:
                    for npv_col in results.financials.npv.columns:
                        self.sens_df[npv_col] = 0
                this_npv = results.financials.npv.reset_index(drop=True, inplace=False)
                this_npv.index = pd.RangeIndex(start=key, stop=key+1, step=1)
                self.sens_df.update(this_npv)

        ends = time.time()
        dLogger.info("DERVET runtime: ")
        dLogger.info(ends - starts)
        if self.sensitivity_analysis:
            self.sens_df.to_csv(path_or_buf=Path(user_log_path, 'sensitivity_summary.csv'))


if __name__ == '__main__':
    """
        the Main section for runStorageVET to run by itself without the GUI 
    """

    parser = argparse.ArgumentParser(prog='StorageVET.py',
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

    script_rel_path = sys.argv[0]
    dir_rel_path = script_rel_path[:-len('run_DERVET.py')]
    schema_rel_path = dir_rel_path + "SchemaDER.xml"

    case = DERVET(arguments.parameters_filename, schema_rel_path)
    case.solve()

    # print("Program is done.")
