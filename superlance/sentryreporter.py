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
# supervisord transition unexpectedly to the EXITED state.

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


class SentryReporter:

    EVENT_NAMES = {
        'crash': 'PROCESS_STATE_EXITED',
        'fatal': 'PROCESS_STATE_FATAL',
    }

    def __init__(self, sentry_dsn, stderr_lines, stdout_lines):
        self.sentry_dsn = sentry_dsn
        self.stderr_lines = stderr_lines
        self.stdout_lines = stdout_lines
        self.stdin = sys.stdin
        self.stdout = sys.stdout
        self.stderr = sys.stderr

    def runforever(self, event_type, test=False):
        while True:
            # we explicitly use self.stdin, self.stdout, and self.stderr
            # instead of sys.* so we can unit test this code
            headers, payload = childutils.listener.wait(self.stdin, self.stdout)

            if headers['eventname'] != self.EVENT_NAMES[event_type]:
                # do nothing with non-TICK events
                childutils.listener.ok(self.stdout)
                continue

            pheaders, pdata = childutils.eventdata(payload+'\n')

            # crashes may be expected. fatal errors can't.
            if event_type == 'crash' and int(pheaders['expected']):
                childutils.listener.ok(self.stdout)
                continue

            msg = 'Process %(groupname)s:%(processname)s exited expectedly\n\n' % pheaders

            if self.stderr_lines:
                msg += get_last_lines_of_process_stderr(pheaders, self.stderr_lines)
            if self.stdout_lines:
                msg += get_last_lines_of_process_stdout(pheaders, self.stdout_lines)

            self.stderr.write('unexpected {}, notifying sentry\n'.format(event_type))
            self.stderr.flush()

            self.notify_sentry(msg, event_type)

            childutils.listener.ok(self.stdout)

    def notify_sentry(self, msg, event_type):
        client = raven.Client(dsn=self.sentry_dsn)
        title = 'Supervisor {}: {}'.format(event_type.upper(), self._md5(msg))
        try:
            client.captureMessage(
                title,
                data={'logger': 'superlance'},
                extra={'msg': msg})
        except Exception as e:
            self.write_stderr("Error notifying Sentry: %s\n" % e)

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
        sys.stderr.write('sentryreporter must be run as a supervisor event '
                         'listener\n')
        sys.stderr.flush()
        sys.exit(1)

    prog = SentryReporter(args.sentry_dsn, args.stderr_lines, args.stdout_lines)
    prog.runforever(args.event_type)


if __name__ == '__main__':
    main()
