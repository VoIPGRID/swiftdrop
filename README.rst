SwiftDrop
=========

*XXX synopsis here*

*XXX LICENSE info ook here*


Configuration
-------------

You can configure accounts for swiftdrop using environment variables in
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
    MYRECIPIENTS='["swiftdrop@example.com", "fallback@test.com"]'

    # Swiftdrop configuration read by confd
    SWIFTDROP_DEFAULT_RECIPIENT=DEFAULT
    SWIFTDROP_DEFAULT_CONTAINER=mycontainer
    # Swiftdrop configuration as used by swiftclient.Connection
    SWIFTDROP_DEFAULT_AUTH_VERSION=3
    SWIFTDROP_DEFAULT_AUTHURL=https://keystone-server/v3
    SWIFTDROP_DEFAULT_USER=myuser
    SWIFTDROP_DEFAULT_KEY=xxx
    SWIFTDROP_DEFAULT_OS_OPTIONS_PROJECT_ID=123abc
    SWIFTDROP_DEFAULT_OS_OPTIONS_USER_DOMAIN_ID=123abc

    # Swiftdrop configuration for a secondary address
    SWIFTDROP_TEST_RECIPIENT=fallback@test.com
    SWIFTDROP_TEST_CONTAINER=test
    ...

The ``confd`` binary will convert the environment to
``/etc/swiftdrop.ini``, among others, during startup. Yielding a config
that may look somewhat like this:

.. code-block:: ini

    [DEFAULT]
    recipient = DEFAULT
    container = mycontainer
    auth_version = 3
    authurl = https://keystone-server/v3
    user = myuser
    key = xxx
    os_options_project_id = 123abc
    os_options_user_domain_id = 123abc

    [TEST]
    recipient = fallback@test.com
    container = test
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

- Add GPLv3 license
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
