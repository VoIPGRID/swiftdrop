#!/usr/bin/env python3
# postfix-wait.py (part of voipgrid/swiftdrop) waits for a kill signal
#   and then calls "postfix stop" [making postfix daemon foregroundable]
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
import signal
import subprocess
import sys
import threading


def handler(*args):
    global run

    if run:
        run = False
        subprocess.check_call(['postfix', 'stop'])
        sys.exit(0)


run = True
signal.signal(signal.SIGINT, handler)
signal.signal(signal.SIGTERM, handler)

while run:
    try:
        threading.Event().wait()
    except RuntimeError:
        pass
    if run:
        sys.stderr.write('.')
        sys.stderr.flush()
