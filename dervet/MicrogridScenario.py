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

from dervet.MicrogridValueStreams.Reliability import Reliability
from dervet.MicrogridDER.Battery import Battery
from dervet.MicrogridDER.CAES import CAES
from dervet.MicrogridDER.PV import PV
from dervet.MicrogridDER.ICE import ICE
from dervet.MicrogridDER.DieselGenset import DieselGenset
from dervet.MicrogridDER.CombustionTurbine import CT
from dervet.MicrogridDER.CombinedHeatPower import CHP
from dervet.MicrogridDER.LoadControllable import ControllableLoad
from dervet.MicrogridDER.ElectricVehicles import ElectricVehicle1, ElectricVehicle2
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
from dervet.CBA import CostBenefitAnalysis
from dervet.MicrogridPOI import MicrogridPOI
from dervet.MicrogridServiceAggregator import MicrogridServiceAggregator
from storagevet.ErrorHandling import *
import numpy as np


class MicrogridScenario(Scenario):
    """ A scenario is one simulation run in the model_parameters file.

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
        })
        self.value_stream_input_map.update({'Reliability': input_tree.Reliability})
        self.deferral_sizing = False  # indicates that dervet should go to the deferral sizing module
        self.reliability_sizing = False  # indicates that dervet should go to the reliability sizing module
        self.Battery_sizing_with_Degradation=False #indicates that dervet sizes ES considering battery degradation
        TellUser.debug("ScenarioSizing initialized ...")

    def set_up_poi_and_service_aggregator(self, point_of_interconnection_class=MicrogridPOI, service_aggregator_class=MicrogridServiceAggregator):
        """ Initialize the POI and service aggregator with DERs and valuestreams to be evaluated.

        """
        super().set_up_poi_and_service_aggregator(point_of_interconnection_class, service_aggregator_class)
        if self.poi.is_sizing_optimization:
            if 'Deferral' in self.service_agg.value_streams.keys():
                # deferral sizing will set the size of the ESS, so no need to check other sizing conditions.
                self.deferral_sizing = True
                # require that only 1 ESS is included
                if len(self.poi.der_list) != 1 or self.poi.der_list[0].technology_type != "Energy Storage System":
                    TellUser.error('Sizing for deferring an asset upgrade is only implemented for a one ESS case.')
                    raise ParameterError("No optimization was built or solved. Please check log files for more information. ")

            if 'Reliability' in self.service_agg.value_streams.keys() and not self.service_agg.value_streams['Reliability'].post_facto_only:
                self.reliability_sizing = True
                # require only 1 ESS is present. we have to work on extending this module to multiple ESSs
                num_ess = sum([1 if der_inst.technology_type == 'Energy Storage System' else 0 for der_inst in self.poi.der_list])
                if num_ess > 1:
                    TellUser.error("Multiple ESS sizing with this reliability module is not implemented yet.")
                    raise ParameterError('See dervet.log for more information.')
                if self.service_agg.value_streams['Reliability'].outage_duration==1 and self.dt==1:
                    TellUser.error("Reliability target must be more than 1 hour in this implementation")
                    raise ParameterError('See dervet.log for more information.')

            if self.poi.der_list[0].technology_type == "Energy Storage System" and self.poi.der_list[0].incl_cycle_degrade:
                self.Battery_sizing_with_Degradation = True

                TellUser.warning(f"Batter sizing with Degradation option. Degradation is calculated as a post-facto in this case")
            else:
                self.check_opt_sizing_conditions()

    def check_opt_sizing_conditions(self):
        """ Throws an error if any DER is being sized under assumptions that will not
        result in a solution within a reasonable amount of time.
        Called IFF we are preforming an optimization based sizing analysis.

        """
        error = False
        # make sure the optimization horizon is the whole year
        if self.n != 'year':
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
            TellUser.error('trying to size for reliability, but only preform post facto calculations. Please turn off post_facto_only or stop sizing')
            error = True
        # check if binary will create a DCP error based on formulation
        if self.poi.is_dcp_error(self.incl_binary):
            TellUser.error('trying to size power and use binary formulation results in nonlinear models')
            error = True
        if error:
            raise ParameterError("Further calculations requires that economic dispatch is solved, but "
                                 + "no optimization was built or solved. Please check log files for more information. ")

    def check_for_infeasible_regulation_constraints_with_system_size(self):
        """ perform error checks on DERs that are being sized with
        ts_user_constraints collect errors and raise if any were found"""
        # down
        has_errors = False
        max_p_sch_down = sum([der_inst.max_p_schedule_down() for der_inst
                              in self.poi.der_list])
        min_p_res_down = sum([service.min_regulation_down() for service in
                              self.service_agg.value_streams.values()])
        diff = max_p_sch_down - min_p_res_down
        negative_vals = np.less(diff, 0)
        if np.any(negative_vals):
            first_time = diff.index[negative_vals][0]
            TellUser.error('The sum of minimum power regulation down exceeds the maximum possible power capacities that ' +
                           f'can provide regulation down, first occurring at time {first_time}.')
            has_errors = True
        # up
        if {'FR', 'LF'} & self.service_agg.value_streams.keys():
            max_p_sch_up = sum([der_inst.max_p_schedule_up() for der_inst in self.poi.der_list])
            min_p_res_up = sum([service.min_regulation_up() for service in self.service_agg.value_streams.values()])
            diff = max_p_sch_up - min_p_res_up
            negative_vals = np.less(diff, 0)
            if np.any(negative_vals):
                first_time = diff.index[negative_vals][0]
                TellUser.error('The sum of minimum power regulation up exceeds the maximum possible power capacities that ' +
                               f'can provide regulation down, first occurring at time {first_time}.')
                has_errors = True
        return has_errors

    def initialize_cba(self):
        """ Initializes DER-VET's cost benefit analysis module with user given inputs
        Determines the end year for analysis
        Adds years to the set of years economic dispatch will be optimized and solved for

        """
        self.cost_benefit_analysis = CostBenefitAnalysis(self.finance_inputs, self.start_year, self.end_year)
        # set the project end year
        self.end_year = self.cost_benefit_analysis.find_end_year(self.poi.der_list)
        if self.end_year.year == 0:
            # some type error was recorded. throw error and exit
            raise Exception("Error occurred while trying to determine the end of the analysis." +
                            " Please check the error_log.log in your results folder for more information.")
        # if economic carrying cost, check for value conflicts in CBA and scenario
        if self.cost_benefit_analysis.ecc_mode:
            self.cost_benefit_analysis.ecc_checks(self.poi.der_list, self.service_agg.value_streams)
        # update opt_years based on this new end_year
        add_analysis_years = self.cost_benefit_analysis.get_years_after_failures(self.end_year, self.poi.der_list)
        TellUser.debug(add_analysis_years)
        set_opt_yrs = set(self.opt_years)
        set_opt_yrs.update(add_analysis_years)
        self.opt_years = list(set_opt_yrs)

    def sizing_module(self):
        """ runs the reliability based sizing module if the correct combination of inputs allows/
        indicates to run it.
        TODO put opt sizing checks here
        """
        if self.reliability_sizing:
            der_list = self.service_agg.value_streams['Reliability'].sizing_module(self.poi.der_list, self.optimization_levels.index)
            self.poi.der_list = der_list
            # Resetting sizing flag. It doesn't size for other services.
            self.poi.is_sizing_optimization = False

        if self.service_agg.is_reliability_only() or self.service_agg.post_facto_reliability_only_and_user_defined():
            self.opt_engine = False

        if self.deferral_sizing:
            # set size of ESS
            self.poi.der_list = self.service_agg.set_size(self.poi.der_list, self.start_year)

    def optimize_problem_loop(self, **kwargs):
        """ This function selects on opt_agg of data in time_series and calls optimization_problem on it.

        Args:
            **kwargs: allows child classes to pass in additional arguments to set_up_optimization

        """
        alpha = 1
        if self.poi.is_sizing_optimization:
            # calculate the annuity scalar that will convert any yearly costs into a present value
            alpha = self.cost_benefit_analysis.annuity_scalar(self.opt_years)
        # TODO
        if self.service_agg.post_facto_reliability_only():
            TellUser.info("Only active Value Stream is post facto only, so not optimizations will run...")
            self.service_agg.value_streams['Reliability'].use_soc_init = True
            TellUser.info("SOC_init will be used for Post-Facto Calculation")
        elif self.service_agg.post_facto_reliability_only_and_user_defined():
            TellUser.info("Only active Value Stream is post facto only, so not optimizations will run." +
                             " Energy min profile from User_constraint will be used")
            self.service_agg.value_streams['Reliability'].use_user_const = True

        if not self.opt_engine:
            return

        TellUser.info("Starting optimization loop")
        if self.Battery_sizing_with_Degradation:
            self.poi.der_list[0].incl_cycle_degrade = 1
        for opt_period in self.optimization_levels.predictive.unique():

            # setup + run optimization then return optimal objective costs
            functions, constraints, sub_index = self.set_up_optimization(opt_period,
                                                                         annuity_scalar=alpha,
                                                                         ignore_der_costs=self.service_agg.post_facto_reliability_only())
            if not len(constraints) and not len(functions.values()):
                TellUser.info(f"Optimization window #{opt_period} does not have any constraints or objectives to minimize -- SKIPPING...")
                continue
            cvx_problem, obj_expressions, cvx_error_msg = self.solve_optimization(functions, constraints)
            #Setting the flag back to calculate degradation
            if self.Battery_sizing_with_Degradation:
                self.poi.der_list[0].incl_cycle_degrade = 0
            self.save_optimization_results(opt_period, sub_index, cvx_problem, obj_expressions, cvx_error_msg)

    def set_up_optimization(self, opt_window_num, annuity_scalar=1, ignore_der_costs=False):
        """ Sets up and runs optimization on a subset of time in a year. Called within a loop.

        Args:
            opt_window_num (int): the optimization window number that is being solved
            annuity_scalar (float): a scalar value to be multiplied by any yearly cost or benefit that helps capture the cost/benefit over
                        the entire project lifetime (only to be set iff sizing OR optimizing carrying costs)
            ignore_der_costs (bool): flag to indicate if we do not want to consider to economics of operating the DERs in our optimization
                (this flag will never be TRUE if the user indicated the desire to size the DER mix)

        Returns:
            functions (dict): functions or objectives of the optimization
            constraints (list): constraints that define behaviors, constrain variables, etc. that the optimization must meet
            sub_index:

        """
        # used to select rows from time_series relevant to this optimization window
        mask = self.optimization_levels.predictive == opt_window_num
        sub_index = self.optimization_levels.loc[mask].index
        # drop any ders that are not operational
        self.poi.grab_active_ders(sub_index)
        if not len(self.poi.active_ders):
            return {}, [], sub_index
        return super(MicrogridScenario, self).set_up_optimization(opt_window_num, annuity_scalar, ignore_der_costs)

    def save_optimization_results(self, opt_window_num, sub_index, prob, obj_expression, cvx_error_msg):
        """ Checks if there was a solution to the optimization. If not, report the problem
         to the user. If there was a solution, then saves results within each instance.

        Args:
            opt_window_num:
            sub_index:
            prob:
            obj_expression:
            cvx_error_msg: any error message that might have occurred during problem solve

        """
        super(MicrogridScenario, self).save_optimization_results(opt_window_num, sub_index, prob, obj_expression, cvx_error_msg)
        for der in self.poi.active_ders:
            # save sizes of DERs that were found in the first optimization run (the method will have no effect after the first time it is called)
            der.set_size()
