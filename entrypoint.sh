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

postfix_config myhostname "$MYHOSTNAME"

# Take MYDOMAIN or keep domain.tld from a.b.c.domain.tld from MYHOSTNAME
[ -z "$MYDOMAIN" ] && MYDOMAIN="$(echo "$MYHOSTNAME" |
    sed -e 's/.*[.]\([^.]\+[.][^.]\+\)$/\1/g')"

postfix_config mydomain "$MYDOMAIN"
postfix_config myorigin '$mydomain'
postfix_config 2bounce_notice_recipient "$POSTMASTER"

# Create /etc/swiftdrop.ini, /etc/postfix/relay_domains,
# /etc/postfix/transport, /etc/postfix/virtual
confd -onetime -backend env || true

# relay_domains is assembled from DESTINATIONS and FORWARDS
test -s /etc/postfix/relay_domains
postfix_config "relay_domains" "$(\
    sort -u /etc/postfix/relay_domains | tr '\n' ' ')"

# smptd_upstream_proxy_protocol is set by UPSTREAM_PROXY_PROTOCOL
opt=smtpd_upstream_proxy_protocol
if grep -q "^[[:blank:]]*-o $opt=" /etc/postfix/master.cf; then
    sed -i -e "s/$opt=[a-z0-9]*/$opt=$UPSTREAM_PROXY_PROTOCOL/" \
        /etc/postfix/master.cf
else
    echo "no $opt in /etc/postfix/master.cf ?" >&2
    exit 1
fi

newaliases
postmap /etc/postfix/transport
postmap /etc/postfix/virtual

# Check swift connection before startup: run it for every 'swiftdrop'
# destination that may or may not have a different Swift backend
test -s /etc/postfix/transport
swiftdrop.py --test-connect $(\
    awk '/^[^#].* discard:silently$/{print $1}' /etc/postfix/transport)

# Start argv
exec "$@"
