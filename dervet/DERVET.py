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
runDERVET.py

This Python script serves as the initial launch point executing the
Python-based version of DERVET.
"""
import time

from dervet.MicrogridScenario import MicrogridScenario
from dervet.DERVETParams import ParamsDER
from dervet.MicrogridResult import MicrogridResult
from storagevet.ErrorHandling import *


class DERVET:
    """ DERVET API. Allows DER-VET to be imported and used like any other python library.

    """

    def __init__(self, model_parameters_path, verbose=False, **kwargs):
        """
            Constructor to initialize the parameters and data needed to run

            Args:
                model_parameters_path (str): Filename of the model parameters
                    CSV or XML that describes the optimization case to be
                    analysed

            Notes: kwargs is in place for testing purposes
        """
        self.verbose = verbose

        # Initialize Params Object from Model Parameters and Simulation Cases
        self.cases = ParamsDER.initialize(model_parameters_path, self.verbose, **kwargs)
        self.results = MicrogridResult.initialize(ParamsDER.results_inputs,
                                                  ParamsDER.case_definitions)

        if self.verbose:
            from storagevet.Visualization import Visualization
            Visualization(ParamsDER).class_summary()

    def solve(self):
        starts = time.time()

        for key, value in self.cases.items():
            run = MicrogridScenario(value)
            run.set_up_poi_and_service_aggregator()
            run.initialize_cba()
            run.fill_and_drop_extra_data()
            run.sizing_module()
            run.emissions_module()  # run emissions analysis (set up as pareto analysis)
            run.optimize_problem_loop()

            MicrogridResult.add_instance(key, run)

        MicrogridResult.sensitivity_summary()

        ends = time.time()
        TellUser.info(f"DERVET runtime: {ends - starts}")

        return MicrogridResult
