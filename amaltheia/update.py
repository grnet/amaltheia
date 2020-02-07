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


from datetime import datetime, timedelta
from time import sleep

import jenkins

import amaltheia.log as log
from amaltheia.utils import (
    ssh_cmd, ssh_try_connect, str_or_dict, jinja, exec_cmd)


class Updater(object):
    """Base updater class"""
    def __init__(self, host_name, host_args, updater_args):
        self.host_args = host_args
        self.updater_args = updater_args

        self.host = self.fix_hostname(host_name)

    def update(self):
        """Perfoms any update actions required. Returns True on success,
        False on error"""
        raise NotImplementedError

    def fix_hostname(self, host):
        """Override this to allow the handler to "rename" the host as
        needed. This function has access to self.host_args as well as
        self.service_args. Default behaviour is to render the template
        from the "fix-hostname" argument, or return the hostname as is"""
        fix_hostname = self.updater_args.get('fix-hostname')
        if fix_hostname is not None:
            return jinja(fix_hostname, host=host, host_args=self.host_args)

        return host


class DummyUpdater(Updater):
    """Dummy updater for testing amaltheia"""
    def update(self):
        print('Dummy update action output for host {}'.format(self.host))
        return True


class SSHTouchFileDummyUpdater(Updater):
    """Dummy SSH updater, touch a file"""
    def update(self):
        fname = self.updater_args.get('filename', '.silently.updated')
        stdout, stderr = ssh_cmd(self.host, self.host_args, 'touch {}'.format(
            fname))
        return stderr == ""


class SSHCommandUpdater(Updater):
    """Dummy SSH updater, touch a file"""
    def __init__(self, host_name, host_args, updater_args):
        super(SSHCommandUpdater, self).__init__(
            host_name, host_args, updater_args)

        self.command = self.updater_args.get('command') or ''
        if not isinstance(self.command, str) or not self.command:
            log.warning('[{}] Invalid ssh command "{}"'.format(
                self.host, self.command))

    def update(self):
        if self.command:
            command = jinja(
                self.command, host=self.host, host_args=self.host_args)
            ssh_cmd(self.host, self.host_args, command)
            return True

        return False


class AptPackagesUpdater(Updater):
    """Update apt packages, ensuring that no interactive prompts stall
    the process. Optionally, send a patchman report

    Optional arguments: {
        "patchman_url": "http://my.patchmanserver.url/",
    }"""

    def update(self):
        stdout, stderr = ssh_cmd(
            self.host, self.host_args,
            'sudo DEBIAN_FRONTEND=noninteractive apt-get -y -q'
            ' -o Dpkg::Options::=--force-confold upgrade;')

        if stderr != "":
            return False

        autoremove = jinja(self.updater_args.get('autoremove', False))
        if autoremove:
            stdout, stderr = ssh_cmd(
                self.host, self.host_args,
                'sudo DEBIAN_FRONTEND=noninteractive apt-get -y -q'
                ' -o Dpkg::Options::=--force-confold autoremove;')

            if stderr != "":
                return False

        patchman_url = self.updater_args.get('patchman-url')
        if patchman_url is not None:
            ssh_cmd(self.host, self.host_args,
                    'sudo patchman-client -s {}'.format(patchman_url))

        return True


class RebootUpdater(Updater):
    """Reboot machine. Optionally, will wait for machine to return

    Optional arguments {
        "wait": True,                   # wait for host to reboot
        "wait_timeout": 100,            # timeout
        "wait_check_interval": 5        # check interval for host
    }"""

    def __init__(self, host_name, host_args, updater_args):
        super(RebootUpdater, self).__init__(
            host_name, host_args, updater_args)

        self.wait = self.updater_args.get('wait', True)

        try:
            self.wait_timeout = int(self.updater_args.get('wait-timeout', 500))
        except (ValueError, TypeError):
            log.debug('[reboot] Default to 500 seconds timeout')
            self.wait_timeout = 500

        try:
            self.wait_check_interval = int(
                self.updater_args.get('wait-check-interval', 10))
        except (ValueError, TypeError):
            log.debug('[reboot] Default to 10 seconds check interval')
            self.wait_check_interval = 10

    def update(self):
        ssh_cmd(self.host, self.host_args, 'sudo reboot')

        if not self.wait:
            log.debug('[{}] Not waiting for reboot'.format(self.host))
            return True

        now = datetime.now()
        timeout = now + timedelta(seconds=self.wait_timeout)
        success = False
        while not success and datetime.now() <= timeout:
            log.debug('[{}] Waiting for reboot...'.format(self.host))
            success = ssh_try_connect(
                self.host, self.host_args, timeout=self.wait_check_interval)

        if not success:
            log.fatal('[{}] Timeout waiting for reboot'.format(self.host))

        return success


class ExecUpdater(Updater):
    """Execute an arbitrary command on the amaltheia host. Use with care"""
    def update(self):
        stdout, stderr, rc = exec_cmd(
            jinja(self.updater_args, host=self.fix_hostname(self.host),
                  **self.host_args))

        expected_rc = self.updater_args.get('expect-returncode')
        if expected_rc is not None:
            return rc == expected_rc

        expected_stdout = self.updater_args.get('expect-stdout')
        if expected_stdout is not None:
            return stdout == expected_stdout

        return True


class JenkinsUpdater(Updater):
    """Post a Jenkins job.

    Required arguments: {
        "server": "https://jenkins.server/",
        "username": "jenkins-user",
        "password": "jenkins-api-key",
        "job": "job-name",
    }

    Optional arguments: {
        "build-arguments": {
            ...
        },
        "wait": True/False,
        "wait-timeout": 200,
        "wait-check-interval": 10,
        "expect-output": "regex-that-can-use-{{ host }}-and-{{ host_args }}"
    }"""
    def __init__(self, host_name, host_args, updater_args):
        super(JenkinsUpdater, self).__init__(host_name, host_args, updater_args)
        self.wait = self.updater_args.get('wait', True)

        try:
            self.wait_timeout = int(self.updater_args.get('wait-timeout', 500))
        except (ValueError, TypeError):
            log.debug('[jenkins] Default to 200 seconds timeout')
            self.wait_timeout = 500

        try:
            self.wait_check_interval = int(
                self.updater_args.get('wait-check-interval', 10))
        except (ValueError, TypeError):
            log.debug('[jenkins] Default to 10 seconds check interval')
            self.wait_check_interval = 10

        self.server = jinja(self.updater_args.get('server'))
        self.username = jinja(self.updater_args.get('username'))
        self.password = jinja(self.updater_args.get('password'))
        self.job = jinja(self.updater_args.get('job'))

        try:
            self.jenkins = jenkins.Jenkins(
                self.server, self.username, self.password)
        except:
            log.exception('[{}] [jenkins] Could not connect to {}'.format(
                self.host, self.server))
            self.jenkins = None

    def update(self):
        try:
            whoami = self.jenkins.get_whoami()
        except:
            log.exception('[{}] [jenkins] Failed to authenticate'.format(
                self.host))
            return False

        if self.job is None:
            log.fatal('[{}] [jenkins] Empty job name'.format(self.host))
            return False

        raw_args = self.updater_args.get('build-arguments')
        try:
            if raw_args:
                queue_id = self.jenkins.build_job(self.job, jinja(
                    raw_args, host=self.host, host_args=self.host_args))
            else:
                queue_id = self.jenkins.build_job(self.job)
        except:
            log.exception('[{}] [jenkins] Failed to queue job {}'.format(
                self.host, self.job))
            return False

        log.info('[{}] [jenkins] Queued job {} (queue id {})'.format(
            self.host, self.job, queue_id))

        if not self.wait:
            return True

        now = datetime.now()
        timeout = now + timedelta(seconds=self.wait_timeout)

        while True:
            try:
                queue_item = self.jenkins.get_queue_item(queue_id)
                job_number = queue_item['executable']['number']
                break
            except KeyError:
                sleep(self.wait_check_interval)
                log.debug('[{}] [jenkins] Waiting for job queue {}'.format(
                    self.host, self.job))
            except:
                log.exception('[{}] [jenkins] Failed to queue job {}'.format(
                    self.host, self.job))
                return False

            if datetime.now() > timeout:
                log.fatal('[{}] [jenkins] Timeout waiting for job queue {}'.format(
                    self.host, self.job))
                return False

        log.info('[{}] [jenkins] Started job {}/{} (queue id {})'.format(
            self.host, self.job, job_number, queue_id))

        done = False
        while not done and datetime.now() <= timeout:
            log.debug('[{}] [jenkins] Waiting for job run {}/{}'.format(
                self.host, self.job, job_number))
            build_info = self.jenkins.get_build_info(self.job, job_number)

            done = build_info['result'] is not None
            if not done:
                sleep(self.wait_check_interval)

        if not done:
            log.fatal('[{}] [jenkins] Timeout waiting for job run {}/{}'.format(
                self.host, self.job, job_number))
            return False

        return build_info['result'] == 'SUCCESS'


updaters = {
    'dummy': DummyUpdater,
    'apt': AptPackagesUpdater,
    'ssh': SSHCommandUpdater,
    'ssh-touch-file': SSHTouchFileDummyUpdater,
    'reboot': RebootUpdater,
    'exec': ExecUpdater,
    'jenkins': JenkinsUpdater,
}


def update(host_name, host_args, updater):
    '''update host'''
    updater_name, updater_args = str_or_dict(updater)

    Updater = updaters.get(updater_name)
    if Updater is not None:
        return Updater(host_name, host_args, updater_args).update()

    return False
