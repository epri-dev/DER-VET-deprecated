"""
Copyright (c) 2021, Electric Power Research Institute

 All rights reserved.

 Redistribution and use in source and binary forms, with or without modification,
 are permitted provided that the following conditions are met:

     * Redistributions of source code must retain the above copyright notice,
       this list of conditions and the following disclaimer.
     * Redistributions in binary form must reproduce the above copyright notice,
       this list of conditions and the following disclaimer in the documentation
       and/or other materials provided with the distribution.
     * Neither the name of DER-VET nor the names of its contributors
       may be used to endorse or promote products derived from this software
       without specific prior written permission.

 THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
 PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
 LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
 NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
 SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
from dervet.DERVET import DERVET
import os
import pandas as pd
from pathlib import Path

def _checkThatFileExists(f, name='Unlabeled', raise_exception_on_fail=True, write_msg_to_terminal=True):
    path_file = Path(f)
    if write_msg_to_terminal:
        msg = f'\n{name} file:\n  {path_file.resolve()}'
        print(msg)
    if not path_file.is_file():
        if raise_exception_on_fail:
            raise FileNotFoundError(f'\n\nFAIL: Your specified {name} file does not exist:\n{path_file.resolve()}\n')
        else:
            print(f'\n\nFAIL: Your specified {name} file does not exist:\n{path_file.resolve()}\n')
            return None
    return path_file

def run_case(model_param_location: str):
    print(f"Testing {model_param_location}...")
    # first make sure the model_param file exists
    model_param_file = _checkThatFileExists(Path(model_param_location), 'Model Parameter Input File')
    case = DERVET(model_param_file)
    results = case.solve()
    print(results.dir_abs_path)
    return results


def check_initialization(model_param_location: str):
    print(f"Testing {model_param_location}...")
    # first make sure the model_param file exists
    model_param_file = _checkThatFileExists(Path(model_param_location), 'Model Parameter Input File')
    case = DERVET(model_param_file)
    return case


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


def assert_ran(model_param_location: str):
    results = run_case(model_param_location)
    assert_file_exists(results)
    return results


def assert_ran_with_services(model_param_location: str, services: list):
    results = run_case(model_param_location)
    assert_file_exists(results)
    value_stream_keys = results.instances[0].service_agg.value_streams.keys()
    print(set(value_stream_keys))
    assert set(services) == set(value_stream_keys)


def assert_usecase_considered_services(results, services: list):
    value_stream_keys = results.instances[0].service_agg.value_streams.keys()
    print(set(value_stream_keys))
    assert set(services) == set(value_stream_keys)

def assert_timeseries_columns_exist(ts, items: list):
    timeseries_columns = ts.columns
    assert set(items).issubset(timeseries_columns)

def assert_timeseries_columns_do_not_exist(ts, items: list):
    timeseries_columns = ts.columns
    assert not set(items).intersection(timeseries_columns)

def assert_timeseries_columns_are_all_zeroes(ts, items: list):
    ts_subset = ts[items]
    max_tf = ts_subset.max().between(-1e-5, 1e-5)
    min_tf = ts_subset.min().between(-1e-5, 1e-5)
    print(max_tf, min_tf)
    assert all(max_tf) & all(min_tf)

def assert_timeseries_columns_have_positive_values(ts, items: list):
    ts_subset = ts[items]
    max_tf = ts_subset.max().gt(1e-5)
    assert all(max_tf)

def assert_timeseries_columns_have_negative_values(ts, items: list):
    ts_subset = ts[items]
    min_tf = ts_subset.min().gt(1e-5)
    assert all(min_tf)

def assert_timeseries_columns_equal(ts, col1: str, col2: str):
    # across all times
    ts_diff = ts[col1] - ts[col2]
    assert ts_diff.abs().max() < 1e-5

def assert_timeseries_columns_not_equal(ts, col1: str, col2: str):
    # across all times
    ts_diff = ts[col1] - ts[col2]
    assert ts_diff.abs().max() > 1e-5

def assert_timeseries_col1_ge_col2(ts, col1: str, col2: str):
    # across all times
    ts_diff = ts[col1] - ts[col2]
    assert all(ts_diff.ge(-1e-5))

def assert_npv_columns_are_zero(npv, items: list):
    # npv only has one row
    npv_subset = npv[items]
    tf = npv_subset.max().between(-1e-5, 1e-5)
    assert all(tf)

def assert_npv_columns_are_negative(npv, items: list):
    # npv only has one row; negative represents a cost
    npv_subset = npv[items]
    tf = npv_subset.max().lt(0)
    assert all(tf)

def assert_pro_forma_columns_are_all_zeroes(pf, items: list):
    pf_subset = pf[items]
    max_tf = pf_subset.max().between(-1e-5, 1e-5)
    min_tf = pf_subset.min().between(-1e-5, 1e-5)
    assert all(max_tf) & all(min_tf)

def assert_pro_forma_columns_are_all_negative(pf, items: list):
    pf_subset = pf[items]
    max_tf = pf_subset.max().lt(0)
    min_tf = pf_subset.min().lt(0)
    assert all(max_tf) & all(min_tf)

def compare_proforma_results(results, frozen_proforma_location: str, error_bound: float,
                             opt_years=None):
    assert_file_exists(results, 'pro_forma')
    test_proforma_df = results.proforma_df()
    expected_df = pd.read_csv(frozen_proforma_location, index_col='Unnamed: 0')
    for yr_indx, values_series in expected_df.iterrows():
        try:
            actual_indx = pd.Period(yr_indx)
            if opt_years is not None and actual_indx.year not in opt_years:
                continue
        except ValueError:
            actual_indx = yr_indx
        # print(actual_indx)
        assert actual_indx in test_proforma_df.index, f'{actual_indx} not in test proforma index'
        for col_indx in values_series.index:
            assert col_indx in test_proforma_df.columns, f'{col_indx} not in test proforma columns'
            error_message = f'ValueError in Proforma [{yr_indx}, {col_indx}]\n'
            assert_within_error_bound(expected_df.loc[yr_indx, col_indx], test_proforma_df.loc[actual_indx, col_indx], error_bound, error_message)


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
