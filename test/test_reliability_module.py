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
This file tests analysis cases have to do with the reliability module.

NOTE there are reliability module tests in test_beta_release_validation_report. This file tests
features that were not showcased through the validation report

"""
import pytest
from pathlib import Path
from test.TestingLib import *
from storagevet.ErrorHandling import *

RESULTS = Path("./test/test_load_shedding/results")
SIZING_RESULTS = Path("./test/test_load_shedding/results/Sizing")
LOAD_FOLLOWING_MP = Path("./test/test_load_shedding/mp")
LOAD_FOLLOWING_MP_SIZING = LOAD_FOLLOWING_MP / "Sizing"
MP = Path("./test/model_params")
JSON = '.json'
CSV = '.csv'


"""
Load shedding TESTS
"""


MAX_PERCENT_ERROR = 3


class TestLoadShedding:
    def setup_class(self):
        self.mp_name = LOAD_FOLLOWING_MP / "Model_Parameters_Template_DER_w_ls1.csv"
        self.results = run_case(self.mp_name)
        self.validated_folder = RESULTS / Path("./reliability_load_shed1")

    def test_lcpc_exists(self):
        assert_file_exists(self.results, 'load_coverage_prob')

    def test_proforma_results_are_expected(self):
        compare_proforma_results(self.results, self.validated_folder / "pro_forma_2mw_5hr.csv",
                                 MAX_PERCENT_ERROR)

    def test_size_results_are_expected(self):
        compare_size_results(self.results, self.validated_folder / "size_2mw_5hr.csv",
                             MAX_PERCENT_ERROR)


class TestWoLoadShedding:

    def setup_class(self):
        self.mp_name = LOAD_FOLLOWING_MP / "Model_Parameters_Template_DER_wo_ls1.csv"
        self.results = run_case(self.mp_name)
        self.validated_folder = RESULTS / Path("./reliability_load_shed_wo_ls1")

    def test_lcpc_exists(self):
        assert_file_exists(self.results, 'load_coverage_prob')

    def test_proforma_results_are_expected(self):
        compare_proforma_results(self.results, self.validated_folder / "pro_forma_2mw_5hr.csv",
                                 MAX_PERCENT_ERROR)

    def test_size_results_are_expected(self):
        compare_size_results(self.results, self.validated_folder / "size_2mw_5hr.csv",
                             MAX_PERCENT_ERROR)


class TestSizingLoadShedding:
    def setup_class(self):
        self.mp_name = LOAD_FOLLOWING_MP_SIZING / "Model_Parameters_Template_DER_w_ls1.csv"
        self.results = run_case(self.mp_name)
        self.validated_folder = SIZING_RESULTS / Path("./w_ls1")

    def test_lcpc_exists(self):
        assert_file_exists(self.results, 'load_coverage_prob')

    def test_proforma_results_are_expected(self):
        compare_proforma_results(self.results, self.validated_folder / "pro_forma_2mw_5hr.csv",
                                 MAX_PERCENT_ERROR)

    def test_size_results_are_expected(self):
        compare_size_results(self.results, self.validated_folder / "size_2mw_5hr.csv",
                             MAX_PERCENT_ERROR)


class TestSizingWoLoadShedding:
    def setup_class(self):
        self.mp_name = LOAD_FOLLOWING_MP_SIZING / "Model_Parameters_Template_DER_wo_ls1.csv"
        self.results = run_case(self.mp_name)
        self.validated_folder = SIZING_RESULTS / Path("./wo_ls1")

    def test_lcpc_exists(self):
        assert_file_exists(self.results, 'load_coverage_prob')

    def test_proforma_results_are_expected(self):
        compare_proforma_results(self.results, self.validated_folder / "pro_forma_2mw_5hr.csv",
                                 MAX_PERCENT_ERROR)

    def test_size_results_are_expected(self):
        compare_size_results(self.results, self.validated_folder / "size_2mw_5hr.csv",
                             MAX_PERCENT_ERROR)


def test_post_facto_calculations_with_user_constraints():
    assert_ran(MP / f"Model_Parameters_Template_issue162{CSV}")


def test_post_facto_calculations_with_user_constraints_error():
    with pytest.raises(ArithmeticError):
        assert_ran(MP / f"Model_Parameters_Template_issue162_error{CSV}")


def test_battery_sizing4reliability_soc_init_small():
    with pytest.raises(ParameterError):
        assert_ran(MP / f"EV_Battery_Sizing_MP{CSV}")


def test_post_facto_dg_only():
    assert_ran(MP / f"Reliability_DG{CSV}")
