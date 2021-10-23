import time
from os import getuid
from subprocess import PIPE, run

def shell(command: str, return_stdout: bool = True) -> str:
    shell_subprocess = run(command, stdout=PIPE, shell=True)
    if return_stdout:
        return shell_subprocess.stdout.decode('utf-8')

def is_root():
    return getuid() == 0

def read(path, dtype=str):
    '''Reads first line of path (str or Path), strips and converts to dtype.'''
    with open(path, "r") as file:
        data = file.readline().strip()
    return dtype(data)

def path_is_writable(path) -> bool:
    try:
        path.write_text(path.read_text())
    except PermissionError:
        return False
    else:
        return True

def wait_on_boot(t=10):
    '''Make sure t seconds have passed since boot'''
    time_since_boot = time.monotonic()
    if time_since_boot < t:
        time.sleep(t - time_since_boot)

def uninstall():
    shell('/opt/powerplan/uninstall')
    print('SEE YOU SPACE COWBOY...')

def enable_daemon():
    shell('/opt/powerplan/enable-daemon')
