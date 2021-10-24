#!/usr/bin/python3
from sys import exit
from time import time
from argparse import ArgumentParser, SUPPRESS

import psutil

import log
import shell
import monitor
import process
from __init__ import __version__
from config import read_profiles
from cpu import Cpu
from powersupply import PowerSupply
from system import System, MonitorSystemStatus, DaemonSystemStatus

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

def single_activation(profile: str, system: System):
    profiles = read_profiles(system)
    if profile in profiles:
        profiles[profile].apply(system.powersupply.ac_power())
        if ARGS.status:
            monitor.show_system_status(profiles[ARGS.profile], monitor_mode=True)
        else:
            print(f'Profile {profile} active.')
    else:
        log.error(f'Profile "{ARGS.profile}" not found in config file.')

def main_loop(monitor_mode: bool, system: System):
    profiles = read_profiles(system)

    if ARGS.status:
        status = MonitorSystemStatus(system, profiles)
        partials = ['time_stamp', 'ac_power', 'triggered_profile']
    else:
        status = DaemonSystemStatus(system, profiles)
        partials = ['ac_power', 'triggered_profile']

    if ARGS.debug:
        running_process = psutil.Process()

    while True:
        iteration_start = time()

        if ARGS.reload:
            profiles = read_profiles(system)
            status.reset()

        status.partial_update(partials)

        # Profile application
        profile = status['triggered_profile']
        if not monitor_mode:
            if status.changed(['ac_power', 'triggered_profile']):
                # Log only on changes, even if --persistent is used (to avoid flooding journal)
                log.info(f'Applying profile: {profile.name}-{"AC" if status["ac_power"] else "Battery"}')
                profile.apply(status)
            elif ARGS.persistent:
                profile.apply(status)

        # Everything else
        if ARGS.status:
            # Update the rest of fields
            status.partial_update()
            monitor.show_system_status(system, status, monitor_mode)
        if ARGS.debug:
            monitor.debug_runtime_info(running_process, profile, iteration_start)

        # Then sleep needed time
        profile.sleep(iteration_start=iteration_start, status=status)


if __name__ == '__main__':
    # If running at boot, wait for sysfs to itialize needed resources
    shell.wait_on_boot()
    log.info(f'powerplan: v{__version__}')

    # Stuff that doesn't need root

    if ARGS.version:
        print(f'powerplan {__version__}')
        exit(0)

    if ARGS.log:
        log.print_log()
        exit(0)

    # Prepare system interface
    system = System(cpu=Cpu(), powersupply=PowerSupply())

    # List profiles and exit
    if ARGS.list:
        profiles = read_profiles(system=system)
        for name in profiles:
            print(name)
        exit(0)

    if ARGS.system:
        print(system.info)
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

    try:
        main_loop(monitor_mode, system=system)
    except KeyboardInterrupt:
        exit(0)
