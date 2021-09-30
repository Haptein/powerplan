import sys
from pathlib import Path

import shell

VERBOSE = '--verbose' in sys.argv

def log_error(message):
    message = '[ERROR] ' + message
    print(message, flush=True)
    sys.exit(1)

def log_warning(message):
    message = 'Warning: ' + message
    print(message, flush=True)

def log_info(message):
    if VERBOSE:
        message = 'Info: ' + message
        print(message, flush=True)

def print_log():
    # If daemon installed
    if Path('/etc/systemd/system/cpuauto.service').exists():
        print(shell.shell('journalctl -u cpuauto.service'))
    else:
        log_error("cpuauto.service is not installed. Run 'cpuauto --daemon' to install daemon (systemd).")
