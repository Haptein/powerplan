#!/usr/bin/python3
from sys import exit
from psutil import Process
from argparse import ArgumentParser

import log
import cpu
from time import sleep
from pprint import pprint
from config import read_profiles, read_config

argparser = ArgumentParser(description='Automatic CPU power configuration control.')
argparser.add_argument('-d', '--debug', action='store_true',
                       help="display runtime info")
argparser.add_argument('-i', '--info', action='store_true', help='show system info')
argparser.add_argument('-p', '--profile', default='', help='activate a given profile')
argparser.add_argument('-l', '--list', action='store_true', help='list configured profiles')

ARGS = argparser.parse_args()


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

def debug_runtime_info(process, profile, sleep_time):
    cpuauto_util, cpuauto_mem = cpu.read_process_cpu_mem(process)
    charging_state = cpu.read_charging_state()
    if charging_state:
        time_iter = profile.ac_pollingperiod - sleep_time*1000
    else:
        time_iter = profile.bat_pollingperiod - sleep_time*1000
    print('Profile:', profile.name,
          '\nCharging:', charging_state,
          '\nPower:', f'{cpu.read_power_draw():.2f}W',
          '\nTemperature:', f'{cpu.read_temperature()}°C',
          '\nCPU Utilization %:', cpu.read_cpu_utilization('avg'),
          f'\nProcess resources: CPU {cpuauto_util:.2f}%, Memory {cpuauto_mem:.2f}%, Time {time_iter:.3f}ms\n')

def single_activation(profile):
    profiles = read_profiles()
    if profile in profiles:
        profiles[ARGS.profile].apply()
        print(profiles[ARGS.profile])
        exit(0)
    else:
        log.log_error(f'Profile "{ARGS.profile}" not found in config file.')

def main_loop():
    process = Process()
    profiles = read_profiles()
    profiles_sorted = sorted(profiles.values())
    while True:
        # Get profile and apply
        profile = get_triggered_profile(profiles, profiles_sorted)
        sleep_time = profile.apply()

        if ARGS.debug:
            debug_runtime_info(process, profile, sleep_time)

        if sleep_time > 0:
            sleep(sleep_time)


if __name__ == '__main__':
    if not cpu.is_root():
        log.log_error('Must be run with root provileges.')

    if ARGS.info:
        print(cpu.SYSTEM_INFO)
        exit(0)
    elif ARGS.list:
        pprint(read_config())
        exit(0)

    if ARGS.profile:
        single_activation(ARGS.profile)
    else:
        main_loop()

    # Sorted by priority
    # TRIGGER_PROCS = { cpuprofile.triggerapps for cpuprofile in PROFILES_SORTED}
