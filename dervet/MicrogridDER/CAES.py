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
CAES.py

This Python class contains methods and attributes specific for technology analysis within StorageVet.
"""

from storagevet.Technology import CAESTech
from dervet.MicrogridDER.ESSSizing import ESSSizing
from storagevet.ErrorHandling import *
from dervet.DERVETParams import ParamsDER


class CAES(CAESTech.CAES, ESSSizing):
    """ CAES class that inherits from StorageVET. this object does not size.

    """

    def __init__(self, params):
        """ Initialize all technology with the following attributes.

        Args:
            params (dict): Dict of parameters for initialization
        """
        TellUser.debug(f"Initializing {__name__}")
        super().__init__(params)  # CAESTech.CAES->ESSizing->EnergyStorage->DER->Sizing

        # warn the user that the power/energy is 0
        if not self.dis_max_rated:
            TellUser.error(f"{self.unique_tech_id()} has a discharge value of 0. Did you mean to do this?")
            raise ModelParameterError(f" Please check the size of {self.unique_tech_id()}")
        if not self.ch_max_rated:
            TellUser.error(f"{self.unique_tech_id()} has a charge value of 0. Did you mean to do this?")
            raise ModelParameterError(f" Please check the size of {self.unique_tech_id()}")
        if not self.ene_max_rated:
            TellUser.error(f"{self.unique_tech_id()} has a energy value of 0. Did you mean to do this?")
            raise ModelParameterError(f" Please check the size of {self.unique_tech_id()}")

    def objective_function(self, mask, annuity_scalar=1):
        """ Generates the objective function related to a technology. Default includes O&M which can be 0

        Args:
            mask (Series): Series of booleans used, the same length as case.power_kw
            annuity_scalar (float): a scalar value to be multiplied by any yearly cost or benefit that helps capture the cost/benefit over
                    the entire project lifetime (only to be set iff sizing, else alpha should not affect the aobject function)

        Returns:
            self.costs (Dict): Dict of objective costs
        """
        costs = super().objective_function(mask, annuity_scalar)
        if self.being_sized():
            costs.update({self.name + 'capex': self.get_capex()})
