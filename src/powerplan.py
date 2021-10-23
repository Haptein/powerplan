#!/usr/bin/python3
from sys import exit
from time import time
from argparse import ArgumentParser, SUPPRESS

import psutil

import log
import shell
import status
import process
import powersupply
from config import read_profiles

argparser = ArgumentParser(description='Automatic CPU power configuration control.')
argparser.add_argument('-d', '--debug', action='store_true', help=SUPPRESS)
argparser.add_argument('-l', '--list', action='store_true', help='list profiles and exit')
argparser.add_argument('-p', '--profile', default='', help='activate the specified profile and exit')
argparser.add_argument('-r', '--reload', action='store_true', help='enable config file hot-reloading')
argparser.add_argument('-s', '--status', action='store_true', help="display system status periodically")
argparser.add_argument('--daemon', action='store_true', help='install and enable as a system daemon (systemd)')
argparser.add_argument('--log', action='store_true', help='print daemon log')
argparser.add_argument('--persistent', action='store_true', help='use this if your profile is reset by your computer')
argparser.add_argument('--system', action='store_true', help='show system info and exit')
argparser.add_argument('--uninstall', action='store_true', help='uninstall program')
argparser.add_argument('--verbose', action='store_true', help='print runtime info')
argparser.add_argument('--version', action='store_true', help='show program version and exit')
ARGS = argparser.parse_args()

# --reload forces --persistent
ARGS.persistent = ARGS.persistent or ARGS.reload

def single_activation(profile: str):
    profiles = read_profiles()
    if profile in profiles:
        profiles[profile].apply(powersupply.ac_power())
        if ARGS.status:
            status.show_system_status(profiles[ARGS.profile], monitor_mode=True)
        else:
            print(f'Profile {profile} active.')
    else:
        log.error(f'Profile "{ARGS.profile}" not found in config file.')

def main_loop(monitor_mode: bool):
    profiles = read_profiles()
    process_reader = process.ProcessReader(profiles)

    if ARGS.debug:
        running_process = psutil.Process()

    # Variables used if no --persistent flag is used
    last_profile_name = None
    last_charging_state = None
    while True:
        iteration_start = time()

        if ARGS.reload:
            profiles = read_profiles()
            process_reader.reset(profiles)

        # Get profile and charging state
        profile = process_reader.triggered_profile(profiles)
        charging_state = powersupply.ac_power()

        # Profile application
        if not monitor_mode:
            if ARGS.persistent:
                profile.apply(charging_state)

            # If profile or charging state changed:
            if (profile.name != last_profile_name) or (charging_state != last_charging_state):
                # Log only on changes, even if --persistent is used (to avoid flooding journal)
                log.info(f'Applying profile: {profile.name}-{"AC" if charging_state else "Battery"}')
                if not ARGS.persistent:
                    profile.apply(charging_state)

        # Everything else
        if ARGS.status:
            status.show_system_status(profile, monitor_mode, charging_state)
        if ARGS.debug:
            status.debug_runtime_info(running_process, profile, iteration_start)

        # Update last state
        last_profile_name = profile.name
        last_charging_state = charging_state

        # Then sleep needed time
        profile.sleep(iteration_start=iteration_start, ac_power=charging_state)


if __name__ == '__main__':
    # If running at boot, wait for sysfs to itialize needed resources
    shell.wait_on_boot()

    # Stuff that doesn't need root

    # List profiles and exit
    if ARGS.list:
        profiles = read_profiles()
        for name in profiles:
            print(name)
        exit(0)

    # Version
    if ARGS.version:
        status.print_version()
        exit(0)

    if ARGS.log:
        log.print_log()
        exit(0)

    if ARGS.system:
        print(status.SYSTEM_INFO)
        exit(0)

    # Stuff that needs root
    if not shell.is_root():
        log.error('Must be run with root provileges.')

    if ARGS.uninstall:
        shell.uninstall()
        exit(0)

    if ARGS.daemon:
        shell.enable_daemon()
        exit(0)

    # Check if already running
    if process.already_running():
        # Monitor mode
        if ARGS.status:
            monitor_mode = True
        elif ARGS.profile:
            # Profile will be overriden
            log.warning('Single profile activation will get overwritten by the already running instance.')
        else:
            log.error('An instance is already running. '
                      'You can monitor system status with: powerplan --status.')
    else:
        monitor_mode = False

    # Activate profile and exit
    if ARGS.profile:
        single_activation(ARGS.profile)
        exit(0)

    # Debug info
    if ARGS.debug:
        status.debug_power_info()

    try:
        main_loop(monitor_mode)
    except KeyboardInterrupt:
        exit(0)
