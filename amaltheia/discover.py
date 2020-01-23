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
import re

import amaltheia.log as log
from amaltheia.utils import GET, jinja, str_or_dict


class Discoverer(object):
    """Base class for discoverers. automatically retrieve hosts from
    a service"""

    def __init__(self, discover_args):
        self.args = discover_args

    def discover(self):
        """discoveres should implement this function to return a host
        inventory with the following format:
        {
            "hostname_1": {**host1_args},
            "hostname_2": {**host2_args}
        }"""
        raise NotImplementedError


class StaticDiscoverer(Discoverer):
    """Parses static list of hosts"""
    def __init__(self, discover_args):
        if not isinstance(discover_args, list):
            raise ValueError('static discoverer expects list of hosts')

        self.args = discover_args

    def discover(self):
        result = {}
        for host in self.args:
            host_name, host_args = str_or_dict(jinja(host))
            result[host_name] = host_args

        return result


class NetBoxDiscoverer(Discoverer):
    """Discover hosts using the NetBox Rest API"""
    def __init__(self, discover_args):
        super(NetBoxDiscoverer, self).__init__(discover_args)
        if 'netbox-url' not in self.args:
            raise ValueError('missing "netbox-url" for netbox discoverer')

        if 'host-name' not in self.args:
            raise ValueError('missing "host-name" for netbox discoverer')

        self.host_name = self.args['host-name']
        self.netbox_url = jinja(self.args['netbox-url'])
        self.filter_name = jinja(self.args.get('filter-name', '.*'))

    def discover(self):
        api_result = json.loads(GET(self.netbox_url))

        hosts = {}
        for host in api_result.get('results', []):

            if not re.match(self.filter_name, host['name']):
                continue

            host_name = jinja(self.host_name, host=host)
            host_args = jinja(self.args.get('host-args') or {}, host=host)

            hosts[host_name] = host_args

        return hosts


class PatchmanDiscoverer(Discoverer):
    """Discover hosts from Patchman Rest API"""
    def __init__(self, discover_args):
        super(PatchmanDiscoverer, self).__init__(discover_args)
        if 'patchman-url' not in self.args:
            raise ValueError('missing "patchman-url" for Patchman discoverer')

        if 'host-name' not in self.args:
            raise ValueError('missing "host-name" for Patchman discoverer')

        self.patchman_url = self.args['patchman-url']
        self.host_name = self.args['host-name']
        self.filter_name = jinja(self.args.get('filter-name', '.*'))
        self.skip_ok = self.args['skip-ok']

    def discover(self):
        results = []
        response = {'next': self.patchman_url}
        while response['next']:
            response = json.loads(GET(response['next']))
            results.extend(response['results'])

        hosts = {}
        for host in results:
            if not re.match(self.filter_name, host['hostname']):
                continue

            host_name = jinja(self.host_name, host=host)
            host_args = jinja(self.args.get('host-args') or {}, host=host)

            if host['updates'] and self.args.get('on-package-updates'):
                host_args.setdefault('updates', [])
                host_args['updates'].extend(
                    self.args.get('on-package-updates'))

            if host['reboot_required'] and self.args.get('on-reboot-required'):
                host_args.setdefault('updates', [])
                host_args['updates'].extend(
                    self.args.get('on-reboot-required'))

            # skip hosts with no actionable items
            if not host_args and self.skip_ok:
                continue

            hosts[host_name] = host_args

        return hosts


discoverers = {
    'static': StaticDiscoverer,
    'netbox': NetBoxDiscoverer,
    'patchman': PatchmanDiscoverer
}


def discover(job):
    """Parses job configuration and returns list of found hosts"""
    hosts = {}

    for disc in job.get('hosts', []):
        disc_name, disc_args = str_or_dict(disc)

        Discoverer = discoverers.get(disc_name)
        if Discoverer is None:
            log.fatal('[amaltheia] Unknown host discoverer {}'.format(
                disc_name))
            continue

        hosts.update(Discoverer(disc_args).discover())

    return hosts


__all__ = [
    discover
]
