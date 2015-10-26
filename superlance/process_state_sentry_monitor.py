import hashlib
import os
import raven
import socket
import sys
from superlance.process_state_monitor import ProcessStateMonitor


class ProcessStateSentryMonitor(ProcessStateMonitor):
    event_label = 'ERROR'

    @classmethod
    def _get_opt_parser(cls):
        from optparse import OptionParser
        parser = OptionParser()
        parser.add_option("-i", "--interval", dest="interval", type="float", default=1.0,
                        help="batch interval in minutes (defaults to 1 minute)")
        parser.add_option("-S", "--sentryDsn", dest="sentry_dsn",
                        help="Sentry DSN")
        parser.add_option("-e", "--tickEvent", dest="eventname", default="TICK_60",
                        help="TICK event name (defaults to TICK_60)")
        parser.add_option("-q", "--stderr_lines", dest="stderr_lines", type="int", default=10,
                        help="Number of stderr lines to report")
        parser.add_option("-w", "--stdout_lines", dest="stdout_lines", type="int", default=10,
                        help="Number of stdout lines to report")
        return parser

    @classmethod
    def get_cmd_line_options(cls):
        parser = cls._get_opt_parser()
        options, _ = parser.parse_args()
        if not options.sentry_dsn and not os.getenv('SENTRY_DSN'):
            parser.print_help()
            sys.exit(1)
        return options

    @classmethod
    def create_from_cmd_line(cls):
        options = cls.get_cmd_line_options()
        if not 'SUPERVISOR_SERVER_URL' in os.environ:
            sys.stderr.write('Must run as a supervisor event listener\n')
            sys.exit(1)
        return cls(**options.__dict__)

    def __init__(self, **kwargs):
        ProcessStateMonitor.__init__(self, **kwargs)
        self.sentry_dsn = kwargs['sentry_dsn']
        self.digest_len = 76

    def send_batch_notification(self):
        if self.batchmsgs:
            msg = '\n'.join(self.batchmsgs)
            self.notify_sentry(msg)
            self.log_notification(msg)

    def log_notification(self, msg):
        self.write_stderr("Sending Sentry notification: %s\n" % msg[:self.digest_len])

    def notify_sentry(self, msg):
        client = raven.Client(dsn=self.sentry_dsn)
        title = 'Supervisor %s: %s' % (self.event_label, self._md5(msg))
        try:
            client.captureMessage(
                title,
                data={'logger': 'superlance'},
                extra={'msg': msg})
        except Exception as e:
            self.write_stderr("Error notifying Sentry: %s\n" % e)

    def _md5(self, msg):
        return hashlib.md5(msg).hexdigest()
