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
import socket
import subprocess
import urllib.request
from base64 import b64encode
from copy import deepcopy

from jinja2 import BaseLoader, DebugUndefined
from jinja2.nativetypes import NativeEnvironment
import paramiko
from colorama import Style, Fore

from amaltheia.config import config


def _openstack_parse_table_output(output):
    """Parses table output format from OpenStack commands. Raises
    IndexError, ValueError on bad output"""
    lines = output.split('\n')

    # assert first, third and last line have "+----+----+----+" format
    if any(x not in '+-' for x in lines[0] + lines[2] + lines[-2]):
        raise ValueError('invalid format')

    # parse column names from second line
    # "| Col1        | Col2       | Col3      |"  ->  ["Col1", "Col2", "Col3"]
    cols = [x.strip() for x in lines[1].split('|')[1:-1]]

    result = []
    # for each data line
    for line in lines[3:-2]:
        # parse values from line
        values = [x.strip() for x in line.split('|')[1:-1]]

        # append to result as a new object
        result.append({k: v for k, v in zip(cols, values)})

    return result


def _openstack_cmd(cmd):
    """Executes an OpenStack command, supplying the required credentials.
    This is a low-level function"""
    return subprocess.run(
        'bash -c ". {} && {}"'.format(config.openstack_rc, cmd),
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def openstack_cmd(cmd):
    """Executes an OpenStack command"""
    p = _openstack_cmd(cmd)
    logging.debug({
        'cmd': cmd,
        'stdout': p.stdout.decode(),
        'stderr': p.stderr.decode()})
    return p


def openstack_cmd_json(cmd):
    """Executes OpenStack command and return parsed JSON output"""
    p = _openstack_cmd(cmd)
    result = json.loads(p.stdout.decode())

    logging.debug({'cmd': cmd, 'json': result})

    return result


def openstack_cmd_table(cmd):
    """Executes OpenStack command and return parsed table output"""

    p = _openstack_cmd(cmd)
    result = _openstack_parse_table_output(p.stdout.decode())

    logging.debug({'cmd': cmd, 'json': result})

    return result


def _ssh_client(host_name, host_args, **kwargs):
    """prepare a paramiko.SSHClient with host keys and our
    custom config. Returns client object and connection arguments.
    Example usage:
```
    client, args = _ssh_client('myhost.domain.name', {})
    client.connect(**args)
    client.exec_command('echo hello')
```
    """

    client = paramiko.SSHClient()

    client.load_system_host_keys()
    if not config.ssh_strict_host_key_checking:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    args = {
        'hostname': host_name,
        'username': host_args.get('ssh-user', config.ssh_user),
        'key_filename': host_args.get('ssh-id-rsa-file',
                                      config.ssh_id_rsa_file),
        'password': host_args.get('ssh-id-rsa-password',
                                  config.ssh_id_rsa_password),
        'timeout': host_args.get('ssh-timeout', 5)
    }

    try:
        proxy_command = host_args.get('ssh-proxycommand')
        if proxy_command is None:
            with open(config.ssh_config_file, 'r') as fin:
                conf = paramiko.SSHConfig()
                conf.parse(fin)

                proxy_command = conf.lookup(host_name).get('proxycommand')

        if proxy_command is not None:
            logging.debug('[{}] Using proxy command {}'.format(
                host_name, proxy_command))
            args.update({'sock': paramiko.ProxyCommand(proxy_command)})

    except Exception:
        pass

    args.update(**kwargs)

    return client, args


def exec_cmd(_kwargs):
    """Executes an arbitrary command, capturing stdout, stderr and return
    code"""

    kwargs = _kwargs.copy()
    kwargs['stdout'] = subprocess.PIPE
    kwargs['stderr'] = subprocess.PIPE
    kwargs.update(kwargs.get('kwargs', {}))
    kwargs.pop('kwargs', None)

    p = subprocess.run(**kwargs)

    rc, stdout, stderr = p.returncode, p.stdout.decode(), p.stderr.decode()
    logging.debug({'exec_args': kwargs, 'stdout': stdout,
                   'stderr': stderr, 'returncode': rc})

    return rc, stdout, stderr


def ssh_cmd(host_name, host_args, cmd, **kwargs):
    """Executes ssh command @cmd on @host_name, @host_args. Any extra arguments
    will be passed to SSHClient.connect().

    Returns stdout, stderr of command (as strings)"""
    client, args = _ssh_client(host_name, host_args, **kwargs)
    client.connect(**args)

    fin, fout, ferr = client.exec_command(cmd)
    stdout = fout.read().decode()
    stderr = ferr.read().decode()

    client.close()

    logging.debug({
        'ssh': args, 'cmd': cmd,
        'stdout': stdout, 'stderr': stderr})

    return stdout, stderr


def ssh_try_connect(host_name, host_args, timeout=5):
    """Tries to connect with ssh on @host_name with @host_args. Return False if
    connection fails or times out, True otherwise"""

    client, args = _ssh_client(host_name, host_args, timeout=timeout)
    try:
        client.connect(**args)

        return True
    except (socket.error,
            paramiko.BadHostKeyException,
            paramiko.SSHException,
            paramiko.AuthenticationException):
        return False


def str_or_dict(entry):
    """Parses config entry and return (name, args). this helps a lot
    in having powerful configuration options per host/strategy/updater etc

    Example:
        str_or_dict('reboot')
            ==>   'reboot', {}
        str_or_dict({'reboot': {'mode': 'ssh'}})
            ==>   'reboot', {'mode': 'ssh'}
    """

    if isinstance(entry, str):
        return entry, {}

    if isinstance(entry, dict):
        if (len(entry) != 1):
            raise ValueError(
                '[amaltheia] entry {} has bad format'.format(entry))

        name, args = list(entry.items())[0]
        return name, (args or {})


def bold(string):
    """Make bold string"""
    if config.color:
        return Style.BRIGHT + string + Style.NORMAL

    return string


def colored(string, color):
    """Add color to string"""
    color = str(color).upper()
    if config.color and hasattr(Fore, color):
        return getattr(Fore, color) + string + Fore.RESET

    return string


def jinja(template, _env=None, **data):
    """Recursively renders a python dict, list or str, evaluating strings
    along the way"""
    kwargs = deepcopy(config.variables)
    kwargs.update(data)

    if _env is None:
        _env = NativeEnvironment(loader=BaseLoader, undefined=DebugUndefined)

    return _env.from_string(str(template)).render(**kwargs, json=json)


def GET(url):
    """Returns the response of a simple GET request"""
    r = urllib.request.urlopen(url)
    logging.info(bold('[http] GET {} {}'.format(url, r.status)))
    return r.read()


def _HTTP(request_json):
    """Returns a urllib.Request object from json data"""
    r = urllib.request.Request(request_json['url'])

    r.headers = request_json.get('headers', {})
    if request_json.get('json', {}):
        r.headers['content-type'] = 'application/json'
        r.data = json.dumps(jinja(request_json['json'])).encode()

    r.method = request_json.get('method', 'GET')
    return r


def HTTP(request_json):
    """Perform HTTP request and return response"""
    return urllib.request.urlopen(_HTTP(request_json))


def override(dictionary, key, value):
    """Override dictionary variables. Key name can have `.` for multiple
    levels. Updates @dictionary in place.
    Example:

    ```
    d = {'a': 1, 'c': {'d': 2}}
    override(d, 'c.d', 10)
    assert d == {'a': 1, 'c': {'d': 10}}
    ```
    """
    if '.' not in key:
        dictionary[key] = value

    else:
        key, rest = key.split('.', 1)
        if not isinstance(dictionary.get(key), dict):
            dictionary[key] = {}

        override(dictionary[key], rest, value)


def thruk_get_host(thruk_url, thruk_username, thruk_password, address):
    """Get Nagios hostname from Thruk API using address. Raise exception
    on error"""
    r = HTTP({
        'url': '{}/hosts?address={}'.format(thruk_url, address),
        'headers': {
            'Authentication': 'Basic {}'.format(
                b64encode('{}:{}'.format(thruk_username, thruk_password) \
                                 .encode()).decode())
        },
        'method': 'GET',
    })

    return json.dumps(r.read())['name']


def thruk_set_notifications(thruk_url, thruk_username, thruk_password, name, enable):
    """Set notifications on or off for Nagios host. Raise exception on error.
    Returns True/False"""
    r = HTTP({
        'url': '{}/hosts/{}/{}_notifications'.format(
            thruk_url, name, 'enable' if enable else 'disable'),
        'headers': {
            'Authentication': 'Basic {}'.format(
                b64encode('{}:{}'.format(thruk_username, thruk_password) \
                                 .encode()).decode())
        },
        'method': 'POST',
    })

    return r
