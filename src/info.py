import csv
import platform
import subprocess
from datetime import datetime
from time import time, sleep
from multiprocessing import Pool

import psutil

import cpu
from cpu import CPU, RAPL

VERSION = '0.1'

# Information display

SYSTEM_INFO = f'''
    System
    OS:\t\t\t{platform.platform()}
    cpuauto:\t\t{VERSION} running on Python{platform.python_version()}
    CPU model:\t\t{CPU['name']}
    Core configuraton:\t{CPU['physical_cores']}/{len(cpu.list_cores())}\
    {' '.join([f"{sib[0]}-{sib[1]}" for sib in CPU['thread_siblings']])}
    Frequency range:\t{CPU['freq_info']}
    Driver:\t\t{CPU['scaling_driver']}
    Governors:\t\t{', '.join(CPU['governors'])}
    Policies:\t\t{', '.join(CPU['policies'])}

    Paths
    Turbo:\t\t{CPU['turbo_path']}
    AC adapter:\t\t{CPU['ac_path'].parent}
    Battery:\t\t{CPU['bat_path'].parent}
    Power method:\t{CPU['power_reading_method']}
'''


def show_system_status(profile, monitor_mode=False):
    '''Prints System status during runtime'''

    charging = cpu.read_charging_state()
    time_now = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    active_profile = f'{time_now}\t\tActive: {profile.name}'
    power_plan = f'Power plan: {cpu.read_governor()}/{cpu.read_policy()}'
    power_status = f'Charging: {charging}\t\tBattery draw: {cpu.read_power_draw():.1f}W'
    if RAPL.enabled:
        power_status += f'\tPackage: {RAPL.read_power():.2f}W'

    cores_online = cpu.list_cores('online')
    num_cores_online = len(cores_online)
    # Per cpu stats
    cpus = '\t'.join(['CPU'+str(coreid) for coreid in cpu.list_cores('online')])
    utils = '\t'.join([str(util) for util in psutil.cpu_percent(percpu=True)])

    # Read current frequencies in MHz
    freq_list = cpu.read_current_freq(divisor=1000).values()
    avg_freqs = int(sum(freq_list)/num_cores_online)
    freqs = '\t'.join([str(freq) for freq in freq_list])

    # CPU average line
    cpu_cores_turbo = '\t'.join([f'Cores online: {num_cores_online}',
                                 f"Turbo: {'enabled' if cpu.read_turbo_state() else 'disabled'}"])

    cpu_avg = '\t'.join([f"Avg. Usage: {cpu.read_cpu_utilization('avg')}%",
                         f"Avg. Freq.: {avg_freqs}MHz",
                         f'Package temp: {cpu.read_temperature()}°C'])

    monitor_mode_indicator = '[MONITOR MODE]' if monitor_mode else ''
    status_lines = ['',
                    active_profile,
                    power_plan,
                    power_status,
                    cpu_cores_turbo,
                    cpu_avg,
                    '',
                    cpus,
                    utils,
                    freqs]

    subprocess.run('clear')
    print(monitor_mode_indicator)
    print(SYSTEM_INFO)
    print('\n'.join(status_lines))


def debug_power_info():
    # POWER SUPPLY TREE
    power_supply_info = cpu.shell('grep . /sys/class/power_supply/*/* -d skip')
    [print('/'.join(info.split('/')[4:])) for info in power_supply_info.splitlines()]


