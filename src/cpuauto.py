#!/usr/bin/python3
from sys import exit
from time import time
from argparse import ArgumentParser, SUPPRESS
from psutil import Process

import log
import cpu
import info
import shell
from config import read_profiles
from process import ProcessReader

argparser = ArgumentParser(description='Automatic CPU power configuration control.')
argparser.add_argument('-l', '--list', action='store_true', help='list profiles and exit')
argparser.add_argument('-s', '--status', action='store_true', help="display system status periodically")
argparser.add_argument('-p', '--profile', default='', help='activate the specified profile and exit')
argparser.add_argument('-r', '--reload', action='store_true', help='enable config file hot-reloading')
argparser.add_argument('-b', '--benchmark', action='store_true', help='stresses CPU and records power/performance metrics to a csv file')
argparser.add_argument('--daemon', action='store_true', help='install and enable cpuauto as a daemon (systemd)')
argparser.add_argument('--log', action='store_true', help='print daemon log.')
argparser.add_argument('--uninstall', action='store_true', help='uninstall program')
argparser.add_argument('-v', '--version', action='store_true', help='show program version and exit')
argparser.add_argument('-d', '--debug', action='store_true', help=SUPPRESS)
argparser.add_argument('--log-level-info', action='store_true', help=SUPPRESS)
ARGS = argparser.parse_args()


def single_activation(profile):
    profiles = read_profiles()
    if profile in profiles:
        profiles[ARGS.profile].apply()
        if ARGS.status:
            info.show_system_status(profiles[ARGS.profile], monitor_mode=True)
        else:
            print(f'Profile {profile} active.')
    else:
        log.log_error(f'Profile "{ARGS.profile}" not found in config file.')

def main_loop(monitor_mode):
    profiles = read_profiles()
    process_reader = ProcessReader(profiles)

    if ARGS.debug:
        process = Process()

    while True:
        iteration_start = time()

        if ARGS.reload:
            profiles = read_profiles()
            process_reader.update_triggerapps(profiles)

        # Get profile and apply
        profile = process_reader.triggered_profile(profiles)
        if not monitor_mode:
            profile.apply()

        # Everything else
        if ARGS.status:
            info.show_system_status(profile, monitor_mode)
        if ARGS.debug:
            info.debug_runtime_info(process, profile, iteration_start)

        # Then sleep needed time
        profile.sleep(iteration_start=iteration_start)


if __name__ == '__main__':
    # Stuff that doesn't need root

    # List profiles and exit
    if ARGS.list:
        profiles = read_profiles()
        for name in profiles:
            print(name)
        exit(0)

    # Version
    if ARGS.version:
        print(info.VERSION)
        exit(0)

    if ARGS.log:
        log.print_log()
        exit(0)

    # Stuff that needs root
    if not cpu.is_root():
        log.log_error('Must be run with root provileges.')

    if ARGS.uninstall:
        shell.uninstall()
        exit(0)

    if ARGS.daemon:
        shell.enable_daemon()
        exit(0)

    # Check if cpuauto is already running
    if shell.process_already_running():
        # Monitor mode
        if ARGS.status:
            monitor_mode = True
        elif ARGS.profile:
            # Profile will be overriden
            log.log_warning('Single profile activation will get overwritten by the already running instance.')
        else:
            log.log_error('An instance of cpuauto is already running. '
                          'You can still monitor system status with: cpuauto --status.')
    else:
        monitor_mode = False

    # Activate profile and exit
    if ARGS.profile:
        single_activation(ARGS.profile)
        exit(0)

    # Debug info
    if ARGS.debug:
        print(info.SYSTEM_INFO)
        info.debug_power_info()

    # benchmark
    if ARGS.benchmark:
        # Note: still need to add arguments to cli
        info.profile_system([1, 1, 1])
        exit(0)

    try:
        main_loop(monitor_mode)
    except KeyboardInterrupt:
        exit(0)
