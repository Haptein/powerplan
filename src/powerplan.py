#!/usr/bin/python3
from sys import exit
from time import time
from argparse import ArgumentParser, SUPPRESS

import psutil

import log
import shell
import monitor
import process
import systemstatus
from cpu import Cpu
from __init__ import __version__
from powersupply import PowerSupply
from config import read_config, read_profiles

argparser = ArgumentParser(description='Automatic CPU power configuration control.')
argparser.add_argument('-d', '--debug', action='store_true', help=SUPPRESS)
argparser.add_argument('-l', '--list', action='store_true', help='list profiles and exit')
argparser.add_argument('-p', '--profile', default='', help='activate the specified profile and exit')
argparser.add_argument('-r', '--reload', action='store_true', help='enable config file hot-reloading')
argparser.add_argument('-s', '--status', action='store_true', help="display system status periodically")
argparser.add_argument('--daemon', action='store_true', help='install and enable as a system daemon (systemd)')
argparser.add_argument('--log', action='store_true', help='print daemon log')
argparser.add_argument('--system', action='store_true', help='show system info and exit')
argparser.add_argument('--uninstall', action='store_true', help='uninstall program')
argparser.add_argument('--verbose', action='store_true', help='print runtime info')
argparser.add_argument('--version', action='store_true', help='show program version and exit')


def single_activation(profile: str, system: systemstatus.System):
    profiles = read_profiles(system)
    if profile in profiles:
        status = systemstatus.StatusMinimal(system, profiles)
        status.update()
        profiles[profile].apply(status)
        if ARGS.status:
            monitor.show_system_status(profiles[ARGS.profile], monitor_mode=True)
        else:
            print(f'Profile {profile} active.')
    else:
        log.error(f'Profile "{ARGS.profile}" not found in config file.')

def main_loop(monitor_mode: bool, system: systemstatus.System):
    config = read_config()
    profiles = read_profiles(system)

    # --reload forces persistency
    config['persistent'] = config['persistent'] or ARGS.reload
    if config['notify'] and not log.CAN_NOTIFY:
        log.warning('libnotify was not found but notifications enabled in configuration.')
        config['notify'] = False

    # Get status object and needed fields at iteration start
    if ARGS.status:
        status = systemstatus.StatusMonitor(system, profiles)
        partials = ['time_stamp', 'ac_power', 'triggered_profile']
    else:
        status = systemstatus.StatusMinimal(system, profiles)
        partials = ['ac_power', 'triggered_profile']

    if ARGS.debug:
        running_process = psutil.Process()

    while True:
        # we need this to time the sleeps periods
        iteration_start = time()

        if ARGS.reload:  # profile hot-reloading
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
                if config['notify']:
                    log.notify('Profile [{profile.name}] active.')
            elif config['persistent']:
                profile.apply(status)

        if ARGS.status:
            # Update the rest of fields here in order to display
            # the status after the profile has been applied
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

    ARGS = argparser.parse_args()

    # uninstall goes first so if something else fails, user can still easily uninstall
    if ARGS.uninstall:
        shell.uninstall()
        exit(0)

    # Stuff that doesn't need root
    if ARGS.version:
        print(f'powerplan {__version__}')
        exit(0)

    if ARGS.log:
        log.print_log()
        exit(0)

    # Initialize system interface
    system = systemstatus.System(cpu=Cpu(), powersupply=PowerSupply())

    if ARGS.system:
        print(system.info)
        exit(0)

    # List profiles and exit
    if ARGS.list:
        profiles = read_profiles(system=system)
        for profile in profiles.values():
            print(profile.description)
        exit(0)

    # Stuff that needs root
    if not shell.is_root():
        log.error('Must be run with root provileges.')

    if ARGS.daemon:
        shell.enable_daemon()
        exit(0)

    # Check if already running and define monitor mode accordingly
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
        single_activation(ARGS.profile, system=system)
        exit(0)

    try:
        main_loop(monitor_mode, system=system)
    except KeyboardInterrupt:
        exit(0)
