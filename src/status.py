import platform
import subprocess
from time import time
from datetime import datetime

import psutil

import cpu
import powersupply
from cpu import CPU, RAPL
from __init__ import __version__

# Information display

TEMP_SENSORS = ', '.join(list(psutil.sensors_temperatures()))

SYSTEM_INFO = f'''
    System
    OS:\t\t\t{platform.platform()}
    powerplan:\t\t{__version__} running on Python{platform.python_version()} with psutil{psutil.__version__}
    CPU model:\t\t{CPU.name}
    Core configuraton:\t{CPU.physical_cores}/{CPU.logical_cores}\
    {' '.join([f"{sib[0]}-{sib[1]}" for sib in CPU.thread_siblings])}
    Frequency range:\t{" - ".join([str(freq) for freq in (CPU.minfreq, CPU.basefreq, CPU.maxfreq) if freq])} KHz
    Driver:\t\t{CPU.driver}
    Turbo:\t\t{CPU.turbo_path}
    Governors:\t\t{', '.join(CPU.governors)}
    Policies:\t\t{', '.join(CPU.policies)}
    Temperature:\t{TEMP_SENSORS}
    AC adapter:\t\t{powersupply.AC.parent.name}
    Battery:\t\t{powersupply.BAT.parent.name}
    Power method:\t{powersupply.POWER_READING_METHOD}
'''


def show_system_status(profile, monitor_mode=False):
    '''Prints System status during runtime'''

    time_now = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    active_profile = f'{time_now}\t\tActive: {profile.name}'
    power_plan = f'Power plan: {cpu.read_governor()}/{cpu.read_policy()}'
    power_status = f'Charging: {powersupply.charging()}\t\tBattery draw: {powersupply.power_draw():.1f}W'
    if RAPL.enabled:
        power_status += f'\tPackage: {RAPL.read_power():.2f}W'

    cores_online = cpu.list_cores('online')
    num_cores_online = len(cores_online)
    # Per cpu stats
    cpus = '\t'.join(['CPU'+str(coreid) for coreid in cpu.list_cores('online')])
    utils = '\t'.join([str(util) for util in psutil.cpu_percent(percpu=True)])

    # Read current frequencies in MHz
    freq_list = cpu.read_current_freq().values()
    avg_freqs = int(sum(freq_list)/num_cores_online)
    freqs = '\t'.join([str(freq) for freq in freq_list])

    # CPU average line
    cpu_cores_turbo = '\t'.join([f'Cores online: {num_cores_online}',
                                 f"Turbo: {'enabled' if cpu.read_turbo_state() else 'disabled'}"])

    cpu_avg = '\t'.join([f"Avg. Usage: {cpu.read_cpu_utilization('avg')}%",
                         f'Avg. Freq.: {avg_freqs}MHz',
                         f'Package temp: {cpu.read_temperature()}°C'])

    monitor_mode_indicator = '[MONITOR MODE]' if monitor_mode else '[ACTIVE MODE]'
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

def print_version():
    print(f'powerplan {__version__}')

def debug_power_info():
    # POWER SUPPLY TREE
    power_supply_tree = powersupply.tree()
    [print('/'.join(info.split('/')[4:])) for info in power_supply_tree.splitlines()]
    print(f'Present temperature sensors: {list(psutil.sensors_temperatures())}')

def read_process_cpu_mem(running_process):
    return running_process.cpu_percent(), running_process.memory_percent()

def debug_runtime_info(process, profile, iteration_start):
    process_util, process_mem = read_process_cpu_mem(process)
    time_iter = (time() - iteration_start) * 1000  # ms
    print(f'Process resources: CPU {process_util:.2f}%, Memory {process_mem:.2f}%, Time {time_iter:.3f}ms')


if __name__ == '__main__':
    debug_power_info()
