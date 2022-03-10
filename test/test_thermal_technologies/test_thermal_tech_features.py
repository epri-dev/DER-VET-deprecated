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
"""
This file tests analysis cases that ONLY contain a SINGLE BATTERY. It is
organized by value stream combination and tests a bariety of optimization
horizons, time scale sizes, and other scenario options. All tests should pass.

The tests in this file can be run with DERVET and StorageVET, so make sure to
update TEST_PROGRAM with the lower case string name of the program that you
would like the tests to run on.

"""
import pytest
from pathlib import Path
import numpy as np
import numpy.testing as npt
from storagevet.ErrorHandling import *
from test.TestingLib import *


DIR = Path("./test/test_thermal_technologies/model_params")
JSON = '.json'
CSV = '.csv'

##adc_EChiller = None
##adc_NGChiller = None
##adc_HeatChiller = None

def thermal_case(test_file):
    results_instance = assert_ran(test_file)
    results = results_instance.instances[0]
    ts = results.time_series_data
    npv = results.cost_benefit_analysis.npv
    pro_forma = results.proforma_df()

    # these assertions are common across all thermal DER-VET cases
    assert_usecase_considered_services(results, ['retailTimeShift'])
    # thermal generation must meet or exceed load across all times
    assert_timeseries_col1_ge_col2(ts, 'Total Thermal Cooling Generation (kW)', 'Total Thermal Cooling Load (kW)')
    assert_timeseries_col1_ge_col2(ts, 'Total Thermal Hot Water Generation (kW)', 'Total Thermal Hot Water Load (kW)')
    assert_timeseries_col1_ge_col2(ts, 'Total Thermal Steam Generation (kW)', 'Total Thermal Steam Load (kW)')
    # total load will always be equal to or exceed original site load
    assert_timeseries_col1_ge_col2(ts, 'Total Load (kW)', 'LOAD: Site Load Original Load (kW)')
    assert_timeseries_col1_ge_col2(ts, 'Total Thermal Cooling Load (kW)', 'THERMAL LOAD: Site Cooling Thermal Load (kW)')
    assert_timeseries_col1_ge_col2(ts, 'Total Thermal Hot Water Load (kW)', 'THERMAL LOAD: Site Hot Water Thermal Load (kW)')
    assert_timeseries_col1_ge_col2(ts, 'Total Thermal Steam Load (kW)', 'THERMAL LOAD: Site Steam Thermal Load (kW)')
    # cooling generation has only a single technology source
    assert_timeseries_columns_equal(ts, 'Total Thermal Cooling Generation (kW)', 'CHILLER: chiller 1 Cooling Generation (kW)')

    return ts, npv, pro_forma

def test_thermal_001():
    test_file = DIR / f'001-CHP_EChiller{CSV}'
    ts, npv, pro_forma = thermal_case(test_file)
    # load dump should not exist
    assert_timeseries_columns_do_not_exist(ts, ['Load Dump (kW)'])
    # total load should have extra electric load from operation of the e-chiller
    assert_timeseries_columns_not_equal(ts, 'Total Load (kW)', 'LOAD: Site Load Original Load (kW)')
    # thermal loads stay the same
    assert_timeseries_columns_equal(ts, 'Total Thermal Cooling Load (kW)', 'THERMAL LOAD: Site Cooling Thermal Load (kW)')
    assert_timeseries_columns_equal(ts, 'Total Thermal Hot Water Load (kW)', 'THERMAL LOAD: Site Hot Water Thermal Load (kW)')
    assert_timeseries_columns_equal(ts, 'Total Thermal Steam Load (kW)', 'THERMAL LOAD: Site Steam Thermal Load (kW)')
    # fuel cost for chiller should be zero
    assert_npv_columns_are_zero(npv, ['CHILLER: chiller 1 Fuel Costs'])
    assert_pro_forma_columns_are_all_zeroes(npv, ['CHILLER: chiller 1 Fuel Costs'])

def test_thermal_002():
    test_file = DIR / f'002-CHP_EChiller_LoadDump_MaxExport{CSV}'
    ts, npv, pro_forma = thermal_case(test_file)
    # load dump should have positive values
    assert_timeseries_columns_exist(ts, ['Load Dump (kW)'])
    assert_timeseries_columns_have_positive_values(ts, ['Load Dump (kW)'])
    # total load should have extra electric load from operation of the e-chiller
    assert_timeseries_columns_not_equal(ts, 'Total Load (kW)', 'LOAD: Site Load Original Load (kW)')
    # thermal loads stay the same
    assert_timeseries_columns_equal(ts, 'Total Thermal Cooling Load (kW)', 'THERMAL LOAD: Site Cooling Thermal Load (kW)')
    assert_timeseries_columns_equal(ts, 'Total Thermal Hot Water Load (kW)', 'THERMAL LOAD: Site Hot Water Thermal Load (kW)')
    assert_timeseries_columns_equal(ts, 'Total Thermal Steam Load (kW)', 'THERMAL LOAD: Site Steam Thermal Load (kW)')
    # fuel cost for chiller should be zero
    assert_npv_columns_are_zero(npv, ['CHILLER: chiller 1 Fuel Costs'])
    assert_pro_forma_columns_are_all_zeroes(npv, ['CHILLER: chiller 1 Fuel Costs'])
    ##adc_EChiller = npv['Avoided Demand Charge'][0]

def test_thermal_003():
    test_file = DIR / f'003-CHP_EChiller_LoadDump_NoPOIConstraint{CSV}'
    ts, npv, pro_forma = thermal_case(test_file)
    # load dump should be all zeroes
    assert_timeseries_columns_exist(ts, ['Load Dump (kW)'])
    assert_timeseries_columns_are_all_zeroes(ts, ['Load Dump (kW)'])
    # total load should have extra electric load from operation of the e-chiller
    assert_timeseries_columns_not_equal(ts, 'Total Load (kW)', 'LOAD: Site Load Original Load (kW)')
    # thermal loads stay the same
    assert_timeseries_columns_equal(ts, 'Total Thermal Cooling Load (kW)', 'THERMAL LOAD: Site Cooling Thermal Load (kW)')
    assert_timeseries_columns_equal(ts, 'Total Thermal Hot Water Load (kW)', 'THERMAL LOAD: Site Hot Water Thermal Load (kW)')
    assert_timeseries_columns_equal(ts, 'Total Thermal Steam Load (kW)', 'THERMAL LOAD: Site Steam Thermal Load (kW)')
    # fuel cost for chiller should be zero
    assert_npv_columns_are_zero(npv, ['CHILLER: chiller 1 Fuel Costs'])
    assert_pro_forma_columns_are_all_zeroes(npv, ['CHILLER: chiller 1 Fuel Costs'])

def test_thermal_004():
    test_file = DIR / f'004-CHP_EChiller_LoadDump_LargeMaxExport{CSV}'
    ts, npv, pro_forma = thermal_case(test_file)
    # load dump should be all zeroes
    assert_timeseries_columns_exist(ts, ['Load Dump (kW)'])
    assert_timeseries_columns_are_all_zeroes(ts, ['Load Dump (kW)'])
    # total load should have extra electric load from operation of the e-chiller
    assert_timeseries_columns_not_equal(ts, 'Total Load (kW)', 'LOAD: Site Load Original Load (kW)')
    # thermal loads stay the same
    assert_timeseries_columns_equal(ts, 'Total Thermal Cooling Load (kW)', 'THERMAL LOAD: Site Cooling Thermal Load (kW)')
    assert_timeseries_columns_equal(ts, 'Total Thermal Hot Water Load (kW)', 'THERMAL LOAD: Site Hot Water Thermal Load (kW)')
    assert_timeseries_columns_equal(ts, 'Total Thermal Steam Load (kW)', 'THERMAL LOAD: Site Steam Thermal Load (kW)')
    # fuel cost for chiller should be zero
    assert_npv_columns_are_zero(npv, ['CHILLER: chiller 1 Fuel Costs'])
    assert_pro_forma_columns_are_all_zeroes(npv, ['CHILLER: chiller 1 Fuel Costs'])

def test_thermal_005():
    test_file = DIR / f'005-CHP_NGChiller_LoadDump_MaxExport{CSV}'
    ts, npv, pro_forma = thermal_case(test_file)
    # load dump should have positive values
    assert_timeseries_columns_exist(ts, ['Load Dump (kW)'])
    assert_timeseries_columns_have_positive_values(ts, ['Load Dump (kW)'])
    # No additional Electric Load (Total Load should equal Original Site Load)
    assert_timeseries_columns_equal(ts, 'Total Load (kW)', 'LOAD: Site Load Original Load (kW)')
    # thermal loads stay the same
    assert_timeseries_columns_equal(ts, 'Total Thermal Cooling Load (kW)', 'THERMAL LOAD: Site Cooling Thermal Load (kW)')
    assert_timeseries_columns_equal(ts, 'Total Thermal Hot Water Load (kW)', 'THERMAL LOAD: Site Hot Water Thermal Load (kW)')
    assert_timeseries_columns_equal(ts, 'Total Thermal Steam Load (kW)', 'THERMAL LOAD: Site Steam Thermal Load (kW)')
    # fuel cost for NGchiller should be non-zero
    assert_npv_columns_are_negative(npv, ['CHILLER: chiller 1 Fuel Costs'])
    assert_pro_forma_columns_are_all_negative(npv, ['CHILLER: chiller 1 Fuel Costs'])
    ##adc_NGChiller = npv['Avoided Demand Charge'][0]
    ##assert adc_EChiller < adc_NGChiller

def test_thermal_006():
    test_file = DIR / f'006-CHP_HeatChiller_LoadDump_MaxExport{CSV}'
    ts, npv, pro_forma = thermal_case(test_file)
    # load dump should have positive values
    assert_timeseries_columns_exist(ts, ['Load Dump (kW)'])
    assert_timeseries_columns_have_positive_values(ts, ['Load Dump (kW)'])
    # No additional Electric Load (Total Load should equal Original Site Load)
    assert_timeseries_columns_equal(ts, 'Total Load (kW)', 'LOAD: Site Load Original Load (kW)')
    # additional thermal hot water load from operating a heat chiller
    assert_timeseries_columns_equal(ts, 'Total Thermal Cooling Load (kW)', 'THERMAL LOAD: Site Cooling Thermal Load (kW)')
    assert_timeseries_columns_not_equal(ts, 'Total Thermal Hot Water Load (kW)', 'THERMAL LOAD: Site Hot Water Thermal Load (kW)')
    assert_timeseries_columns_equal(ts, 'Total Thermal Steam Load (kW)', 'THERMAL LOAD: Site Steam Thermal Load (kW)')
    # fuel cost for chiller should be zero
    assert_npv_columns_are_zero(npv, ['CHILLER: chiller 1 Fuel Costs'])
    assert_pro_forma_columns_are_all_zeroes(npv, ['CHILLER: chiller 1 Fuel Costs'])
    ##adc_HeatChiller = npv['Avoided Demand Charge'][0]
    ##assert adc_EChiller < adc_HeatChiller

def test_inactive_chiller():
    # following should fail
    # a cooling load exists, but no active chiller
    with pytest.raises(ModelParameterError):
        check_initialization(DIR / f'007-NoActiveChiller{CSV}')

def test_no_heat_source_for_heat_chiller():
    # following should fail
    # a heat chiller is active, but no heat source technology
    with pytest.raises(ModelParameterError):
        check_initialization(DIR / f'008-HeatChiller-NoActiveCHP-NoActiveBoiler{CSV}')

def test_no_cooling_load_for_active_chiller():
    # following should fail
    # a chiller is active, but no cooling load is input
    with pytest.raises(ModelParameterError):
        check_initialization(DIR / f'009-ActiveChiller-NoCoolingLoad{CSV}')

def test_no_heating_load_for_active_boiler():
    # following should fail
    # a boiler is active, but no heating load is input
    with pytest.raises(ModelParameterError):
        check_initialization(DIR / f'010-ActiveBoiler-NoHeatingLoads{CSV}')

def test_no_heating_load_for_active_chp():
    # following should fail
    # a chp is active, but no heating load is input
    with pytest.raises(ModelParameterError):
        check_initialization(DIR / f'011-ActiveCHP-NoHeatingLoads{CSV}')

def test_no_hotwater_load_for_active_boiler():
    # following should pass
    # a boiler is active, but no hot water load is input; a steam load is present
    test_file = DIR / f'012-ActiveBoiler-NoHotWaterLoad{CSV}'
    ts, npv, pro_forma = thermal_case(test_file)
    # all hot water columns should be zeroes
    assert_timeseries_columns_are_all_zeroes(ts, [
        'BOILER: boiler 1 Hot Water Generation (kW)', 'THERMAL LOAD: Site Hot Water Thermal Load (kW)',
        'Total Thermal Hot Water Load (kW)', 'Total Thermal Hot Water Generation (kW)',
    ])

def test_no_steam_load_for_active_boiler():
    # following should pass
    # a boiler is active, but no steam load is input; a hot water load is present
    test_file = DIR / f'013-ActiveBoiler-NoSteamLoad{CSV}'
    ts, npv, pro_forma = thermal_case(test_file)
    # all steam columns should be zeroes
    assert_timeseries_columns_are_all_zeroes(ts, [
        'BOILER: boiler 1 Steam Generation (kW)', 'THERMAL LOAD: Site Steam Thermal Load (kW)',
        'Total Thermal Steam Load (kW)', 'Total Thermal Steam Generation (kW)',
    ])

