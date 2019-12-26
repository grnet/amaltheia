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
import logging
import multiprocessing

from amaltheia.discover import discover
from amaltheia.services import get_service
from amaltheia.update import update
from amaltheia.config import config
from amaltheia.utils import str_or_dict, c


class Strategy():
    """Base class for strategy handling"""

    def __init__(self, hosts, services, updates, strategy_args):
        self.hosts = hosts
        self.services = services
        self.updates = updates
        self.strategy_args = strategy_args

        logging.debug({
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
        logging.info(c('[{}] Starting, arguments: {}'.format(
            host_name, host_args)))

        # allow host to override services
        services = host_args.get('services', self.services)

        handlers = list(get_service(
            host_name, host_args, service) for service in services)

        # cleanup services
        success = True
        for handler in handlers:
            logging.info(c('[{}] Evacuating {} {}'.format(
                host_name, handler.name, handler.__dict__)))
            success &= handler.evacuate()
            if not success:
                logging.fatal('[{}] Failed to disable service {}'.format(
                    host_name, handler))
                break

        # allow host to override updates
        updates = host_args.get('updates', self.updates)

        # do updates
        if success:
            for u in updates:
                logging.info(c('[{}] Running update action: {}'.format(
                    host_name, u)))
                # TODO: check success here
                update(host_name, host_args, u)

        # restore services
        for handler in handlers:
            logging.info(c('[{}] Restoring {} {}'.format(
                host_name, handler.name, handler.__dict__)))
            handler.restore()

        logging.info(c('[{}] Done'.format(host_name)))
        return success


class SerialStrategy(Strategy):
    '''run updates on hosts one-by-one'''

    @property
    def name(self):
        return 'Serial'

    def execute(self):
        for host_name, host_args in self.hosts.items():
            try:
                success = self.do_host(host_name, host_args)
                if not success:
                    logging.fatal(c('[{}] [amaltheia] Host failed'.format(
                        host_name)))

            # handle all exceptions here, to cover for
            # possibly unhandled exceptions in the code
            # above that would disrupt the process
            except Exception:
                success = False
                logging.exception(c(
                    '[{}] [amaltheia] An unhandled exception occured'.format(
                        host_name)))

            if not success and self.strategy_args.get('quit_on_error'):
                logging.fatal(
                    c('[amaltheia] "quit_on_error" is enabled, quitting'))
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
            host_args = self.hosts[host_name]
            success = self.do_host(host_name, host_args)
            if not success:
                logging.fatal(c('[{}] [amaltheia] Host failed'.format(
                    host_name)))

        # handle all exceptions here, to cover for
        # possibly unhandled exceptions in the code
        # above that would disrupt the process
        except Exception:
            success = False
            logging.exception(c(
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
        logging.info(json.dumps(hosts, indent=2))
        exit(0)

    Strategy = strategies[strategy_name]
    s = Strategy(hosts, job['services'], job['updates'], strategy_args)

    logging.info('[amaltheia] Strategy: {} with {} hosts'.format(
        s.name, len(hosts)))

    s.execute()
