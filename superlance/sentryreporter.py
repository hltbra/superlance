#!/usr/bin/env python -u
##############################################################################
#
# Original copyright (c) 2007 Agendaless Consulting and Contributors.
# Copyright (c) 2015 Yipit Inc.
# All Rights Reserved.
#
# This software is subject to the provisions of the BSD-like license at
# http://www.repoze.org/LICENSE.txt.  A copy of the license should accompany
# this distribution.  THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL
# EXPRESS OR IMPLIED WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND
# FITNESS FOR A PARTICULAR PURPOSE
#
##############################################################################

# An event listener meant to be subscribed to PROCESS_STATE_CHANGE
# events.  It will send notifications to Sentry when processes that are children of
# supervisord transition unexpectedly to the EXITED or FATAL states.

# A supervisor config snippet that tells supervisor to use this script
# as a listener is below.
#
# [eventlistener:sentryreporter]
# command=/usr/bin/sentryreporter -e {crash,fatal} [-s http://sentrydsn]
# events=PROCESS_STATE
#

"""
usage: sentry_reporter.py [-h] -e {crash,fatal} [-s SENTRY_DSN]
                          [-o STDOUT_LINES] [-r STDERR_LINES]

An event listener meant to be subscribed to
PROCESS_STATE_CHANGE/PROCESS_STATE_EXITED events. It will send notifications
to Sentry when processes that are children of supervisord transition
unexpectedly to the EXITED/FATAL state.

optional arguments:
  -h, --help            show this help message and exit
  -e {crash,fatal}, --event_type {crash,fatal}
                        if event type is 'crash', it subscribes to the event
                        PROCESS_STATE_CHANGE. If 'fatal', it subscribes to the
                        event PROCESS_STATE_EXITED (default: None)
  -s SENTRY_DSN, --sentry-dsn SENTRY_DSN
                        the Sentry DSN to be used. If not specified, it will
                        rely on the environment variable SENTRY_DSN (default:
                        None)
  -o STDOUT_LINES, --stdout-lines STDOUT_LINES
                        the number of stdout lines to read (default: 10)
  -r STDERR_LINES, --stderr-lines STDERR_LINES
                        the number of stderr lines to read (default: 10)
"""

import argparse
import hashlib
import os
import sys
import raven

from superlance.helpers import (
    get_last_lines_of_process_stderr,
    get_last_lines_of_process_stdout,
)
from supervisor import childutils


SENTRY_STRING_MAX_LENGTH = 4096


class SentryReporter:

    EVENT_NAMES = {
        'crash': 'PROCESS_STATE_EXITED',
        'fatal': 'PROCESS_STATE_FATAL',
    }

    def __init__(self, sentry_dsn, stderr_lines, stdout_lines):
        self.sentry_dsn = sentry_dsn
        self.stderr_lines = stderr_lines
        self.stdout_lines = stdout_lines
        # create and use self.{stdin,stdout,stderr} to make it easier to test
        self.stdin = sys.stdin
        self.stdout = sys.stdout
        self.stderr = sys.stderr

    def runforever(self, event_type):
        while True:
            pheaders, should_ignore = self.get_event_details(event_type)

            if should_ignore:
                childutils.listener.ok(self.stdout)
                continue

            msg_header = 'Process %(groupname)s:%(processname)s exited unexpectedly' % pheaders
            stderr, stdout = self.get_notification_message(pheaders)
            self.notify_sentry(msg_header, stderr, stdout, event_type)

            childutils.listener.ok(self.stdout)

    def get_event_details(self, event_type):
        headers, payload = childutils.listener.wait(self.stdin, self.stdout)
        pheaders, pdata = childutils.eventdata(payload+'\n')

        ignore = self.ignore_event(headers, pheaders, event_type)
        return pheaders, ignore

    def ignore_event(self, headers, pheaders, event_type):
        # 1) event must be an expected event
        # 2) crashes may be expected; fatal errors can't
        return ((headers['eventname'] != self.EVENT_NAMES[event_type]) or
                (event_type == 'crash' and int(pheaders['expected'])))

    def get_notification_message(self, pheaders):
        stderr = ''
        stdout = ''
        if self.stderr_lines:
            stderr = get_last_lines_of_process_stderr(pheaders, self.stderr_lines)
            stderr = stderr[1:-1]  # remove wrapping text (i.e., ------- LAST LINES...)
        if self.stdout_lines:
            stdout = get_last_lines_of_process_stdout(pheaders, self.stdout_lines)
            stdout = stdout[1:-1]  # remove wrapping text (i.e., ------- LAST LINES...)
        return (stderr, stdout)

    def notify_sentry(self, header, stderr, stdout, event_type):
        self.stderr.write('unexpected {}, notifying sentry\n'.format(event_type))
        client = raven.Client(
            dsn=self.sentry_dsn,
            string_max_length=SENTRY_STRING_MAX_LENGTH,
        )

        stderr_body = '\n'.join(stderr.splitlines()[:-1])
        stderr_last_line = stderr.splitlines()[-1] if stderr else ''
        title = 'Supervisor {}: {}'.format(event_type.upper(), self._md5(stderr_body + stdout))
        try:
            client.captureMessage(
                title,
                data={'logger': 'superlance'},
                extra={
                    'header': header,
                    'stderr': stderr_body,
                    'stderr_last_line': stderr_last_line,
                    'stdout': stdout,
                })
        except Exception as e:
            self.stderr.write("Error notifying Sentry: {}\n".format(e))

    def _md5(self, msg):
        return hashlib.md5(msg).hexdigest()


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description='''\
An event listener meant to be subscribed to PROCESS_STATE_CHANGE/PROCESS_STATE_EXITED
events.  It will send notifications to Sentry when processes that are children of supervisord transition unexpectedly to the EXITED/FATAL state.
''')
    parser.add_argument('-e', '--event-type',
                        dest='event_type',
                        choices=['crash', 'fatal'],
                        required=True,
                        help="if event type is 'crash', it subscribes to the event PROCESS_STATE_CHANGE. If 'fatal', it subscribes to the event PROCESS_STATE_EXITED")
    parser.add_argument('-s', '--sentry-dsn',
                        dest='sentry_dsn',
                        help='the Sentry DSN to be used. If not specified, it will rely on the environment variable SENTRY_DSN')
    parser.add_argument('-o', '--stdout-lines',
                        dest='stdout_lines',
                        type=int,
                        default=10,
                        help='the number of stdout lines to read')
    parser.add_argument('-r', '--stderr-lines',
                        dest='stderr_lines',
                        type=int,
                        default=10,
                        help='the number of stderr lines to read')

    args = parser.parse_args()
    if not args.sentry_dsn and 'SENTRY_DSN' not in os.environ:
        sys.stderr.write("You must specify the --sentry-dsn option or export the SENTRY_DSN variable (neither of them were specified).\n")
        sys.exit(1)

    if 'SUPERVISOR_SERVER_URL' not in os.environ:
        sys.stderr.write('sentryreporter must be run as a supervisor event listener\n')
        sys.exit(1)

    prog = SentryReporter(args.sentry_dsn, args.stderr_lines, args.stdout_lines)
    prog.runforever(args.event_type)


if __name__ == '__main__':
    main()
