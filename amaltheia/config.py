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

import os
import logging


class Config:
    _entries = dict(
        openstack_rc=os.getenv('OPENSTACK_RC', 'pilot.rc'),
        ssh_id_rsa_file=os.getenv('SSH_ID_RSA', 'ssh_id_rsa'),
        ssh_id_rsa_password=os.getenv('SSH_ID_RSA_PASSWORD', None),
        ssh_user=os.getenv('SSH_USER', 'ubuntu'),
        ssh_config_file=os.getenv('SSH_CONFIG_FILE', 'ssh_config'),
        ssh_strict_host_key_checking=False,
        log_level=logging.INFO,
        color=True,
        list_hosts=False
    )

    variables = dict()

    def __getattribute__(self, name):
        """overrides so that config.OPTION returns config.entries['OPTION']"""
        if name in super().__getattribute__('_entries'):
            return super().__getattribute__('_entries')[name]

        return super().__getattribute__(name)

    @classmethod
    def load(cls, config):
        """loads and overrides configuration from @config dict"""
        try:
            for key, value in config.items():
                # allow setting log_level via int or string
                if key == 'log_level':
                    if isinstance(value, int):
                        cls._entries[key] = value
                    elif isinstance(value, str):
                        cls._entries[key] = getattr(logging, value.upper())

                elif key == 'color':
                    cls._entries[key] = value not in [
                        0, None, False, 'no', 'false', 'off']

                elif key == 'list_hosts':
                    cls._entries[key] = value

                elif key in cls._entries:
                    cls._entries[key] = value

        except (ValueError, KeyError) as e:
            logging.getLogger('amaltheia').exception(
                '[amaltheia] Invalid config: {}'.format(e))


config = Config()
