#!/usr/bin/python3
from sys import exit
from time import time
from argparse import ArgumentParser

from psutil import Process

import log
import cpu
from config import read_profiles, get_triggered_profile

NAME = 'cpuauto.py'

argparser = ArgumentParser(description='Automatic CPU power configuration control.')
argparser.add_argument('-p', '--profile', default='', help='activate a given profile and exit')
argparser.add_argument('-l', '--list', action='store_true', help='list profiles and exit')
argparser.add_argument('-s', '--status', action='store_true', help='show system status')
argparser.add_argument('-d', '--debug', action='store_true', help="display additional runtime info")
argparser.add_argument('-v', '--version', action='store_true', help='show program version and exit')
argparser.add_argument('-r', '--reload', action='store_true', help='hot-reload profiles (for testing)')
ARGS = argparser.parse_args()


def debug_runtime_info(process, profile, iteration_start):
    cpuauto_util, cpuauto_mem = cpu.read_process_cpu_mem(process)
    time_iter = (time() - iteration_start) * 1000  # ms
    print(f'\nProcess resources: CPU {cpuauto_util:.2f}%, Memory {cpuauto_mem:.2f}%, Time {time_iter:.3f}ms\n')

def single_activation(profile):
    profiles = read_profiles()
    if profile in profiles:
        profiles[ARGS.profile].apply()
        print(profiles[ARGS.profile])
    else:
        log.log_error(f'Profile "{ARGS.profile}" not found in config file.')

def main_loop(monitor_mode):
    process = Process()
    profiles = read_profiles()

    while True:
        iteration_start = time()

        if ARGS.reload:
            profiles = read_profiles()

        # Get profile and apply
        profile = get_triggered_profile(profiles)
        if not monitor_mode:
            profile.apply()

        # Everything else
        if ARGS.status:
            cpu.show_system_status(profile)
        if ARGS.debug:
            debug_runtime_info(process, profile, iteration_start)

        # Then sleep needed time
        profile.sleep(iteration_start=iteration_start)


if __name__ == '__main__':
    if not cpu.is_root():
        log.log_error('Must be run with root provileges.')

    # List profiles and exit
    if ARGS.list:
        profiles = read_profiles()
        for name in profiles:
            print(name)
        exit(0)

    # Activate profile and exit
    if ARGS.profile:
        single_activation(ARGS.profile)
        if ARGS.status:
            cpu.show_system_status()
        exit(0)

    # Check if cpuauto is already running
    if cpu.process_instances(NAME) > 1:
        if ARGS.status:
            print('An instance of cpuauto is already running. This one will just report system status.')
            monitor_mode = True
        else:
            log.log_error('An instance of cpuatuto is already running.')
    else:
        monitor_mode = False

    # System info
    if ARGS.status:
        print(cpu.SYSTEM_INFO)

    try:
        main_loop(monitor_mode)
    except KeyboardInterrupt:
        exit(0)

    # Sorted by priority
    # TRIGGER_PROCS = { cpuprofile.triggerapps for cpuprofile in PROFILES_SORTED}
