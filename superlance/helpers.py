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