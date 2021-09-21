import sys
from pathlib import Path

import shell

LOG_LEVEL = 'warning'
if '--log-level-info' in sys.argv:
    LOG_LEVEL = 'info'

def log_error(message):
    message = '[ERROR] ' + message
    print(message)
    sys.exit(1)

def log_warning(message):
    message = 'Warning: ' + message
    print(message)

def log_info(message):
    if LOG_LEVEL == 'info':
        message = 'Info: ' + message
        print(message)

def print_log():
    # If daemon installed
    if Path('/etc/systemd/system/cpuauto.service').exists():
        print(shell.shell('journalctl -u cpuauto.service'))
    else:
        log_error("cpuauto.service is not installed. Run 'cpuauto --daemon' to install daemon (systemd).")
