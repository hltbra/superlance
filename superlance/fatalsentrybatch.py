#!/usr/bin/env python -u
##############################################################################
#
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

# A event listener meant to be subscribed to PROCESS_STATE_FATAL
# events.  It will send a Sentry notification when processes that are children of
# supervisord transition unexpectedly to the EXITED state.

# A supervisor config snippet that tells supervisor to use this script
# as a listener is below.
#
# [eventlistener:fatalsentrybatch]
# command=python fatalsentrybatch --sentryDsn=http://sentrydns.com/myapi
# events=PROCESS_STATE,TICK_60

doc = """\
fatalsentrybatch.py [--interval=<batch interval in minutes>]
        [--sentryDsn=<sentry dsn>]

Options:

--interval  - batch cycle length (in minutes).  The default is 1.0 minute.
                  This means that all events in each cycle are batched together
                  and sent as a single email

--sentryDsn - the Sentry DSN token URL

--stderr_lines - number of stderr lines to report in the alert

--stdout_lines - number of stdout lines to report in the alert

A sample invocation:

    fatalsentrybatch.py --sentryDsn="http://sentrydsn.com/123"

"""

from supervisor import childutils
from superlance.helpers import (
    get_last_lines_of_process_stderr,
    get_last_lines_of_process_stdout,
)
from superlance.process_state_sentry_monitor import ProcessStateSentryMonitor


class FatalSentryBatch(ProcessStateSentryMonitor):

    event_label = 'FATAL'
    process_state_events = ['PROCESS_STATE_FATAL']

    def __init__(self, **kwargs):
        kwargs['subject'] = kwargs.get('subject', 'Fatal alert from supervisord')
        ProcessStateSentryMonitor.__init__(self, **kwargs)
        self.now = kwargs.get('now', None)

    def get_process_state_change_msg(self, headers, payload):
        pheaders, pdata = childutils.eventdata(payload+'\n')

        txt = 'Process %(groupname)s:%(processname)s failed to start too many \
times\n' % pheaders
        if self.stderr_lines:
            txt += get_last_lines_of_process_stderr(pheaders, self.stderr_lines)
        if self.stdout_lines:
            txt += get_last_lines_of_process_stdout(pheaders, self.stdout_lines)
        return '%s -- %s' % (childutils.get_asctime(self.now), txt)


def main():
    fatal = FatalSentryBatch.create_from_cmd_line()
    fatal.run()


if __name__ == '__main__':
    main()
