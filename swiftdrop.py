#!/usr/bin/env python3
# swiftdrop.py (part of voipgrid/swiftdrop) listens for SMTP on 10025
#   and saves emails to OpenStack Swift
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
from logging.handlers import SysLogHandler
from os import getpid
from swiftclient import Connection
from swiftclient.exceptions import ClientException
from time import time
import logging
import logging.handlers
import os.path
import select
import signal
import socket
import sys

# Set up logging (no datetime, this is handled by docker/k8s).
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
try:
    handler = SysLogHandler(
        address='/dev/log', facility=SysLogHandler.LOG_DAEMON)
except FileNotFoundError:
    handler = logging.StreamHandler()
formatter = logging.Formatter(
    '[%(process)d] %(module)s.%(funcName)s: %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)


class SmtpProxyMaster:
    def __init__(self, handler_factory):
        self.handler_factory = handler_factory

        # Ignore children, auto-reap zombies.
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)

        # Start listening.
        log.info('Starting')
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('127.0.0.1', 10025))
        self.sock.listen(100)

    def run(self):
        log.info('Mainloop')
        while True:
            conn, address = self.sock.accept()
            pid = os.fork()
            if pid:
                # Don't need this anymore.
                conn.close()
            else:
                # Handle the connection.
                try:
                    log.info('Handling %r', address)
                    handler = self.handler_factory(conn)
                    handler.handle()
                except Exception:
                    log.exception('During handling of %r', address)
                    os._exit(1)
                os._exit(0)


class SmtpProxyHackToGetData(object):
    """
    SMTP proxy that uses a second call back into the server to avoid
    having to implement most of the SMTP protocol.

    Override on_data(self, message) to process the message. Raise any
    error to bail: this will report 4xx back to upstream.

    Args:
        in_[socket]: Socket in the incoming side
        handle_recipients[list]: List of recipients to handle. Anyone
            not in this list will get forwarded. (In fact, if there is
            any in this list, they will all get forwarded, as we do not
            edit RCPT TO. The (already) handled ones are discard by
            postfix later on.)
    """
    def __init__(self, in_, handle_recipients):
        """
        Connect to downstream so we can use their communicating skills.
        """
        self.in_ = in_
        self.handle_recipients = set(i.lower() for i in handle_recipients)
        self.out = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.out.connect(('127.0.0.1', 10026))

    def on_data(self, message, recipients):
        raise NotImplementedError()

    def handle(self):
        try:
            recipients, message = self.collect_email()
            if recipients:
                self.on_data(message, recipients=recipients)
            self.report_success()
        finally:
            for commands in (
                # (self.in_.shutdown, socket.SHUT_RDWR),
                (self.in_.close,),
                (self.out.shutdown, socket.SHUT_RDWR),
                (self.out.close,),
            ):
                try:
                    commands[0](*commands[1:])
                except Exception as e:
                    log.info('During handling of %r', commands, exception=e)

    def collect_email(self):
        """
        Instead of implementing a compatible mail server, we forward the
        message back to the postfix MX immediately.

        Notes:
        - the postfix will not actually use the forwarded message
          (and we won't actually send any)
        - when getting the DATA, we RSET+QUIT the 2nd connection freeing
          up the connection

        Example transscript of a valid forwarded conversation:

        '220 swiftdrop.example.com ESMTP Postfix (Debian/GNU)\r\n'

        'EHLO mx.example.com\r\n'
        '250-\r\n250-PIPELINING\r\n250-SIZE 10240000\r\n'
        '250-VRFY\r\n250-ETRN\r\n250-STARTTLS\r\n'
        '250-XFORWARD NAME ADDR PROTO HELO SOURCE PORT IDENT\r\n'
        '250-ENHANCEDSTATUSCODES\r\n250-8BITMIME\r\n250-DSN\r\n'
        '250 SMTPUTF8\r\n'

        'XFORWARD NAME=[UNAVAILABLE] ADDR=172.17.0.1 \\
         PORT=34004 HELO=client.example.com PROTO=SMTP SOURCE=REMOTE\r\n'
        '250 2.0.0 Ok\r\n'

        'MAIL FROM:<client@example.com>\r\n'
        '250 2.1.0 Ok\r\n'

        'RCPT TO:<dest@example.com>\r\n'
        '250 2.1.5 Ok\r\n'

        'DATA\r\n'
        '354 End data with <CR><LF>.<CR><LF>\r\n'
        ^-- at this point, we're fetching the data ourselves and sending
            RSET+QUIT to downstream, while sending 354 to upstream

        'Received: from ...\r\n.\r\n'
        '250 2.0.0 Ok: queued by swiftdrop\r\n'

        'QUIT\r\n'
        '221 2.0.0 Bye\r\n'
        """
        skip_forward, handle_recipients, pass_recipients = (
            self._collect_email_setup())
        data = self._collect_email_data(skip_forward=skip_forward)
        return handle_recipients, data

    def _collect_email_setup(self):
        bufsiz = 32767
        who = (self.in_, self.out)
        all_recipients = []

        # Talk to other MX and relay all messages, but wait before
        # forwarding DATA.
        # (Not using tempfile for data, as it shouldn't exceeed 10MB-ish
        # anyway.)
        while True:
            rlist, wlist, elist = select.select(who, (), who, 120)

            if elist:
                raise StopIteration('socket exception')

            if self.in_ in rlist:
                data = self.in_.recv(bufsiz)
                if not data:
                    raise StopIteration('in_ disconnected')
                log.debug('[setup] >-- (%d bytes) %.64r...', len(data), data)

                # Technically, this could be split over multiple
                # recv()s, but should never happen in practice. (Same
                # with 'DATA' below.)
                if data.startswith(b'RCPT TO:<'):
                    all_recipients.append(
                        data.split(b'>', 1)[0].split(b'<', 1)[1]
                        .decode('utf-8').lower())

                if data == b'DATA\r\n':
                    handle_recipients = [
                        recipient for recipient in all_recipients
                        if recipient in self.handle_recipients]
                    pass_recipients = [
                        recipient for recipient in all_recipients
                        if recipient not in self.handle_recipients]
                    log.debug(
                        '[setup] handle_recipients: %s', handle_recipients)
                    log.debug(
                        '[setup] pass_recipients: %s', pass_recipients)

                    if pass_recipients:
                        # We must forward it into postfix, regardless of
                        # whether we handle any as well.
                        log.debug(
                            '[setup] --> (%d bytes) %.64r...', len(data), data)
                        self.out.send(data)
                        data = self.out.recv(bufsiz)
                        log.debug(
                            '[setup] <<< (%d bytes) %.64r...', len(data), data)
                        self.in_.send(data)
                        skip_forward = False
                    else:
                        # We capture all. We can drop the out-connection now.
                        log.debug('[setup] <-- 354 End data...')
                        self.in_.send(
                            b'354 End data with <CR><LF>.<CR><LF>\r\n')

                        # We're done, close forward destination:
                        log.debug('[setup] --> RSET')
                        self.out.send(b'RSET\r\n')
                        self.out.recv(bufsiz)
                        skip_forward = True

                    # Done with setup. Return recipients.
                    return skip_forward, handle_recipients, pass_recipients

                log.debug('[setup] --> (%d bytes) %.64r...', len(data), data)
                self.out.send(data)

            if self.out in rlist:
                data = self.out.recv(bufsiz)
                if not data:
                    raise StopIteration('out disconnected')
                log.debug('[setup] <<< (%d bytes) %.64r...', len(data), data)
                self.in_.send(data)

    def _collect_email_data(self, skip_forward):
        bufsiz = 32767

        # Fetch data.
        databuf = []
        while True:
            data = self.in_.recv(bufsiz)
            if not data:
                raise StopIteration('in_ disconnected')
            log.debug('[data] --> (%d bytes) %.64r...', len(data), data)

            databuf.append(data)
            last_bytes = self.get_last_bytes(databuf, 5)
            if last_bytes == b'\r\n.\r\n':
                break

        # Send data on.
        if not skip_forward:
            for data in databuf:
                self.out.send(data)

            # Eat the 250. Or return error.
            data = self.out.recv(bufsiz)
            if not data.startswith(b'250 '):
                raise StopIteration('got {} from internal postfix'.format(
                    data))
            self.out.send(b'QUIT\r\n')
            self.out.recv(bufsiz)

        # Return data.
        return b''.join(databuf)[0:-3]  # drop trailing ".\r\n"

    def report_success(self):
        """
        Report back to caller that we succeeded.
        """
        bufsiz = 4096

        self.in_.send(b'250 2.0.0 Ok: queued by swiftdrop\r\n')
        data = self.in_.recv(bufsiz)
        assert data == b'QUIT\r\n'
        self.in_.send(b'221 2.0.0 Bye\r\n')
        try:
            data = self.in_.recv(bufsiz)
        except Exception:
            pass
        else:
            assert not data

    @staticmethod
    def get_last_bytes(source_array, count):
        if len(source_array[-1]) >= 5:
            last_bytes = source_array[-1][-count:]
        else:
            # Yuck. This should not happen that often.
            last_bytes = b''
            for data in reversed(source_array):
                last_bytes = data[-count:] + last_bytes
                if len(last_bytes) >= count:
                    break

        return last_bytes[-count:]


class SwiftEmailUploader(object):
    def __init__(self, config):
        self.config = config

    def get_connection(self, config):
        timeout = (int(config['timeout']) if config.get('timeout') else None)

        if config['auth_version'] == '3':
            # Keystone v3
            os_options = {}
            for option, value in config.items():
                if option.startswith('os_options_') and value:
                    short_option = option[len('os_options_'):]
                    os_options[short_option] = value

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

    def generate_filename(self, message):
        """
        Technical operation

        (from https://en.wikipedia.org/wiki/Maildir#)
        (from https://wiki2.dovecot.org/MailboxFormat/Maildir#)

        The program that delivers an email message, a mail delivery
        agent, writes it to a file in the tmp directory with a unique
        filename. [...] [The] recommendations had been further amended
        to require that [...] the filename should be created by
        "concatenating enough strings to guarantee uniqueness" [...].

        * Mn, where n is (in decimal) the microsecond counter from the
          same gettimeofday() used for the left part of the unique name.
        * Pn, where n is (in decimal) the process ID.
        * ,S=<size>: <size> contains the file size. Getting the size from
          the filename avoids doing a stat(), which may improve the
          performance. This is especially useful with Maildir++ quota.
        * ,W=<vsize>: <vsize> contains the file's RFC822.SIZE, ie. the
          file size with linefeeds being CR+LF characters. If the message
          was stored with CR+LF linefeeds, <size> and <vsize> are the
          same. [Not needed for our purposes.]

        [...]

        When a cognizant maildir reading process [...] finds messages in
        the new/ directory, it must move them to cur/. [...] An
        informational suffix is appended [... consisting of colon, a '2'
        (version)] a comma and various flags.
        """
        # from datetime import timezone
        # from email import message_from_bytes
        # from email.policy import default as default_policy
        # parsed = message_from_bytes(message, policy=default_policy)
        # # Might not be set, ignore it.
        # message_id = parsed['Message-ID'][1:-1]
        # # Might not be set (although it should), ignore it.
        # timestamp = parsed['Date'].datetime.astimezone(timezone.utc)
        # filename = '{:%Y-%m-%dT%H:%M:%S.%f%z}-{}.eml'.format(
        #     timestamp, message_id)
        sec, usec = [int(i) for i in str(time()).split('.')]
        size = len(message)
        flags = ''  # ':2,S'
        filename = 'cur/{sec}.M{usec}P{pid}.{hostname},S={size}{flags}'.format(
            sec=sec, usec=usec, pid=getpid(), hostname=socket.gethostname(),
            size=size, flags=flags)
        return filename

    def upload(self, recipients, message):
        unique_destinations = self.recipients_to_destinations(recipients)

        for destination in unique_destinations:
            config = self.config[destination]
            filename = self.generate_filename(message)

            log.info(
                '[swift] Uploading (%d bytes) to %s %s: %s',
                len(message), destination, config['container'],
                filename)
            connection = self.get_connection(config)
            # connection.put_container(config['container'])
            connection.put_object(
                config['container'], filename, message,
                content_type='text/plain')  # 'message/rfc822' raises 502s!?
            # .. with swift 2.22, we're seeing 502s by the nginx proxy
            # because the backend apparently disconnects if we use
            # message/rfc822. This is unexplained thusfar.

        log.info('[swift] All uploads done')

    def test_connect(self, recipients):
        unique_destinations = self.recipients_to_destinations(recipients)
        failures = 0

        for destination in unique_destinations:
            config = self.config[destination]
            connection = self.get_connection(config)
            # connection.put_container(config['container'])
            try:
                resp_headers, containers = connection.get_account()
            except ClientException as e:
                log.error(
                    '[swift] Connection to %s FAILED: %s', destination,
                    e)
                failures += 1
            else:
                if config['container'] not in [i['name'] for i in containers]:
                    raise ValueError('missing container {} for {}'.format(
                        config['container'], destination))
                log.info(
                    '[swift] Connection to %s OK: %s', destination,
                    config['container'])

        if failures:
            sys.exit(1)

    def recipients_to_destinations(self, recipients):
        destinations = set()
        for recipient in recipients:
            for section in self.config:
                srecipients = self.config[section].get('recipients').split(',')
                if recipient in srecipients:
                    destinations.add(section)
                    break
            else:
                assert False, '{} not found in recipients'.format(recipient)
        return destinations


class SwiftEmailUploaderHandler(SmtpProxyHackToGetData):
    def __init__(self, uploader, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uploader = uploader

    def on_data(self, message, recipients):
        if not recipients:
            # We must have at least one recipient, or we'd silently
            # upload it to nowhere.
            raise ValueError('did not get recipient')

        self.uploader.upload(recipients, message)


def exit_message(message, code=1, parser=None):
    sys.stderr.write(message)
    if not message.endswith('\n'):
        sys.stderr.write('\n')
    if parser is not None:
        parser.print_usage(sys.stderr)
    sys.exit(code)


def main_proxy(config):
    def handler_factory(*args, **kwargs):
        uploader = SwiftEmailUploader(config)

        handle_recipients = set()
        for section in config:
            srecipients = config[section].get('recipients').split(',')
            handle_recipients.update(srecipients)

        return SwiftEmailUploaderHandler(
            uploader, handle_recipients=handle_recipients, *args, **kwargs)

    proxy = SmtpProxyMaster(handler_factory)
    proxy.run()


def main_swift_connect_test(config, recipients):
    uploader = SwiftEmailUploader(config)
    uploader.test_connect(recipients)


def main_lda(config, recipients, message):
    uploader = SwiftEmailUploader(config)
    uploader.upload(recipients, message)


def main():
    # There are three modes of operation:
    # - proxy-daemon-mode
    # - swift connection test
    # - one-shot email save (DISABLED)
    parser = ArgumentParser(
        description='Drop email to a swift server.')
    parser.add_argument(
        '--input', metavar='FILE', default='-', help='The input file')
    parser.add_argument(
        '--config', metavar='FILE', default='/etc/swiftdrop.ini',
        help='The configuration file')
    parser.add_argument(
        '--test-connect', action='store_true', help='Connection test only')
    parser.add_argument(
        '--run-as-proxy', action='store_true', help='Run in proxy mode')
    parser.add_argument(
        'recipients', metavar='RECIPIENT', nargs='*', help=(
            'The recipients; used for test-connect or one-shot mode only'))
    args = parser.parse_args()

    config = ConfigParser(allow_no_value=True)

    if os.path.exists(args.config):
        with open(args.config, 'r') as f:
            config.read_file(f)
    else:
        with open(args.config, 'w') as f:
            config.write(f)
        exit_message(
            'default config options written to {}'.format(args.config))

    if args.run_as_proxy and not args.test_connect:
        main_proxy(config)
    elif not args.recipients:
        exit_message('error: missing recipients', parser=parser)
    elif args.test_connect:
        main_swift_connect_test(config, args.recipients)
    else:
        raise NotImplementedError(
            "You cannot use this, unless you switch 'discard:silently' "
            "in transports back to 'swiftdrop:'. The discarding is "
            "necessary because we end up there _after_ uploading to swift "
            "if we _also_ have a non-swift recipient.")
        if args.input == '-':
            if sys.stdin.isatty():
                exit_message('error: missing input on stdin', parser=parser)
            message = sys.stdin.buffer.read()
        else:
            with open(args.input, 'rb') as fp:
                message = fp.read()
        main_lda(config, args.recipients, message)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        exit_message('mail transport unavailable: {}'.format(e))
