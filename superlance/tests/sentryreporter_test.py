import unittest
import hashlib
from mock import patch
from superlance.compat import StringIO
from superlance.sentryreporter import SentryReporter


class SentryReporterTests(unittest.TestCase):

    def test_ignore_event(self):
        reporter = SentryReporter(sentry_dsn=None, stderr_lines=10, stdout_lines=10)
        exit_event_headers = {'eventname': 'PROCESS_STATE_EXITED'}
        fatal_event_headers = {'eventname': 'PROCESS_STATE_FATAL'}
        stop_event_headers = {'eventname': 'PROCESS_STATE_STOPPED'}

        # should ignore crash when it's expected
        self.assertTrue(
            reporter.ignore_event(
                headers=exit_event_headers,
                pheaders={'expected': 1},
                event_type='crash'),
            'expected crash')

        # should ignore if event is not exit
        self.assertTrue(
            reporter.ignore_event(
                headers=stop_event_headers,
                pheaders={'expected': 0},
                event_type='crash'),
            'unexpected stop')

        # should not ignore crash when it's not expected
        self.assertFalse(
            reporter.ignore_event(
                headers=exit_event_headers,
                pheaders={'expected': 0},
                event_type='crash'),
            'unexpected crash')

        # should ignore fatal if event is not exit
        self.assertTrue(
            reporter.ignore_event(
                headers=exit_event_headers,
                pheaders={},
                event_type='fatal'),
            'exit + fatal')

        # should not ignore fatal if event is an exit
        self.assertFalse(
            reporter.ignore_event(
                headers=fatal_event_headers,
                pheaders={},
                event_type='fatal'),
            'fatal error')

    def test_get_event_details(self):
        reporter = SentryReporter(sentry_dsn=None, stderr_lines=10, stdout_lines=10)
        reporter.stdin = StringIO()
        reporter.stdout = StringIO()

        reporter.stdin.write('ver:3.0 len:69 eventname:PROCESS_STATE_EXITED\n')
        reporter.stdin.write('processname:proc groupname:grp from_state:RUNNING expected:0 pid:123\n')
        reporter.stdin.seek(0)

        event_details = reporter.get_event_details('crash')

        expected_pheaders = {
            'processname': 'proc',
            'groupname': 'grp',
            'from_state': 'RUNNING',
            'expected': '0',
            'pid': '123',
        }
        expected_ignore = False
        self.assertEqual(event_details, (expected_pheaders, expected_ignore))

    def test_notify_sentry(self):
        reporter = SentryReporter(sentry_dsn=None, stderr_lines=10, stdout_lines=10)
        msg_header = 'boom header'
        msg = 'BOOM!!!'
        md5 = hashlib.md5(msg).hexdigest()

        with patch('superlance.sentryreporter.raven') as raven_mock:
            reporter.notify_sentry(msg_header, msg, 'crash')

            raven_mock.Client().captureMessage.assert_called_with(
                'Supervisor CRASH: {}'.format(md5),
                data={'logger': 'superlance'},
                extra={'header': msg_header, 'msg': msg},
            )


if __name__ == '__main__':
    unittest.main()
