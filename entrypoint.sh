#!/bin/sh
# entrypoint.sh (part of voipgrid/swiftdrop) sets ENV-based config into
#   the appropriate configuration files
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
set -e

[ "${DEBUG}" = "yes" ] && set -x

postfix_config() {
    key=$1
    value=$2
    echo "Setting postfix $key: $value"
    [ "$key" = "" ] && echo "ERROR: No key set !!" && exit 1
    [ "$value" = "" ] && echo "ERROR: No value set !!" && exit 1
    postconf -e "$key = $value"
}

postfix_config "myhostname" "$MYHOSTNAME"

# Take MYDOMAIN or keep domain.tld from a.b.c.domain.tld from MYHOSTNAME
[ -z "$MYDOMAIN" ] && MYDOMAIN="$(echo "$MYHOSTNAME" |
    sed -e 's/.*[.]\([^.]\+[.][^.]\+\)$/\1/g')"

postfix_config "mydomain" "$MYDOMAIN"
postfix_config "myorigin" '$mydomain'
postfix_config "relay_domains" "$RELAY_DOMAINS"

# Create /etc/swiftdrop.ini and /etc/postfix/transport
confd -onetime -backend env

newaliases
postmap /etc/postfix/transport

# Check swift connection before startup
swiftdrop.py --test-connect $(awk '/^[^#]/{print $1}' /etc/postfix/transport)

# Start argv
exec "$@"
