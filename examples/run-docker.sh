#!/bin/sh
# run-docker.sh (part of voipgrid/swiftdrop) contains examples how to
#   run swiftdrop with docker environment
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

exec docker run --name swiftdrop_example --rm \
  -e UPSTREAM_PROXY_PROTOCOL= \
  \
  -e MYHOSTNAME=swiftdrop.example.com \
  -e RECIPIENTS='["deliver@example.com"]' \
  -e FORWARDS='{
      "hostmaster@example.com": "elsewhere@test.com",
      "postmaster@example.com": "elsewhere@test.com"}' \
  -e POSTMASTER=elsewhere@test.com \
  \
  -e SWIFTDROP_DEFAULT_RECIPIENTS=deliver@example.com \
  -e SWIFTDROP_DEFAULT_AUTH_VERSION=3 \
  -e SWIFTDROP_DEFAULT_AUTHURL=https://keystone-server/v3 \
  -e SWIFTDROP_DEFAULT_USER=myuser \
  -e SWIFTDROP_DEFAULT_KEY=xxx \
  -e SWIFTDROP_DEFAULT_OS_OPTIONS_PROJECT_NAME=mytenant \
  -e SWIFTDROP_DEFAULT_OS_OPTIONS_PROJECT_DOMAIN_NAME=mydomain \
  -e SWIFTDROP_DEFAULT_OS_OPTIONS_USER_DOMAIN_NAME=mydomain \
  -e SWIFTDROP_DEFAULT_CONTAINER=swiftdrop_maildir \
  \
  -it tmp "$@"
