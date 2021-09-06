#!/usr/bin/python3

from time import sleep
from psutil import Process

import cpu
from config import read_profiles

def get_triggered_profile(PROFILES: dict, PROFILES_SORTED: list):
    '''Returns triggered CpuProfile object according to running processes'''
    # Check running processes
    procs = cpu.read_procs()

    # check profile trigger apps against procs
    for cpuprofile in PROFILES_SORTED:
        if cpuprofile.triggerapp_present(procs):
            return cpuprofile
    else:
        return PROFILES['DEFAULT']


def update_cpu_settings(cpuprofile):
    pass

def debug_runtime_info():
    cpuauto_util, cpuauto_mem = cpu.read_process_cpu_mem(PROCESS)
    print('Profile:', needed_profile.name)
    print('Charging:', cpu.read_charging_state())
    print('CPU Utilization %:', cpu.read_cpu_utilization('avg'))
    print(f'cpuauto: cpu% {cpuauto_util:.2f}, mem% {cpuauto_mem:.2f}')


if __name__ == '__main__':
    PROCESS = Process()
    PROFILES = read_profiles()
    PROFILES_SORTED = sorted(PROFILES.values())
    # Sorted by priority
    # TRIGGER_PROCS = { cpuprofile.triggerapps for cpuprofile in PROFILES_SORTED}
    while True:
        needed_profile = get_triggered_profile(PROFILES, PROFILES_SORTED)
        debug_runtime_info()
        sleep(needed_profile.pollingperiod / 1000)
