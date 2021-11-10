import sys
from pathlib import Path

import shell

VERBOSE = '--verbose' in sys.argv

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
