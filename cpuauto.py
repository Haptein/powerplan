#!/usr/bin/python3

from time import sleep
from config import read_profiles
from cpu import read_procs

def get_triggered_profile(PROFILES: dict, PROFILES_SORTED: list):
    '''Returns triggered CpuProfile object according to running processes'''
    # Check running processes
    procs = read_procs()

    # check profile trigger apps against procs
    for cpuprofile in PROFILES_SORTED:
        if cpuprofile.triggerapp_present(procs):
            return cpuprofile
    else:
        return PROFILES['DEFAULT']


def update_cpu_settings(cpuprofile):
    pass


PROFILES = read_profiles()
# Sorted by priority
PROFILES_SORTED = sorted(PROFILES.values())
#TRIGGER_PROCS = { cpuprofile.triggerapps for cpuprofile in PROFILES_SORTED}

if __name__ == '__main__':
    while True:
        needed_profile = get_triggered_profile(PROFILES, PROFILES_SORTED)
        print(needed_profile.name)
        sleep(needed_profile.pollingperiod / 1000)
