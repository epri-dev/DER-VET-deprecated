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
This file tests features of the CBA module. All tests should pass.

The tests in this file can be run with .

"""
import pytest
from test.TestingLib import assert_ran, run_case
from storagevet.ErrorHandling import *
import numpy as np


CBA_DIR = r".\Testing\cba_validation\Model_params"
MP_DIR = Path("./test/model_params")

DIR = Path("./test/test_cba_validation/model_params")
"""
Evaluation column tests
TODO add test to make sure that evaluation data of different dt is caught
"""


class TestEvaluateBatteryICECostsToZero:

    def setup_class(self):
        # run case
        run_results = run_case(DIR / "001-cba_valuation.csv")
        # get proforma
        self.actual_proforma = run_results.proforma_df()

    def test_battery_capital_cost(self):
        # capital cost should 0
        capital_cost = self.actual_proforma.loc[:, 'BATTERY: 2mw-5hr Capital Cost'].values
        assert np.all(capital_cost == 0)

    def test_battery_variable_om(self):
        # variable OM costs are 0
        variable_om = self.actual_proforma.loc[:, 'BATTERY: 2mw-5hr Variable O&M Cost'].values
        assert np.all(variable_om == 0)

    def test_battery_fixed_om(self):
        # fixed OM costs are 0
        fixed_om = self.actual_proforma.loc[:, 'BATTERY: 2mw-5hr Fixed O&M Cost'].values
        assert np.all(fixed_om == 0)

    def test_ice_capital_cost(self):
        # capital cost should 0
        capital_cost = self.actual_proforma.loc[:, 'ICE: ice gen Capital Cost'].values
        assert np.all(capital_cost == 0)

    def test_ice_variable_om(self):
        # variable OM costs are 0
        variable_om = self.actual_proforma.loc[:, 'ICE: ice gen Variable O&M Costs'].values
        assert np.all(variable_om == 0)

    def test_ice_fixed_om(self):
        # fixed OM costs are 0
        fixed_om = self.actual_proforma.loc[:, 'ICE: ice gen Fixed O&M Cost'].values
        assert np.all(fixed_om == 0)

    def test_ice_fuel(self):
        # fuel costs are 0
        fuel = self.actual_proforma.loc[:, 'ICE: ice gen Fuel Costs'].values
        assert np.all(fuel == 0)


def test_sensitivity_evaluation():
    # TODO check that post-facto cash flows are ZERO
    assert_ran(DIR / '003-cba_valuation_sensitivity.csv', )


def test_coupled_evaluation():
    # TODO check that post-facto cash flows are ZERO
    assert_ran(DIR / '004-cba_valuation_coupled_dt.csv', )


def xtest_tariff():  # TODO
    assert_ran(DIR / '106-cba_tariff.csv', )


def test_monthly():
    # TODO check that post-facto cash flows are ZERO
    assert_ran(DIR / '005-cba_monthly_timseries.csv', )


def test_catch_wrong_length():
    # trying to do sensetivity analysis and evaluation columns
    # following should fail
    with pytest.raises(ModelParameterError):
        assert_ran(DIR / '002-catch_wrong_length.csv', )


"""
Analysis end mode tests
"""


class TestLongestLifetimeNoReplacement:
    """ Battery lifetime = 14 years, PV lifetime = 13 years, ICE lifetime = 12
    analysis_horizon_mode = 3, start_year = 2017
    """
    def setup_class(self):
        run_results = run_case(DIR / "longest_lifetime.csv")
        # get proforma
        self.actual_proforma = run_results.proforma_df()

    def xtest_decommissing_cost(self):
        #  decomissioning costs show up on the last year the equipment is expect to last
        pass

    def xtest_replacement_cost(self):
        #  no replacement costs
        pass

    def test_proforma_length(self):
        #  proforma should be the length of the longest life time + 1 year
        expected_length = 14 + 1
        assert len(self.actual_proforma.index) == expected_length

    def xtest_no_der_costs_after_der_last_year_of_life(self):
        #  no costs for a DER after the end of its expected life time
        pass


class TestLongestLifetimeReplacements:
    """ Battery lifetime = 14 years, PV lifetime = 13 years, ICE lifetime = 12 ALL replaceable
    analysis_horizon_mode = 3, start_year = 2017
    """
    def setup_class(self):
        run_results = run_case(DIR / "longest_lifetime_replaceble.csv")
        # get proforma
        self.actual_proforma = run_results.proforma_df()

    def xtest_decommissing_cost(self):
        #  all decomissioning costs should be on the last year
        pass

    def xtest_replacement_cost(self):
        #  check to make sure there are replacement costs on the years that a new DER is installed
        pass

    def test_proforma_length(self):
        #  proforma should be the length of the longest life time + 1 year
        expected_length = 14 + 1
        assert len(self.actual_proforma.index) == expected_length


class TestShortestLifetime:

    def setup_class(self):
        run_results = run_case(DIR / "shortest_lifetime.csv")
        # get proforma
        self.actual_proforma_no_replacements = run_results.proforma_df()
        run_results = run_case(DIR / "shortest_lifetime_replaceble.csv")
        # get proforma
        self.actual_proforma_replacements = run_results.proforma_df()

    def xtest_decommissing_cost_no_replacements(self):
        #  all decomissioning costs should be on the last year
        pass

    def xtest_replacement_cost_no_replacements(self):
        #  no replacement costs
        pass

    def xtest_proforma_length_no_replacements(self):
        #  proforma should be the same as shortest_lifetime_replacement
        pass

    def xtest_decommissing_cost_replacements(self):
        #  all decomissioning costs should be on the last year
        pass

    def xtest_replacement_cost_replacements(self):
        #  no replacement costs
        pass

    def xtest_proforma_length_replacements(self):
        #  proforma should be the same as shortest_lifetime_replacement
        pass

    def test_replacements_and_no_replacements_same_proforma(self):
        assert np.all(self.actual_proforma_replacements == self.actual_proforma_no_replacements)


# mode==2 + a DER is being sized
def test_shortest_lifetime_sizing_error():
    with pytest.raises(Exception):
        run_case(DIR / "shortest_lifetime_sizing_error.csv", )


# mode==3 + a DER is being sized
def test_longest_lifetime_sizing_error():
    with pytest.raises(Exception):
        run_case(DIR / "longest_lifetime_sizing_error.csv", )


"""
End of life cost tests
"""


def xtest_linear_salvage_value():
    # TODO check to make sure that salvage value is some nonzero value
    assert_ran(CBA_DIR + r"\110-linear_salvage_value.csv", )


def xtest_user_defined_salvage_value():
    # TODO check to make sure that salvage value is some nonzero value
    assert_ran(CBA_DIR + r"\user_salvage_value.csv", )


def xtest_shortest_lifetime_linear_salvage():
    assert_ran(DIR / "shortest_lifetime_linear_salvage.csv")


"""
Non-initial investment payment options: PPA, ECC
"""


# mode==4 + e==d
def xtest_carrying_cost_d_is_e_error():
    with pytest.raises(Exception):  # TODO
        run_case(DIR / "109-carrying_cost_d_is_e_error.csv")


def xtest_ppa():
    """ Test solar's PPA feature"""
    assert_ran(DIR / "ppa_payment.csv")


def xtest_carrying_cost_replacable():
    """ 3 DERs all replaceable for the duration of the project
    This test will check for :
        1) proforma is length of lifetime + 1
        2) no replacement costs
        3) decomissioning cost should be on the last year
        4) capital cost column should be replaced with economic carrying
            capacity
        5) in proforma, economic carrying capacity column should have a value
            for every row except CAPEX Year
        6) taxes dont appear in proforma
        7) ecc breakdown CSV in results
    """
    assert_ran(r" ", )    # TODO


def xtest_carrying_cost_not_replacable():
    """ 3 DERs all not replaceable for the duration of the project
    This test will check for :
        1) proforma is length of lifetime + 1
        2) replacement costs
        3) decomissioning cost should be on the last year
        4) capital cost column should be replaced with economic carrying
            capacity
        6) taxes dont appear in proforma
        7) ecc breakdown CSV in results
    """
    assert_ran(r" ", )    # TODO


def xtest_carrying_cost_error():
    """ 3 DERs not all are replaceable"""
    # ECC should be run in a Reliability/Deferral case
    with pytest.raises(ModelParameterError):
        run_case(CBA_DIR + r"\108-carrying_cost_eccPerc_error.csv", )


def xtest_ecc_zero_out():
    """ Test that value from services are 0-ed"""
    # TODO
    assert_ran(r" ", )


def xtest_ecc_shorter_actual_lifetime():
    """ Test ECC calculations when batteries degradation module results in a
        shorter lifetime than user given"""    # TODO
    assert_ran(r" ", )


def xtest_ecc_long_actual_lifetime():
    """ Test ECC calculations when batteries degradation module results in a
        longer lifetime than user given"""    # TODO
    assert_ran(r" ", )


"""
All other tests for the cost benefit analysis and financials class
"""


def xtest_da_month_degradation_predict_when_battery_will_be_replaced():
    assert_ran(CBA_DIR +
               r"\Model_Parameters_Template_ENEA_S1_8_12_UC1_DAETS_" +
               r"doesnt_reach_eol_during_opt.csv", )


class TestAssetDepreciation:

    def setup_class(self):
        run_results = run_case(MP_DIR / "002-tax_scenario.csv")
        # get tax calculation data frame
        self.actual_tax_calc = run_results.instances[0].cost_benefit_analysis.tax_calculations

    def test_macrs_depreciation(self):
        actual_depreciation = [0, -274972.5, -366712.5, -122182.5, -61132.5, 0, 0, 0, 0, 0,
                               0, 0, 0, 0, 0]
        assert list(self.actual_tax_calc['BATTERY: es MACRS Depreciation'].values) == \
               actual_depreciation

    def test_zero_tax_in_capex(self):
        assert self.actual_tax_calc.loc['CAPEX Year', 'Taxable Yearly Net'] == 0

    def test_sign_of_state_tax(self):
        no_capex_year = self.actual_tax_calc[self.actual_tax_calc.index != 'CAPEX Year']
        taxable = no_capex_year['Taxable Yearly Net'].values
        state_tax = no_capex_year['State Tax Burden'].values
        assert np.all(np.sign(taxable) != np.sign(state_tax))

    def test_sign_of_federal_tax(self):
        no_capex_year = self.actual_tax_calc[self.actual_tax_calc.index != 'CAPEX Year']
        taxable = no_capex_year['Taxable Yearly Net'].values
        federal_tax = no_capex_year['Federal Tax Burden'].values
        assert np.all(np.sign(taxable) != np.sign(federal_tax))
