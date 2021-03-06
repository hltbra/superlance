import unittest
from mock import patch
from superlance.helpers import MAX_BYTES_TO_READ
from superlance.compat import StringIO

class CrashMailTests(unittest.TestCase):
    def _getTargetClass(self):
        from superlance.crashmail import CrashMail
        return CrashMail

    def _makeOne(self, *opts):
        return self._getTargetClass()(*opts)

    def setUp(self):
        import tempfile
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tempdir)

    def _makeOnePopulated(self, programs, any, stderr_lines=0, stdout_lines=0, response=None):
        import os
        sendmail = 'cat - > %s' % os.path.join(self.tempdir, 'email.log')
        email = 'chrism@plope.com'
        header = '[foo]'
        prog = self._makeOne(programs, any, email, sendmail, header, stderr_lines, stdout_lines)
        prog.stdin = StringIO()
        prog.stdout = StringIO()
        prog.stderr = StringIO()
        return prog

    def test_runforever_not_process_state_exited(self):
        programs = {'foo':0, 'bar':0, 'baz_01':0 }
        any = None
        prog = self._makeOnePopulated(programs, any)
        prog.stdin.write('eventname:PROCESS_STATE len:0\n')
        prog.stdin.seek(0)
        prog.runforever(test=True)
        self.assertEqual(prog.stderr.getvalue(), 'non-exited event\n')

    def test_runforever_expected_exit(self):
        programs = ['foo']
        any = None
        prog = self._makeOnePopulated(programs, any)
        payload=('expected:1 processname:foo groupname:bar '
                 'from_state:RUNNING pid:1')
        prog.stdin.write(
            'eventname:PROCESS_STATE_EXITED len:%s\n' % len(payload))
        prog.stdin.write(payload)
        prog.stdin.seek(0)
        prog.runforever(test=True)
        self.assertEqual(prog.stderr.getvalue(), 'expected exit\n')

    def test_runforever_unexpected_exit(self):
        programs = ['foo']
        any = None
        prog = self._makeOnePopulated(programs, any)
        payload=('expected:0 processname:foo groupname:bar '
                 'from_state:RUNNING pid:1')
        prog.stdin.write(
            'eventname:PROCESS_STATE_EXITED len:%s\n' % len(payload))
        prog.stdin.write(payload)
        prog.stdin.seek(0)
        prog.runforever(test=True)
        output = prog.stderr.getvalue()
        lines = output.split('\n')
        self.assertEqual(lines[0], 'unexpected exit, mailing')
        self.assertEqual(lines[1], 'Mailed:')
        self.assertEqual(lines[2], '')
        self.assertEqual(lines[3], 'To: chrism@plope.com')
        self.assertTrue('Subject: [foo]: foo crashed at' in lines[4])
        self.assertEqual(lines[5], '')
        self.assertTrue(
            'Process foo in group bar exited unexpectedly' in lines[6])
        import os
        f = open(os.path.join(self.tempdir, 'email.log'), 'r')
        mail = f.read()
        f.close()
        self.assertTrue(
            'Process foo in group bar exited unexpectedly' in mail)

    @patch('superlance.crashmail.childutils.getRPCInterface')
    def test_stderr_lines_should_use_stderr_tail(self, getRPCInterfaceMock):
        supervisor_mock = getRPCInterfaceMock().supervisor
        tailProcessStderrLogMock = supervisor_mock.tailProcessStderrLog
        tailProcessStderrLogMock.return_value = ['test1\test2\n', 0, False]

        programs = ['foo']
        any = None
        prog = self._makeOnePopulated(programs, any, stderr_lines=2)
        payload=('expected:0 processname:foo groupname:bar '
                 'from_state:RUNNING pid:1')
        prog.stdin.write(
            'eventname:PROCESS_STATE_EXITED len:%s\n' % len(payload))
        prog.stdin.write(payload)
        prog.stdin.seek(0)
        prog.runforever(test=True)

        tailProcessStderrLogMock.assert_called_with(
            'bar:foo',
            0,
            MAX_BYTES_TO_READ
        )

    @patch('superlance.crashmail.childutils.getRPCInterface')
    def test_stderr_lines_should_use_stdout_tail(self, getRPCInterfaceMock):
        supervisor_mock = getRPCInterfaceMock().supervisor
        tailProcessStdoutLogMock = supervisor_mock.tailProcessStdoutLog
        tailProcessStdoutLogMock.return_value = ['test1\test2\n', 0, False]

        programs = ['foo']
        any = None
        prog = self._makeOnePopulated(programs, any, stdout_lines=2)
        payload=('expected:0 processname:foo groupname:bar '
                 'from_state:RUNNING pid:1')
        prog.stdin.write(
            'eventname:PROCESS_STATE_EXITED len:%s\n' % len(payload))
        prog.stdin.write(payload)
        prog.stdin.seek(0)
        prog.runforever(test=True)

        tailProcessStdoutLogMock.assert_called_with(
            'bar:foo',
            0,
            MAX_BYTES_TO_READ
        )

if __name__ == '__main__':
    unittest.main()
