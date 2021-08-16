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
from test.TestingLib import *


DIR = Path("./test/model_params")
JSON = '.json'
CSV = '.csv'


def test_battery_timeseries_constraints():
    test_file = DIR / f'001-DA_FR_SR_NSR_battery_month_ts_constraints{CSV}'
    results = assert_ran(test_file)
    case_results = results.instances[0]
    timeseries = case_results.time_series_data
    discharge_constraint = timeseries['BATTERY: battery User Discharge Max (kW)']
    charge_constraint = timeseries['BATTERY: battery User Charge Max (kW)']
    assert np.all(timeseries['BATTERY: battery Discharge (kW)'] <= discharge_constraint)
    assert np.all(timeseries['BATTERY: battery Charge (kW)'] <= charge_constraint)


class TestEVGuiUseCase:
    """ Tests to ensure the EV Use Case (Fleet EV) in the GUI funtions properly in DER-VET"""


    def setup_class(self):
        self.results = run_case(DIR / f"ev_gui_case_study{JSON}")
        self.results_instance = self.results.instances[0]
        self.ts = self.results_instance.time_series_data
        self.ch = self.ts['ELECTRICVEHICLE2: partially controllable ev fleet Charge (kW)']
        self.base_load = self.ts['ELECTRICVEHICLE2: partially controllable ev fleet EV Fleet Baseline Load']
        self.max_load_ctrl = 0.5


    def test_services_are_active(self):
        assert_usecase_considered_services(self.results, ['DCM', 'retailTimeShift'])


    def test_dcm_billing_periods_count(self):
        assert self.results_instance.service_agg.value_streams['DCM'].tariff.shape[0] == 4


    def test_rts_billing_periods_count(self):
        assert self.results_instance.service_agg.value_streams['retailTimeShift'].tariff.shape[0] == 10


    def test_fleetEV_ch_constraint(self):
        # base_load >= ch
        npt.assert_approx_equal(min(self.base_load / self.ch), 1, significant=15)


    def test_fleetEV_max_load_ctrl_constraint(self):
        # ch >= base_load * 0.5
        npt.assert_approx_equal(max(self.ch / (self.max_load_ctrl * self.base_load)), 2, significant=15)
