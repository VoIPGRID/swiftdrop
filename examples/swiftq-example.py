#!/usr/bin/env python3
# swiftq-example.py (part of voipgrid/swiftdrop) contains examples how to
#   handle swiftdrop queued emails
# Copyright (C) 2019  Walter Doekes, Harm Geerts, VoIPGRID B.V.
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
from argparse import ArgumentParser
from configparser import ConfigParser
from random import choice
from swiftclient import Connection
import sys


class BogoFileLock:
    def __init__(self):
        self._files = set()

    def acquire(self, filename):
        assert filename not in self._files, (filename, self._files)
        if choice([True, False]):
            print('BogoLock.acquire(', filename, ')')
            self._files.add(filename)
        else:
            raise ValueError(
                '{} already locked by someone else (example)'.format(filename))

    def release(self, filename):
        assert filename in self._files, (filename, self._files)
        print('BogoLock.release(', filename, ')')
        self._files.remove(filename)


BOGO_FILE_LOCK = BogoFileLock()


class locked:
    def __init__(self, lock, id_):
        self.lock = lock
        self.id_ = id_

    def __enter__(self):
        self.lock.acquire(self.id_)

    def __exit__(self, type, value, tb):
        self.lock.release(self.id_)


class SwiftEmailViewer(object):
    def __init__(self, config_section):
        self.conn = self.get_connection(config_section)
        self.container = config_section['container']

    def get_connection(self, config):
        timeout = (int(config['timeout']) if config.get('timeout') else None)

        if config['auth_version'] == '3':
            # Keystone v3
            os_options = {}
            for option, value in config.items():
                if option.startswith('os_options_') and value:
                    short_option = option[len('os_options_'):]
                    os_options[short_option] = config.get(option)

            connection = Connection(
                auth_version='3', authurl=config['authurl'],
                user=config['user'], key=config['key'],
                os_options=os_options, timeout=timeout)

        elif config['auth_version'] == '1':
            # Legacy auth
            connection = Connection(
                auth_version='1', authurl=config['authurl'],
                user=config['user'], key=config['key'],
                tenant_name=config['tenant_name'], timeout=timeout)

        else:
            raise NotImplementedError('auth_version? {!r}'.format(config))

        return connection

    def list(self, subdir):
        assert subdir in ('cur', 'processing', 'retry', 'failed', 'done')

        resp_headers, obj_contents = self.conn.get_container(
            self.container, path=subdir)
        for f in obj_contents:
            print('{}  {}'.format(f['last_modified'], f['name']))

    def dequeue(self, subdir, filename):  # move from cur->processing
        assert subdir in ('cur', 'retry')  # 'failed', 'done'

        with locked(BOGO_FILE_LOCK, filename):
            obj = self._download('{}/{}'.format(subdir, filename))
            self._rename(
                '{}/{}'.format(subdir, filename),
                'processing/{}'.format(filename))
            print(obj)

    def finish(self, subdir, filename):
        assert subdir in ('retry', 'failed', 'done')

        with locked(BOGO_FILE_LOCK, filename):
            self._rename(
                'processing/{}'.format(filename),
                '{}/{}'.format(subdir, filename))

    def _download(self, path):
        resp_headers, obj_contents = self.conn.get_object(self.container, path)
        #print(resp_headers)
        #print(obj_contents)
        return obj_contents  # bytes()

    def _rename(self, path, newpath):
        ret = self.conn.copy_object(
            self.container, path, destination='/{}/{}'.format(
                self.container, newpath))
        assert ret is None, ret
        ret = self.conn.delete_object(self.container, path)
        assert ret is None, ret


def main():
    parser = ArgumentParser(
        description='List/dequeue mails from swiftdrop.')
    parser.add_argument(
        '--config', metavar='FILE', default='/etc/swiftdrop.ini',
        help='The configuration file')
    parser.add_argument(
        '--section', metavar='SECTION', default='DEFAULT',
        help='Which section from the config to use')
    parser.add_argument(
        'command', choices=('list', 'dequeue', 'finish'),
        help='What to do')
    parser.add_argument(
        'args', nargs='+', help='Command parameters')
    args = parser.parse_args()

    config = ConfigParser(allow_no_value=True)
    with open(args.config, 'r') as f:
        config.read_file(f)

    app = SwiftEmailViewer(config[args.section])
    cmd = getattr(app, args.command)
    cmd(*args.args)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print('mail transport unavailable: {}'.format(e), file=sys.stderr)
        sys.exit(1)
