from sys import exit

def log_error(message):
    message = 'Error: ' + message
    print(message)
    exit(1)

def log_warning(message):
    message = 'Warning: ' + message
    print(message)
