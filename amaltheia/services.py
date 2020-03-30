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
from time import sleep
from shlex import quote

import amaltheia.log as log
from amaltheia.utils import (
    openstack_cmd, openstack_cmd_table, str_or_dict, jinja,
    thruk_get_host, thruk_set_notifications)


class Service():
    """Base class for handling evacution/restoring of services"""

    @property
    def name(self):
        return '<unnamed>'

    def __init__(self, host, host_args, service_args):
        self.host_args = host_args
        self.service_args = service_args

        self.host = self.fix_hostname(host)

    def evacuate(self):
        """Handles evacuating a host that is running the service. Typical
        actions include stopping and disabling services, migrating running
        VMs to other hosts, etc"""
        raise NotImplementedError

    def restore(self):
        """Handles restoring the service after a successful upgrade"""
        raise NotImplementedError

    def fix_hostname(self, host):
        """Override this to allow the handler to "rename" the host as
        needed. This function has access to self.host_args as well as
        self.service_args. Default behaviour is to render the template
        from the "fix-hostname" argument, or return the hostname as is"""
        fix_hostname = self.service_args.get('fix-hostname')
        if fix_hostname is not None:
            return jinja(fix_hostname, host=host)

        return host


class NovaComputeService(Service):
    """Service handler for nova-compute"""

    @property
    def name(self):
        return 'nova-compute'

    def evacuate(self):
        """Disable nova-compute service on this host, migrate away
        all running and stopped instances"""

        if self.service_args.get('skip-evacuate'):
            return True

        # Disable nova-compute
        openstack_cmd(
            'openstack compute service set {} nova-compute --disable'.format(
                quote(self.host)))

        # Retrieve list of VMs, indexable by their Instance ID
        server_list = openstack_cmd_table(
            'nova hypervisor-servers {}'.format(quote(self.host)))
        servers = {s['ID']: s for s in server_list}

        # Schedule live migration for running VMs
        result = openstack_cmd_table('nova host-evacuate-live {}'.format(
            quote(self.host)))

        for server in result:
            iid = server['Server UUID']

            if server['Live Migration Accepted'] == 'True':
                servers[iid].update({'status': 'OK'})
            else:
                servers[iid].update({
                    'status': 'NOTOK',
                    'error': server['Error Message']})

        # Errors with live migration may occur for VMs that are stopped.
        # Migrate them as well
        result = openstack_cmd_table('nova host-servers-migrate {}'.format(
            quote(self.host)))

        for server in result:
            iid = server['Server UUID']

            if server['Migration Accepted'] == 'True':
                servers[iid].update({'status': 'OK'})
                del servers[iid]['error']
            elif servers[iid].get('status', '') != 'OK':
                servers[iid].update({
                    'status': 'NOTOK',
                    'error': server['Error Message']})

        errors = {
            k: v for k, v in servers.items() if v['status'] != 'OK'
        }
        if errors:
            log.fatal('[{}] {}'.format(self.host, errors))
            return False

        # Wait for migrations to complete
        try:
            timeout_per_server = int(self.service_args.get('timeout', 40))
        except (ValueError, TypeError):
            log.debug('[{}] Defaulting to 40 seconds timeout'.format(
                self.host))

            timeout_per_server = 40

        timeout = len(server_list) * timeout_per_server
        while server_list and timeout > 0:
            timeout -= 5
            sleep(5)

            server_list = openstack_cmd_table(
                'nova hypervisor-servers {}'.format(quote(self.host)))

            log.debug('[{}] Waiting for migrations, {} remaining'.format(
                self.host, len(server_list)))

        if server_list:
            log.fatal('[{}] Some migrations timed-out: {}'.format(
                self.host, server_list))
            return False
        else:
            log.debug('[{}] All servers migrated successfully'.format(
                self.host))

        return True

    def restore(self):
        """Restores nova-compute service"""
        if self.service_args.get('skip-restore'):
            return True

        openstack_cmd(
            'openstack compute service set {} nova-compute --enable'.format(
                quote(self.host)))

        return True


class ThrukDowntimeService(Service):
    """Service handler for thruk-downtime."""
    @property
    def name(self):
        return 'thruk-downtime'

    def __init__(self, host_name, host_args, service_args):
        super(ThrukDowntimeService, self).__init__(
            host_name, host_args, service_args)

        self.thruk_url = host_args.get(
            'thruk-url', service_args.get('thruk-url'))
        self.thruk_username = host_args.get(
            'thruk-username', service_args.get('thruk-username'))
        self.thruk_password = host_args.get(
            'thruk-password', service_args.get('thruk-password'))

    def evacuate(self):
        """Use the Thruk Rest API to disable notifications for this host."""

        if self.thruk_url is None:
            return False

        try:
            self.nagios_hostname = thruk_get_host(self.thruk_url,
                                                  self.thruk_username,
                                                  self.thruk_password,
                                                  self.host)

        except (json.JSONDecodeError, ValueError, KeyError, TypeError):
            log.fatal('[{}] Failed to retrieve Nagios name'.format(
                self.host))

        response = thruk_set_notifications(
            self.thruk_url, self.thruk_username, self.thruk_password,
            self.nagios_hostname, False)

        if response.status != 200:
            log.fatal('[{}] Failed to disable notifications for {}'.format(
                self.host, self.nagios_hostname))

    def restore(self):
        """Use the Thruk Rest API to enable notifications for this host"""
        response = thruk_set_notifications(
            self.thruk_url, self.thruk_username, self.thruk_password,
            self.nagios_hostname, True)

        if response.status != 200:
            log.fatal('[{}] Failed to re-enable notifications for {}'.format(
                self.host, self.nagios_hostname))


services = {
    'nova-compute': NovaComputeService,
    'thruk-downtime': ThrukDowntimeService,
}


def get_service(host_name, host_args, service):
    """Get service handler for service"""
    service_name, service_args = str_or_dict(service)

    Service = services.get(service_name)
    if Service is not None:
        return Service(host_name, host_args, service_args)

    raise ValueError('Invalid service name {}'.format(service_name))
