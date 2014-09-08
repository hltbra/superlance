import unittest
from mock import Mock
from superlance.helpers import get_last_lines

class HelpersTest(unittest.TestCase):

    def test_get_last_lines_should_call_functions_correctly(self):
        get_last_bytes_mock = Mock()
        read_bytes_mock = Mock()
        line1 = 'line1\n'
        line2 = 'line2\n'
        line3 = 'line3\n'
        lines = line1 + line2 + line3
        get_last_bytes_mock.return_value = [lines, len(lines), False]
        read_bytes_mock.return_value = lines

        proc_name = 'test:proc'

        result = get_last_lines(
            proc_name=proc_name,
            get_last_bytes_func=get_last_bytes_mock,
            read_bytes_func=read_bytes_mock,
            lines=2
        )

        self.assertEqual(result, 'line2\nline3\n')

    def test_get_last_lines_should_not_add_empty_lines(self):
        get_last_bytes_mock = Mock()
        read_bytes_mock = Mock()
        line1 = 'line1\n'
        line2 = 'line2\n'
        line3 = 'line3\n'
        lines = line1 + line2 + line3
        get_last_bytes_mock.return_value = [lines, len(lines), False]
        read_bytes_mock.return_value = lines

        proc_name = 'test:proc'

        result = get_last_lines(
            proc_name=proc_name,
            get_last_bytes_func=get_last_bytes_mock,
            read_bytes_func=read_bytes_mock,
            lines=10
        )

        self.assertEqual(result, 'line1\nline2\nline3\n')


if __name__ == '__main__':
    unittest.main()