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
This file tests analysis cases have to do with the emissions reduction module.

"""
import pytest
from pathlib import Path
from test.TestingLib import *
from storagevet.ErrorHandling import *


MP = Path("./test/model_params")
JSON = '.json'
CSV = '.csv'
TEMP_PATH = Path(r"C:\Users\phna001\Documents\dervet-gui\DervetBackEnd\dervet\Model_Parameters_Template_DER.csv")

"""
Load shedding TESTS
"""


MAX_PERCENT_ERROR = 3


class TestEmissionsParetoAnalysis:
    def setup_class(self):
        self.mp_name = TEMP_PATH
        self.results = run_case(self.mp_name)
        # self.validated_folder = RESULTS / Path("./reliability_load_shed1")

    def test_services_were_part_of_problem(self):
        assert_usecase_considered_services(self.results, ['DA', 'ER'])

    # def test_proforma_results_are_expected(self):
    #     compare_proforma_results(self.results, self.validated_folder / "pro_forma_2mw_5hr.csv",
    #                              MAX_PERCENT_ERROR)
    #
    # def test_size_results_are_expected(self):
    #     compare_size_results(self.results, self.validated_folder / "size_2mw_5hr.csv",
    #                          MAX_PERCENT_ERROR)

