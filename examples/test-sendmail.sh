#!/bin/sh
# test-sendmail.sh (part of voipgrid/swiftdrop) contains examples how to
#   send an email to the swiftdrop service
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

cat << EOF
HELO example.com

MAIL FROM:<john@doe.com>

RCPT TO:<deliver@example.com>

DATA

Subject: this is an email
From: <john@doe.com>
To: <deliver@example.com>
Message-ID: <1>

hi there!
.
EOF
nc 172.17.0.2 25
