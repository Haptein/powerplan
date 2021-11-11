import sys
from pathlib import Path
from subprocess import PIPE, run

import shell

VERBOSE = '--verbose' in sys.argv
CAN_NOTIFY = not bool(run('which notify-send', stdout=PIPE, shell=True).returncode)

def error(message):
    message = '[ERROR] ' + message
    print(message, flush=True)
    sys.exit(1)

def warning(message):
    message = 'Warning: ' + message
    print(message, flush=True)

def info(message):
    if VERBOSE:
        message = 'Info: ' + message
        print(message, flush=True)

def print_log():
    # If daemon installed
    if Path('/etc/systemd/system/powerplan.service').exists():
        print(shell.shell('journalctl -u powerplan.service'))
    else:
        error("powerplan.service is not installed. Run 'powerplan --daemon' to install daemon (systemd).")

def notify(message):
    shell.shell(f'notify-send "{message}" "powerplan"', return_stdout=False)
