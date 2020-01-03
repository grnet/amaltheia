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

import logging

from amaltheia.utils import bold, colored


class AmaltheiaFormatter(logging.Formatter):
    """Colorize log output"""
    colors = {
        'DEBUG': 'lightblack_ex',
        'INFO': 'blue',
        'ERROR': 'red',
        'FATAL': 'red',
    }

    def format(self, record, *args, **kwargs):
        color = self.colors.get(record.levelname)
        record.levelname = colored(bold(record.levelname), color)
        return super(AmaltheiaFormatter, self).format(record, *args, **kwargs)


def setup(level):
    """Setup logging"""
    logging.getLogger().setLevel(level)
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(AmaltheiaFormatter("%(levelname)s:%(name)s:%(msg)s"))
    logging.getLogger('amaltheia').addHandler(handler)
    logging.getLogger('paramiko.transport').disabled = True


def logger():
    return logging.getLogger('amaltheia')


def debug(*args, **kwargs):
    return logger().debug(*args, **kwargs)


def fatal(*args, **kwargs):
    return logger().fatal(*args, **kwargs)


def exception(*args, **kwargs):
    return logger().exception(*args, **kwargs)


def info(*args, **kwargs):
    return logger().info(*args, **kwargs)
