SwiftDrop
=========

*SwiftDrop, or smtp2swift, receives email messages over SMTP and writes
them to a configured OpenStack Swift container where they await further
processing by some other process.*

It consists of:

* a **docker** image;
* with a **postfix** SMTP daemon;
* some glue to make Postfix runnable inside docker;
* and a *before-queue* filter that stores incoming messages in **swift**.

The messages end up in *Maildir*-format inside the ``cur/`` path in
the configured Swift container.

Basic usage involves:

* running the docker image;
* sending a message/rfc822 email message over SMTP on port 25;
* seeing the message end up in the Swift container, named something like
  ``cur/1567067375.M6337175P228.f87ce1e3553a,S=241``, where the first
  digits are the delivery unixtime.

See `run-docker.sh`_ for a sample invocation.

Processing the delivered mail is beyond the scope of this project, but a
suggested operation is:

* listing the files in ``cur/``;
* taking the first -- using a key-based global lock to lock that file --
  downloading it, and moving it (copy+delete) to ``processing/``;
* doing the processing;
* then -- again, using a lock -- moving it from ``processing/`` to one
  of ``done/``, ``failed/`` or ``retry/``;
* and using a separate job to delete very old messages.

See `swiftq-example.py`_ for sample dequeueing.


License
-------

This project is licensed under the terms of the GPLv3 license.


Configuration
-------------

You can configure accounts for SwiftDrop using environment variables in
the form ``SWIFTDROP_<SECTION>_<OPTION>``.

You must specify at least one account where ``SECTION=DEFAULT``. The
configuration options can be specified using UPPERCASE.

For example, a configuration with *one Swift account* that distributes
incoming mail over an *acceptance* and a *production* container, for *three
distinct e-mail addresses*, could be configured as follows::

    # Postfix configuration (read by start wrapper and/or confd)
    # - postfix hostname, prefer having it resolvable, also used in HELO
    MYHOSTNAME=swiftdrop.example.com
    # - swiftdrop destinations (see also SWIFTDROP_xxx_RECIPIENTS)
    RECIPIENTS='[
      "swiftdrop@example.com", "whatever@test.com", "whatever2@test.com"]'
    # - forwards to other destinations (postmaster, bounces, ...)
    FORWARDS='{
      "postmaster@example.com": "swiftdrop@elsewhere.com",
      "info@example.com": "swiftdrop@elsewhere.com",
      "info@test.com": "swiftdrop@elsewhere.com"}'
    POSTMASTER=swiftdrop@elsewhere.com

    # Swiftdrop configuration read by confd
    SWIFTDROP_DEFAULT_RECIPIENTS=whatever@test.com,whatever2@test.com
    SWIFTDROP_DEFAULT_CONTAINER=acceptance
    # Swiftdrop configuration as used by swiftclient.Connection
    SWIFTDROP_DEFAULT_AUTH_VERSION=3
    SWIFTDROP_DEFAULT_AUTHURL=https://keystone-server/v3
    SWIFTDROP_DEFAULT_USER=myuser
    SWIFTDROP_DEFAULT_KEY=xxx
    SWIFTDROP_DEFAULT_OS_OPTIONS_PROJECT_DOMAIN_NAME=project_domain
    SWIFTDROP_DEFAULT_OS_OPTIONS_PROJECT_NAME=project
    SWIFTDROP_DEFAULT_OS_OPTIONS_USER_DOMAIN_NAME=user_domain

    # Swiftdrop configuration for a secondary address;
    # note that values from DEFAULT are available here too,
    # and need to be overwritten with blanks if they conflict.
    # For sanity, the DEFAULT above is the catch-all, and this
    # one handles only the "production" address.
    SWIFTDROP_PRODUCTION_RECIPIENTS=swiftdrop@example.com
    SWIFTDROP_PRODUCTION_CONTAINER=production
    ...

The ``confd`` binary will convert the environment to
``/etc/swiftdrop.ini``, among others, during startup. Yielding a config
that may look somewhat like this:

.. code-block:: ini

    [DEFAULT]
    recipients = whatever@test.com,whatever2@test.com
    container = acceptance
    auth_version = 3
    authurl = https://keystone-server/v3
    user = myuser
    key = xxx
    os_options_project_name = project
    os_options_project_domain_name = project_domain
    os_options_user_domain_name = user_domain

    [PRODUCTION]
    recipients = swiftdrop@example.com
    container = production
    ...


Completed subtickets
--------------------

- Docker + Stretch image
- Postfix (3+)
- Python3.5 (comes with postfix install)
- Config of Swift accounts, and mail destinations through ENV
- main.cf config, for relay of desired recipients to Swift
- master.cf config
- Check Swift account (auth) on startup
- Only ``2xx`` incoming mail if it is actually uploaded to Swift
  (otherwise it sends: ``451 4.3.0 Error: queue file write error``) by
  using the before-queue smtpd_proxy_filter
- Describe if/how do we cope with duplicates (email message-id cannot be
  used as globablly unique value)
- Add example code to dequeue stored mail (if possible with minimal
  dependencies): see examples/swiftq-example.py
- Opportunistic TLS has been observed to work out of the box.
- Hosting at OSSO in ossoio-k8s + swift2019.
- Allow forwarding of postmaster@ and other names to elsewhere.
- Enlarge message limits to 50MB.


Optional subtickets
-------------------

- Add basic SPF checks?
- Add DKIM checks?
- Add countermeasures against spam / floods / other malicious stuff.
- Add currently implemented cur/MAILDIR scheme in synopsis at the top.
- Check/fix that SSL is kept up to date (both the ca-certificates -- for
  swift uploads -- and that postfix SSL snakeoil keys are kept up to date).
- Failures are now logged, but K8S is not scraped: do we need an
  ERRORMAIL (logging) handler?


.. _`run-docker.sh`: examples/run-docker.sh
.. _`swiftq-example.py`: examples/swiftq-example.py
