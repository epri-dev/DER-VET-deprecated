"""
Scenario.py

This Python class contains methods and attributes vital for completing the scenario analysis.
"""

__author__ = 'Miles Evans and Evan Giarta'
__copyright__ = 'Copyright 2018. Electric Power Research Institute (EPRI). All Rights Reserved.'
__credits__ = ['Miles Evans', 'Andres Cortes', 'Evan Giarta', 'Halley Nathwani', 'Micah Botkin-Levy', 'Yekta Yazar']
__license__ = 'EPRI'
__maintainer__ = ['Evan Giarta', 'Miles Evans']
__email__ = ['egiarta@epri.com', 'mevans@epri.com']


import storagevet

from TechnologiesDER.BatterySizing import BatterySizing
from TechnologiesDER.CurtailPVSizing import CurtailPVSizing
from TechnologiesDER.DieselSizing import DieselSizing
from ValueStreamsDER.Reliability import Reliability

from storagevet.Scenario import Scenario

from cbaDER import CostBenDER

import logging

dLogger = logging.getLogger('Developer')
uLogger = logging.getLogger('User')
e_logger = logging.getLogger('Error')


class ScenarioSizing(Scenario):
    """ A scenario is one simulation run in the model_parameters file.

    """

    def __init__(self, input_tree):
        """ Initialize a scenario.

        Args:
            input_tree (Dict): Dict of input attributes such as time_series, params, and monthly_data

        """
        Scenario.__init__(self, input_tree)

        self.predispatch_service_inputs_map.update({'Reliability': input_tree.Reliability})

        self.sizing_optimization = False

        dLogger.info("ScenarioDER initialized ...")

    def init_financials(self, finance_inputs):
        """ Initializes the financial class with a copy of all the price data from timeseries, the tariff data, and any
         system variables required for post optimization analysis.

         Args:
             finance_inputs (Dict): Financial inputs

        """

        self.financials = CostBenDER(finance_inputs)
        dLogger.info("Finished adding Financials...")

    def add_technology(self):
        """ Reads params and adds technology. Each technology gets initialized and their physical constraints are found.

        """
        ess_action_map = {
            'Battery': BatterySizing,
        }

        active_storage = self.active_objects['storage']
        for storage in active_storage:
            inputs = self.technology_inputs_map[storage]
            tech_func = ess_action_map[storage]
            self.technologies['Storage'] = tech_func('Storage', self.power_kw['opt_agg'], inputs, self.cycle_life)
            dLogger.info("Finished adding storage...")

        generator_action_map = {
            'PV': CurtailPVSizing,
            'Diesel': DieselSizing
        }

        active_gen = self.active_objects['generator']
        for gen in active_gen:
            inputs = self.technology_inputs_map[gen]
            tech_func = generator_action_map[gen]
            new_gen = tech_func(gen, inputs)
            new_gen.estimate_year_data(self.opt_years, self.frequency)
            self.technologies[gen] = new_gen
            dLogger.info("Finished adding generators...")

        dLogger.info("Finished adding active Technologies...")

    def add_services(self):
        """ Reads through params to determine which services are turned on or off. Then creates the corresponding
        service object and adds it to the list of services. Also generates a list of growth functions that apply to each
        service's timeseries data (to be used when adding growth data).

        Notes:
            This method needs to be applied after the technology has been initialized.
            ALL SERVICES ARE CONNECTED TO THE TECH

        TODO [multi-tech] need dynamic mapping of services to tech in RIVET
        """
        storage_inputs = self.technologies['Storage']

        predispatch_service_action_map = {
            'Backup': storagevet.Backup,
            'User': storagevet.UserConstraints,
            'Reliability': Reliability
        }
        for service in self.active_objects['pre-dispatch']:
            dLogger.info("Using: " + str(service))
            inputs = self.predispatch_service_inputs_map[service]
            service_func = predispatch_service_action_map[service]
            new_service = service_func(inputs, storage_inputs, self.power_kw, self.dt)
            new_service.estimate_year_data(self.opt_years, self.frequency)
            self.predispatch_services[service] = new_service

        dLogger.info("Finished adding Predispatch Services for Value Stream")

        service_action_map = {
            'DA': storagevet.DAEnergyTimeShift,
            'FR': storagevet.FrequencyRegulation,
            'SR': storagevet.SpinningReserve,
            'NSR': storagevet.NonspinningReserve,
            'DCM': storagevet.DemandChargeReduction,
            'retailTimeShift': storagevet.EnergyTimeShift,
        }

        for service in self.active_objects['service']:
            dLogger.info("Using: " + str(service))
            inputs = self.service_input_map[service]
            service_func = service_action_map[service]
            new_service = service_func(inputs, storage_inputs, self.dt)
            new_service.estimate_year_data(self.opt_years, self.frequency)
            self.services[service] = new_service

        dLogger.info("Finished adding Services for Value Stream")

    def optimize_problem_loop(self, annuity_scalar=1):
        """This function selects on opt_agg of data in self.time_series and calls optimization_problem on it. We determine if the
        optimization will be sizing and calculate a lifetime project NPV multiplier to pass into the optimization problem

        Args:
            annuity_scalar (float): a scalar value to be multiplied by any yearly cost or benefit that helps capture the cost/benefit over
                the entire project lifetime (only to be set iff sizing)

        """
        if self.sizing_optimization:
            annuity_scalar = self.financials.annuity_scalar(self.start_year, self.end_year, self.opt_years)

        Scenario.optimize_problem_loop(self, annuity_scalar)