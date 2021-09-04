from sys import exit

def log_error(message, terminate=True):
    print(message)
    if terminate:
        exit(1)
