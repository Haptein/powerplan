import subprocess
from os import getuid

PIPE = subprocess.PIPE

def shell(command: str, return_stdout: bool = True) -> str:
    shell_subprocess = subprocess.run(command, stdout=PIPE, shell=True)
    if return_stdout:
        return shell_subprocess.stdout.decode('utf-8')

def is_root():
    return getuid() == 0

def read_procs() -> set:
    return set(shell("grep -sh . /proc/*/comm").splitlines())  # 2000 : 13.47s

def process_instances(name: str) -> int:
    return shell("grep -sh . /proc/*/comm").splitlines().count(name)

def process_already_running(name: str = 'cpuauto') -> bool:
    return process_instances(name) > 1

def uninstall():
    shell('/opt/cpuauto/uninstall')
    print('SEE YOU SPACE COWBOY...')

def enable_daemon():
    shell('/opt/cpuauto/enable-daemon')

def read_datafile(path, dtype=str):
    '''Reads first line of path (str or Path), strips and converts to dtype.'''
    with open(path, "r") as file:
        data = file.readline().strip()
    return dtype(data)