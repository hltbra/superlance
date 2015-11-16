import os
from supervisor import childutils


__all__ = [
    'get_last_lines_of_process_stderr',
    'get_last_lines_of_process_stdout',
    'get_last_lines_of_process_stderr_unwrapped',
    'get_last_lines_of_process_stdout_unwrapped',
]

MAX_BYTES_TO_READ = 1024 * 50 # 50kb


def get_last_lines(proc_name, get_last_bytes_func, read_bytes_func, lines):
    """\
    Read last @lines from process @proc_name,
    using @get_last_bytes_func and @read_bytes_func.

    This function reads at most `MAX_BYTES_TO_READ` bytes, currently 50KB
    """
    bytes, offset, _ = get_last_bytes_func(proc_name, 0, MAX_BYTES_TO_READ)
    last_lines = bytes.split('\n')
    return '\n'.join(last_lines[-lines - 1:])


def get_proc_name(pheaders):
    if pheaders['groupname']:
        return pheaders['groupname'] + ':' + pheaders['processname']
    else:
        return pheaders['processname']


def get_last_lines_of_process_stderr_unwrapped(pheaders, stderr_lines):
    rpc = childutils.getRPCInterface(os.environ)
    proc_name = get_proc_name(pheaders)
    result = get_last_lines(
        proc_name,
        rpc.supervisor.tailProcessStderrLog,
        rpc.supervisor.readProcessStderrLog,
        stderr_lines)
    return result


def get_last_lines_of_process_stderr(pheaders, stderr_lines):
    last_lines = get_last_lines_of_process_stderr_unwrapped(pheaders, stderr_lines)
    result = '-------LAST LINES OF STDERR---------\n'
    result += last_lines
    result += '-----------------END----------------\n'
    return result


def get_last_lines_of_process_stdout_unwrapped(pheaders, stdout_lines):
    rpc = childutils.getRPCInterface(os.environ)
    proc_name = get_proc_name(pheaders)
    result = get_last_lines(
        proc_name,
        rpc.supervisor.tailProcessStdoutLog,
        rpc.supervisor.readProcessStdoutLog,
        stdout_lines)
    return result


def get_last_lines_of_process_stdout(pheaders, stdout_lines):
    last_lines = get_last_lines_of_process_stdout_unwrapped(pheaders, stdout_lines)
    result = '-------LAST LINES OF STDOUT---------\n'
    result += last_lines
    result += '-----------------END----------------\n'
    return result
