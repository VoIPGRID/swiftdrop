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

For example, a configuration with one Swift account that distributes
incoming mail over a ``DEFAULT`` and a specific ``fallback@test.com``
account, could be configured as follows::

    # Postfix configuration (read by start wrapper)
    MYHOSTNAME=swiftdrop.example.com
    RELAY_DOMAINS=example.com,test.com

    # Postfix configuration read by confd
    MYRECIPIENTS='["swiftdrop@example.com", "whatever@test.com"]'

    # Swiftdrop configuration read by confd
    SWIFTDROP_DEFAULT_RECIPIENT=DEFAULT
    SWIFTDROP_DEFAULT_CONTAINER=fallback_and_test_container
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
    SWIFTDROP_PRODUCTION_RECIPIENT=swiftdrop@example.com
    SWIFTDROP_PRODUCTION_CONTAINER=production
    ...

The ``confd`` binary will convert the environment to
``/etc/swiftdrop.ini``, among others, during startup. Yielding a config
that may look somewhat like this:

.. code-block:: ini

    [DEFAULT]
    recipient = DEFAULT
    container = fallback_and_test_container
    auth_version = 3
    authurl = https://keystone-server/v3
    user = myuser
    key = xxx
    os_options_project_name = project
    os_options_project_domain_name = project_domain
    os_options_user_domain_name = user_domain

    [PRODUCTION]
    recipient = swiftdrop@example.com
    container = production
    ...


Completed subtickets
--------------------

- Docker + Stretch image
- Postfix (3+)
- Python3.5 (comes with postfix install)
- Config of Swift accounts, and mail destunations through ENV
- main.cf config, for relay of desired recipients to Swift
- master.cf config
- Check Swift account (auth) on startup
- Only ``2xx`` incoming mail if it is actually uploaded to Swift
  (otherwise it sends: ``451 4.3.0 Error: queue file write error``) by
  using the before-queue smtpd_proxy_filter
- Describe if/how do we cope with duplicates (email message-id cannot be
  used as globablly unique value)
- Add example code to dequeue stored mail (if possible with minimal
  dependencies)


Non-completed subtickets
------------------------

- Check that HELO hostname is remotely resolvable
- Add currently implemented cur/MAILDIR scheme in synopsis at the top
- Document how the mails are stored and write up example how they can be
  retrieved/dequeued
- Fix main.cf to cope with SSL (allow anonymous starttls if the peer
  wants to)
- Add countermeasures against spam / floods / other malicious stuff (?)
- Check/fix that SSL is kept up to date (both the ca-certificates -- for
  swift uploads -- and the postfix SSL keys)
- Review max (attachment) filesize
- Add (log? mail?) notification when Swift upload fails; so we can look into it
- Also pass along admin/postmaster/hostmaster/etc@ etc.. to a custom
  spindle address
- These instances will at the edge (direct MX, so we'll still need to
  add opportunistic TLS, and possibly minimal spam/abuse protections)
- This should be hosted at OSSO while spindle does not load balance non-http


.. _`run-docker.sh`: examples/run-docker.sh
.. _`swiftq-example.py`: examples/swiftq-example.py
