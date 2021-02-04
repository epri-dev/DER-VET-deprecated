from dervet.DERVET import DERVET
from storagevet.run_StorageVET import StorageVET
import os
import pandas as pd


DERVET_DICT = {'schema': "./dervet/SchemaDER.xml",
               'run_script': DERVET}
STORAGEVET_DICT = {'schema': "./dervet/storagevet/Schema.xml",
                   'run_script': StorageVET}

TEST_DICT = {'storagevet': STORAGEVET_DICT,
             'dervet': DERVET_DICT}


def run_case(model_param_location: str, program: str):
    print(f"Testing {program}...")
    case = TEST_DICT[program]['run_script'](model_param_location, TEST_DICT[program]['schema'])
    results = case.solve()
    print(results.dir_abs_path)
    return results


def assert_file_exists(model_results, results_file_name='timeseries_results'):
    if model_results.sensitivity_df.empty:
        check_for_file = model_results.dir_abs_path / f'{results_file_name}{model_results.csv_label}.csv'
        assert os.path.isfile(check_for_file), f'No {results_file_name} found at {check_for_file}'
    else:
        for index in model_results.instances.keys():
            check_for_file = model_results.dir_abs_path / str(index) / f'{results_file_name}{model_results.csv_label}.csv'
            assert os.path.isfile(check_for_file), f'No {results_file_name} found at {check_for_file}'


def assert_within_error_bound(actual: float, test_value: float, error_bound: float, error_message: str):
    diff = abs(actual-test_value)
    if not diff:
        return
    assert diff/actual <= error_bound/100, error_message + f'Test value: {test_value}   Should be in range: ({actual+(actual*(error_bound/100))},{actual-(actual*(error_bound/100))}) \n'


##########################################


def assert_ran(model_param_location: str, program: str):
    results = run_case(model_param_location, program)
    assert_file_exists(results)


def compare_proforma_results(results, frozen_proforma_location: str, error_bound: float):
    assert_file_exists(results, 'pro_forma')
    test_proforma_df = results.proforma_df()
    actual_df = pd.read_csv(frozen_proforma_location, index_col='Unnamed: 0')
    for yr_indx, values_series in actual_df.iterrows():
        try:
            actual_indx = pd.Period(yr_indx)
        except ValueError:
            actual_indx = yr_indx
        assert actual_indx in test_proforma_df.index, f'{actual_indx} not in test proforma index'
        for col_indx in values_series.index:
            assert col_indx in test_proforma_df.columns, f'{col_indx} not in test proforma columns'
            error_message = f'ValueError in Proforma [{yr_indx}, {col_indx}]\n'
            assert_within_error_bound(actual_df.loc[yr_indx, col_indx], test_proforma_df.loc[actual_indx, col_indx], error_bound, error_message)


def check_lcpc(results, test_model_param_location: str):
    # asset file exists
    assert_file_exists(results, 'load_coverage_prob')
    test_lcpc_pd = results.instances[0].drill_down_dict['load_coverage_prob']
    # get max # of hours that value of lcpc is 1
    test_covered_hrs = sum(test_lcpc_pd['Load Coverage Probability (%)'] == 1)
    # get target hours
    case_mp_pd = pd.read_csv(test_model_param_location)
    try:
        target_covered_hours = case_mp_pd.loc[(case_mp_pd['Tag'] == 'Reliability') & (case_mp_pd['Key'] == 'target'), 'Value']
    except KeyError:
        target_covered_hours = case_mp_pd.loc[(case_mp_pd['Tag'] == 'Reliability') & (case_mp_pd['Key'] == 'target'), 'Optimization Value']
    target_covered_hours = int(target_covered_hours.values[0])
    assert target_covered_hours <= test_covered_hrs, f'Hours covered: {test_covered_hrs}\nExpected: {target_covered_hours}'


def compare_size_results(results, frozen_size_location: str, error_bound: float):
    assert_file_exists(results, 'size')  # assert that results exists
    test_df = results.instances[0].sizing_df
    try:
        test_df.set_index("DER", inplace=True)
    except KeyError:
        pass
    actual_df = pd.read_csv(frozen_size_location, index_col='DER')
    for der_name in actual_df.index:
        for col in actual_df.columns:
            test_value = test_df.loc[der_name, col]
            actual_value = actual_df.loc[der_name, col]
            if str(test_value) != 'nan' and str(actual_value) != 'nan':
                error_message = f'ValueError in [{der_name}, {col}]\nExpected: {actual_value}\nGot: {test_value}'

                assert_within_error_bound(actual_value, test_value, error_bound, error_message)


def compare_lcpc_results(results, frozen_lcpc_location: str, error_bound: float):
    test_df = results.instances[0].drill_down_dict.get('load_coverage_prob')
    assert test_df is not None
    actual_df = pd.read_csv(frozen_lcpc_location)
    for time_step in actual_df.index:

        test_value = test_df.loc[time_step]['Load Coverage Probability (%)']
        actual_value = actual_df.loc[time_step]['Load Coverage Probability (%)']
        if test_value is not 'nan' and actual_value is not 'nan':
            error_message = f'ValueError in [{time_step}]\nExpected: {actual_value}\nGot: {test_value}'

            assert_within_error_bound(actual_value, test_value, error_bound, error_message)
