from sys import exit

def log_error(message):
    message = '[ERROR] ' + message
    print(message)
    exit(1)

def log_warning(message):
    message = 'Warning: ' + message
    print(message)

def log_info(message):
    message = 'Info: ' + message
    print(message)
