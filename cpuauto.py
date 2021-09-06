#!/usr/bin/python3
from sys import exit
from psutil import Process
from argparse import ArgumentParser

import log
import cpu
from time import time
from config import read_profiles

argparser = ArgumentParser(description='Automatic CPU power configuration control.')
argparser.add_argument('-d', '--debug', action='store_true',
                       help="Display runtime info.")
argparser.add_argument('-i', '--info', action='store_true', help='Show system info.')
args = argparser.parse_args()


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

def debug_runtime_info():
    cpuauto_util, cpuauto_mem = cpu.read_process_cpu_mem(PROCESS)
    print('Profile:', needed_profile.name)
    print('Charging:', cpu.read_charging_state())
    print('CPU Utilization %:', cpu.read_cpu_utilization('avg'))
    print(f'cpuauto: cpu% {cpuauto_util:.2f}, mem% {cpuauto_mem:.2f}')


if __name__ == '__main__':
    if not cpu.is_root():
        log.log_error('Must be run with root provileges.')
    if args.info:
        cpu.display_cpu_info()
        exit(0)

    PROCESS = Process()
    PROFILES = read_profiles()
    PROFILES_SORTED = sorted(PROFILES.values())
    # Sorted by priority
    # TRIGGER_PROCS = { cpuprofile.triggerapps for cpuprofile in PROFILES_SORTED}
    t0 = time()
    while True:
        needed_profile = get_triggered_profile(PROFILES, PROFILES_SORTED)
        if args.debug:
            debug_runtime_info()
            print(f'Time since last iter:{time()-t0:.2f}\n')
            t0 = time()
        needed_profile.apply()
