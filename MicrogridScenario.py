"""
MicrogridScenario.py

This Python class contains methods and attributes vital for completing the scenario analysis.
"""

__author__ = 'Halley Nathwani, Evan Giarta, Thien Nygen'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani']
__license__ = 'EPRI'
__maintainer__ = ['Halley Nathwani', 'Miles Evans']
__email__ = ['hnathwani@epri.com', 'mevans@epri.com']
__version__ = 'beta'  # beta version

from MicrogridValueStreams.Reliability import Reliability
from MicrogridDER.Battery import Battery
from MicrogridDER.CAES import CAES
from MicrogridDER.PV import PV
from MicrogridDER.ICE import ICE
from MicrogridDER.DieselGenset import DieselGenset
from MicrogridDER.CombustionTurbine import CT
from MicrogridDER.CombinedHeatPower import CHP
from MicrogridDER.LoadControllable import ControllableLoad
from MicrogridDER.ElectricVehicles import ElectricVehicle1, ElectricVehicle2
from MicrogridDER.Chiller import Chiller
from storagevet.ValueStreams.DAEnergyTimeShift import DAEnergyTimeShift
from storagevet.ValueStreams.FrequencyRegulation import FrequencyRegulation
from storagevet.ValueStreams.NonspinningReserve import NonspinningReserve
from storagevet.ValueStreams.DemandChargeReduction import DemandChargeReduction
from storagevet.ValueStreams.EnergyTimeShift import EnergyTimeShift
from storagevet.ValueStreams.SpinningReserve import SpinningReserve
from storagevet.ValueStreams.Backup import Backup
from storagevet.ValueStreams.Deferral import Deferral
from storagevet.ValueStreams.DemandResponse import DemandResponse
from storagevet.ValueStreams.ResourceAdequacy import ResourceAdequacy
from storagevet.ValueStreams.UserConstraints import UserConstraints
from storagevet.ValueStreams.VoltVar import VoltVar
from storagevet.ValueStreams.LoadFollowing import LoadFollowing
from storagevet.Scenario import Scenario
from CBA import CostBenefitAnalysis
from MicrogridPOI import MicrogridPOI
from MicrogridServiceAggregator import MicrogridServiceAggregator
import time
import pandas as pd
from ErrorHandelling import *


class MicrogridScenario(Scenario):
    """ A scenario is one simulation run in the model_parameters file.

    """

    def __init__(self, input_tree):
        """ Initialize a scenario with sizing technology and paramsDER

        Args:
            input_tree (Dict): Dict of input attributes such as time_series, params, and monthly_data

        """
        Scenario.__init__(self, input_tree)

        self.technology_inputs_map.update({
            'ElectricVehicle1': input_tree.ElectricVehicle1,
            'ElectricVehicle2': input_tree.ElectricVehicle2,
            'DieselGenset': input_tree.DieselGenset,
            'CT': input_tree.CT,
            'CHP': input_tree.CHP,
            'Chiller': input_tree.Chiller,
        })
        self.value_stream_input_map.update({'Reliability': input_tree.Reliability})
        self.deferral_sizing = False
        TellUser.debug("ScenarioSizing initialized ...")

    def set_up_poi_and_service_aggregator(self):
        """ Initialize the POI and service aggregator with DERs and valuestreams to be evaluated.

        """
        technology_class_map = {
            'CAES': CAES,
            'Battery': Battery,
            'PV': PV,
            'ICE': ICE,
            'DieselGenset': DieselGenset,
            'CT': CT,
            'CHP': CHP,
            'Load': ControllableLoad,
            'ElectricVehicle1': ElectricVehicle1,
            'ElectricVehicle2': ElectricVehicle2,
            'Chiller': Chiller,
        }

        value_stream_class_map = {
            'Deferral': Deferral,
            'DR': DemandResponse,
            'RA': ResourceAdequacy,
            'Backup': Backup,
            'Volt': VoltVar,
            'User': UserConstraints,
            'DA': DAEnergyTimeShift,
            'FR': FrequencyRegulation,
            'LF': LoadFollowing,
            'SR': SpinningReserve,
            'NSR': NonspinningReserve,
            'DCM': DemandChargeReduction,
            'retailTimeShift': EnergyTimeShift,
            'Reliability': Reliability
        }
        # these need to be initialized after opt_agg is created
        self.poi = MicrogridPOI(self.poi_inputs, self.technology_inputs_map, technology_class_map)
        self.service_agg = MicrogridServiceAggregator(self.value_stream_input_map, value_stream_class_map)

        if self.poi.is_sizing_optimization:
            # if Deferral is active -- require that only DER active is ESS and there is only 1 DER total
            if 'Deferral' in self.service_agg.value_streams.keys():
                if len(self.poi.der_list) != 1 or self.poi.der_list[0].technology_type != "Energy Storage System":
                    TellUser.error('Sizing for deferring an asset upgrade is only implemented for a one ESS case.')
                    raise ParameterError("No optimization was built or solved. Please check log files for more information. ")
                # deferral sizing will set the size of the ESS, so no need to check other sizing conditions.
                self.deferral_sizing = True
            else:
                self.check_sizing_conditions()

    def check_sizing_conditions(self):
        """ Throws an error if any DER is being sized under assumptions that will not
        result in a solution within a reasonable amount of time.
        Called IFF we are preforming an optimization based sizing analysis.

        """
        error = False
        # make sure the optimization horizon is the whole year
        if self.n != 'year' and 'Reliability' not in self.service_agg.value_streams.keys():
            TellUser.error('Trying to size without setting the optimization window to \'year\'')
            error = True
        # any wholesale markets active?
        if self.service_agg.is_whole_sale_market():
            TellUser.warning('trying to size the power of the battery to maximize profits in wholesale markets.' +
                             ' We will not run analysis power capacity is not limited by the DERs or through market participation constraints.')
            # check that either (1) or (2) is true
            # 1) if all wholesale markets has a max defined
            not_all_markets_have_max = self.service_agg.any_max_participation_constraints_not_included()
            # 2) for each technology, if power is being sized and max is defined
            not_all_power_max_defined = self.poi.is_any_sizable_der_missing_power_max()
            # add validation step here to check on compatibility of the tech size constraints and timeseries service constraints
            participation_constraints_are_infeasible = self.check_for_infeasible_regulation_constraints_with_system_size()
            error = error or not_all_markets_have_max or not_all_power_max_defined or participation_constraints_are_infeasible
        # check if only have Reliability and post_facto_only==1
        if self.service_agg.post_facto_reliability_only():
            TellUser.error('trying to size and preform post facto calculations only')
            error = True
        # check if binary will create a DCP error based on formulation
        if self.poi.is_dcp_error(self.incl_binary):
            TellUser.error('trying to size power and use binary formulation results in nonlinear models')
            error = True

        if error:
            raise ParameterError("Further calculations requires that economic dispatch is solved, but "
                                 + "no optimization was built or solved. Please check log files for more information. ")

    def fill_and_drop_extra_data(self):
        """ Go through value streams and technologies and keep data for analysis years, and add more
        data if necessary.  ALSO creates/assigns optimization levels.

        Returns: None

        """
        super(MicrogridScenario, self).fill_and_drop_extra_data()
        if self.deferral_sizing:
            # set size of ESS
            self.poi.der_list = self.service_agg.set_size(self.poi.der_list, self.start_year)

    def initialize_cba(self):
        self.cost_benefit_analysis = CostBenefitAnalysis(self.finance_inputs)
        # add fuel_cost to active DERs that can consume fuel
        for der in self.poi.der_list:
            der.set_fuel_cost(self.cost_benefit_analysis.get_fuel_cost)

        # set the project end year
        self.end_year = self.cost_benefit_analysis.find_end_year(self.start_year, self.end_year, self.poi.der_list)
        if self.end_year.year == 0:
            # some type error was recorded. throw error and exit
            raise Exception("Error occurred while trying to determine the end of the analysis." +
                            " Please check the error_log.log in your results folder for more information.")

        # update opt_years based on this new end_year
        add_analysis_years = self.cost_benefit_analysis.get_years_after_failures(self.end_year, self.poi.der_list)
        TellUser.debug(add_analysis_years)
        set_opt_yrs = set(self.opt_years)
        set_opt_yrs.update(add_analysis_years)
        self.opt_years = list(set_opt_yrs)

    def reliability_based_sizing_module(self):
        """ runs the reliability based sizing module if the correct combination of inputs allows/
        indicates to run it.

        """
        if 'Reliability' not in self.service_agg.value_streams.keys():
            return
        else:
            if self.service_agg.value_streams['Reliability'].post_facto_only:
                return

        # require only 1 ESS is present. we have to work on extending this module to multiple ESSs
        num_ess = sum([1 if der_inst.technology_type == 'Energy Storage System' else 0 for der_inst in self.poi.der_list])
        if num_ess > 1:
            TellUser.error("Multiple ESS sizing with this reliability module is not implemented yet.")
            raise ArithmeticError('See dervet.log for more information.')

        der_list = self.service_agg.value_streams['Reliability'].sizing_module(self.poi.der_list, self.optimization_levels.index)
        self.poi.der_list = der_list

    def optimize_problem_loop(self, **kwargs):
        """ This function selects on opt_agg of data in time_series and calls optimization_problem on it.

        Args:
            **kwargs: allows child classes to pass in additional arguments to set_up_optimization

        """
        alpha = 1
        if self.poi.is_sizing_optimization:
            # calculate the annuity scalar that will convert any yearly costs into a present value
            alpha = self.cost_benefit_analysis.annuity_scalar(self.start_year, self.end_year, self.opt_years)

        if self.service_agg.is_deferral_only() or self.service_agg.post_facto_reliability_only():
            TellUser.warning("Only active Value Stream is Deferral or post facto only, so not optimizations will run...")
            return True

        TellUser.info("Starting optimization loop")
        for opt_period in self.optimization_levels.predictive.unique():

            # used to select rows from time_series relevant to this optimization window
            mask = self.optimization_levels.predictive == opt_period
            sub_index = self.optimization_levels.loc[mask].index

            # drop any ders that are not operational
            self.poi.grab_active_ders(sub_index)
            if not len(self.poi.active_ders):
                continue

            # apply past degradation in ESS objects (NOTE: if no degradation module applies to specific ESS tech, then nothing happens)

            TellUser.info(f"{time.strftime('%H:%M:%S')} Running Optimization Problem starting at {sub_index[0]} hb")

            # setup + run optimization then return optimal objective costs
            functions, constraints = self.set_up_optimization(mask, self.system_requirements,
                                                              annuity_scalar=alpha,
                                                              ignore_der_costs=self.service_agg.post_facto_reliability_only())
            objective_values = self.run_optimization(functions, constraints, opt_period)

            for vs in self.service_agg.value_streams.values():
                # record the solution of the variables used in the optimization run
                vs.save_variable_results(sub_index)

            for der in self.poi.active_ders:
                # record the solution of the variables used in the optimization run
                der.save_variable_results(sub_index)
                # save sizes of DERs that were found in the first optimization run (the method will have no effect after the first time it is called)
                der.set_size()
                if der.tag == "Battery":
                    # calculate degradation in ESS objects (NOTE: if no degradation module applies to specific ESS tech, then nothing happens)
                    der.calc_degradation(opt_period, sub_index[0], sub_index[-1])

            # then add objective expressions to financial obj_val
            self.objective_values = pd.concat([self.objective_values, objective_values])
        return True

    def check_for_infeasible_regulation_constraints_with_system_size(self):
        """ perform error checks on DERs that are being sized with ts_user_constraints
        collect errors and raise if any were found"""
        # down
        has_errors = False
        max_p_sch_down = sum([der_inst.max_p_schedule_down() for der_inst in self.poi.der_list])
        min_p_res_down = sum([service.min_regulation_down() for service in self.service_agg.value_streams.values()])
        diff = max_p_sch_down - min_p_res_down
        negative_vals = (diff.values < 0)
        if negative_vals.any():
            first_time = diff.index[negative_vals][0]
            TellUser.error('The sum of minimum power regulation down exceeds the maximum possible power capacities that ' +
                           f'can provide regulation down, first occurring at time {first_time}.')
            has_errors = True
        # up
        if {'FR', 'LF'} & self.service_agg.value_streams.keys():
            max_p_sch_up = sum([der_inst.max_p_schedule_up() for der_inst in self.poi.der_list])
            min_p_res_up = sum([service.min_regulation_up() for service in self.service_agg.value_streams.values()])
            diff = max_p_sch_up - min_p_res_up
            negative_vals = (diff.values < 0)
            if negative_vals.any():
                first_time = diff.index[negative_vals][0]
                TellUser.error('The sum of minimum power regulation up exceeds the maximum possible power capacities that ' +
                               f'can provide regulation down, first occurring at time {first_time}.')
                has_errors = True
        return has_errors
