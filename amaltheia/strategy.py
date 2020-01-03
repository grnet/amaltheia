# Copyright (C) 2019  GRNET S.A.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


import json
import multiprocessing

import amaltheia.log as log
from amaltheia.discover import discover
from amaltheia.services import get_service
from amaltheia.update import update
from amaltheia.results import Results
from amaltheia.config import config
from amaltheia.utils import str_or_dict, bold


class Strategy():
    """Base class for strategy handling"""

    def __init__(self, hosts, services, updates, strategy_args):
        self.hosts = hosts
        self.services = services
        self.updates = updates
        self.strategy_args = strategy_args

        self.results = Results

        log.debug({
            'hosts': self.hosts,
            'updates': self.updates,
            'services': self.services,
            'strategy_args': self.strategy_args
        })

    def execute(self):
        raise NotImplementedError

    @property
    def name(self):
        raise NotImplementedError

    def do_host(self, host_name, host_args):
        """Execute the whole process for a single host"""
        log.info(bold('[{}] Starting, arguments: {}'.format(
            host_name, host_args)))

        # allow host to override services
        services = host_args.get('services', self.services)

        handlers = list(get_service(
            host_name, host_args, service) for service in services)

        # cleanup services
        self.results[host_name].evacuated = True
        for handler in handlers:
            log.info(bold('[{}] Evacuating {} {}'.format(
                host_name, handler.name, handler.__dict__)))
            this_success = handler.evacuate()
            if not this_success:
                self.results[host_name].evacuated = False
                self.results[host_name].failed += 1
                log.fatal('[{}] Failed to disable service {}'.format(
                    host_name, handler))
                break

            self.results[host_name].evacuated &= this_success

        # allow host to override updates
        updates = host_args.get('updates', self.updates)

        # do updates
        if self.results[host_name].evacuated:
            for u in updates:
                log.info(bold('[{}] Running update action: {}'.format(
                    host_name, u)))
                if update(host_name, host_args, u):
                    self.results[host_name].updated += 1
                else:
                    self.results[host_name].failed += 1

                    log.fatal('[{}] Failed update action {}'.format(
                        host_name, u))

        # restore services
        self.results[host_name].restored = True
        for handler in handlers:
            log.info(bold('[{}] Restoring {} {}'.format(
                host_name, handler.name, handler.__dict__)))
            if not handler.restore():
                self.results[host_name].restored = False
                self.results[host_name].failed += 1

                log.fatal('[{}] Failed to restore service {}'.format(
                    host_name, handler))

        log.info(bold('[{}] Done'.format(host_name)))
        return self.results[host_name]

    def output_stats(self):
        print(bold('\n\n*****************************************'))
        ok, err = 0, 0
        for host, stats in self.results.items():
            print(bold('[{}]'.format(host).ljust(50)), stats)
            if stats.failed > 0:
                err += 1
            else:
                ok += 1

        print(bold('\n\n*****************************************'))
        print('[amaltheia] {} hosts OK, {} hosts ERROR'.format(ok, err))


class SerialStrategy(Strategy):
    '''run updates on hosts one-by-one'''

    @property
    def name(self):
        return 'Serial'

    def execute(self):
        for host_name, host_args in self.hosts.items():
            success = True
            try:
                result = self.do_host(host_name, host_args)
                if result.failed > 0:
                    success = False
                    log.fatal(bold('[{}] [amaltheia] Host failed'.format(
                        host_name)))

            # handle all exceptions here, to cover for
            # possibly unhandled exceptions in the code
            # above that would disrupt the process
            except Exception:
                success = False
                self.results[host_name].failed += 1
                log.exception(bold(
                    '[{}] [amaltheia] An unhandled exception occured'.format(
                        host_name)))

            if not success and self.strategy_args.get('quit_on_error'):
                log.fatal(
                    bold('[amaltheia] "quit_on_error" is enabled, quitting'))
                break


class ParallelStrategy(Strategy):
    '''run updates on hosts one-by-one'''

    defaults = {
        'nparallel': 2
    }

    @property
    def name(self):
        return 'Parallel-{}'.format(self.nparallel)

    @property
    def nparallel(self):
        try:
            return int(self.strategy_args.get('nparallel'))
        except (ValueError, TypeError):
            return self.defaults['nparallel']

    def execute_one(self, host_name):
        try:
            result = self.do_host(host_name, self.hosts[host_name])
            if result.failed > 0:
                log.fatal(bold('[{}] [amaltheia] Host failed'.format(
                    host_name)))

        # handle all exceptions here, to cover for
        # possibly unhandled exceptions in the code
        # above that would disrupt the process
        except Exception:
            log.exception(bold(
                '[{}] [amaltheia] An unhandled exception occured'.format(
                    host_name)))

    def execute(self):
        with multiprocessing.Pool(processes=self.nparallel) as p:
            p.map(self.execute_one, self.hosts)


strategies = {
    'serial': SerialStrategy,
    'parallel': ParallelStrategy
}


def run_strategy(job):
    # TODO: this needs to change for strategy configuration
    strategy_name, strategy_args = str_or_dict(job['strategy'])

    hosts = discover(job)
    if config.list_hosts:
        log.info(json.dumps(hosts, indent=2))
        exit(0)

    Strategy = strategies[strategy_name]
    s = Strategy(hosts, job['services'], job['updates'], strategy_args)

    log.info('[amaltheia] Strategy: {} with {} hosts'.format(
        s.name, len(hosts)))

    s.execute()

    s.output_stats()
