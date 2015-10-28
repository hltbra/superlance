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
# [eventlistener:crashsentry]
# command=/usr/bin/crashsentry [-s http://sentrydsn]
# events=PROCESS_STATE
#

"""
usage: crashsentry.py [-h] [-s SENTRY_DSN] [-o STDOUT_LINES] [-e STDERR_LINES]

An event listener meant to be subscribed to PROCESS_STATE_CHANGE events. It
will send notifications to Sentry when processes that are children of
supervisord transition unexpectedly to the EXITED state.

optional arguments:
  -h, --help            show this help message and exit
  -s SENTRY_DSN, --sentry_dsn SENTRY_DSN
                        the Sentry DSN to be used. If not specified, it will
                        rely on the environment variable SENTRY_DSN (default:
                        None)
  -o STDOUT_LINES, --stdout_lines STDOUT_LINES
                        the number of stdout lines to read (default: 50)
  -e STDERR_LINES, --stderr_lines STDERR_LINES
                        the number of stderr lines to read (default: 50)

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


class CrashSentry:

    def __init__(self, sentry_dsn, stderr_lines, stdout_lines):
        self.sentry_dsn = sentry_dsn
        self.stderr_lines = stderr_lines
        self.stdout_lines = stdout_lines
        self.stdin = sys.stdin
        self.stdout = sys.stdout
        self.stderr = sys.stderr

    def runforever(self, test=False):
        while True:
            # we explicitly use self.stdin, self.stdout, and self.stderr
            # instead of sys.* so we can unit test this code
            headers, payload = childutils.listener.wait(self.stdin, self.stdout)

            if headers['eventname'] != 'PROCESS_STATE_EXITED':
                # do nothing with non-TICK events
                childutils.listener.ok(self.stdout)
                continue

            pheaders, pdata = childutils.eventdata(payload+'\n')

            if int(pheaders['expected']):
                childutils.listener.ok(self.stdout)
                continue

            msg = 'Process %(groupname)s:%(processname)s exited expectedly\n\n' % pheaders

            if self.stderr_lines:
                msg += get_last_lines_of_process_stderr(pheaders, self.stderr_lines)
            if self.stdout_lines:
                msg += get_last_lines_of_process_stdout(pheaders, self.stdout_lines)

            self.stderr.write('unexpected exit, notifying sentry\n')
            self.stderr.flush()

            self.notify_sentry(msg)

            childutils.listener.ok(self.stdout)

    def notify_sentry(self, msg):
        client = raven.Client(dsn=self.sentry_dsn)
        title = 'Supervisor CRASH: %s' % (self._md5(msg))
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
An event listener meant to be subscribed to PROCESS_STATE_CHANGE
events.  It will send notifications to Sentry when processes that are children of supervisord transition unexpectedly to the EXITED state.
''')
    parser.add_argument('-s', '--sentry_dsn',
                        dest='sentry_dsn',
                        help='the Sentry DSN to be used. If not specified, it will rely on the environment variable SENTRY_DSN')
    parser.add_argument('-o', '--stdout_lines',
                        dest='stdout_lines',
                        type=int,
                        default=50,
                        help='the number of stdout lines to read')
    parser.add_argument('-e', '--stderr_lines',
                        dest='stderr_lines',
                        type=int,
                        default=50,
                        help='the number of stderr lines to read')

    args = parser.parse_args()
    if not args.sentry_dsn and 'SENTRY_DSN' not in os.environ:
        sys.stderr.write("You must specify the --sentry-dsn option or export the SENTRY_DSN variable (neither of them were specified).\n")
        sys.exit(1)

    if 'SUPERVISOR_SERVER_URL' not in os.environ:
        sys.stderr.write('crashsentry must be run as a supervisor event '
                         'listener\n')
        sys.stderr.flush()
        sys.exit(1)

    prog = CrashSentry(args.sentry_dsn, args.stderr_lines, args.stdout_lines)
    prog.runforever()


if __name__ == '__main__':
    main()
