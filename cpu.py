#!/usr/bin/python3

import psutil
import subprocess
from os import getuid
from pathlib import Path
from pprint import pprint
from log import log_warning, log_error

# PATHS
POWER_DIR = '/sys/class/power_supply/'
SYSTEM_DIR = '/sys/devices/system/'

# Interface
PIPE = subprocess.PIPE

def shell(command: str, return_stdout: bool = True) -> str:
    shell_subprocess = subprocess.run(command, stdout=PIPE, shell=True)
    if return_stdout:
        return shell_subprocess.stdout.decode('utf-8')

def check_root_privileges():
    if getuid() != 0:
        log_error('This software must run with root privileges.')

def read_datafile(path: str, dtype=str):
    '''Reads first line of a file, strips and converts to dtype.'''
    with open(path, "r") as file:
        data = file.readline().strip()
    return dtype(data)


# Scaling driver

# Hardware : intel_pstate
# Kernel (cpufreq) : intel_cpufreq, acpi-cpufreq, speedstep-lib, powernow-k8, pcc-cpufreq, p4-clockmod
scaling_driver_data = read_datafile(SYSTEM_DIR + 'cpu/cpufreq/policy0/scaling_driver').lower()
if scaling_driver_data == 'intel_pstate':
    SCALING_DRIVER = 'intel_pstate'
else:
    SCALING_DRIVER = 'cpufreq'


# Turbo

# https://www.kernel.org/doc/Documentation/cpu-freq/boost.txt
turbo_pstate = Path(SYSTEM_DIR + 'cpu/intel_pstate/no_turbo')
turbo_cpufreq = Path(SYSTEM_DIR + 'cpu/cpufreq/boost')
turbo_amd_legacy = Path(SYSTEM_DIR + 'cpu0/cpufreq/cpb')

# Set TURBO_FILE, TURBO_INVERSE and TURBO_ALLOWED
if turbo_pstate.exists():
    TURBO_FILE = turbo_pstate
    TURBO_INVERSE = True
elif turbo_cpufreq.exists():
    TURBO_FILE = turbo_cpufreq
    TURBO_INVERSE = False
elif turbo_amd_legacy.exists():
    TURBO_FILE = turbo_amd_legacy
    TURBO_INVERSE = False
else:
    TURBO_FILE = None
    log_warning('Turbo boost is not available.')

if TURBO_FILE is not None:
    # Test if writing to TURBO_FILE is possible
    try:
        turbo_file_contents = TURBO_FILE.read_text()
        TURBO_FILE.write_text(turbo_file_contents)
    except PermissionError:
        log_warning('Turbo (boost/core) is disabled on BIOS or not available.')
        TURBO_ALLOWED = False
    else:
        TURBO_ALLOWED = True

# SYSTEM

def read_procs() -> set:
    return set(shell("grep -h . /proc/*/comm").splitlines())  # 2000 : 17.95s

def read_charging_state() -> bool:
    ''' Is battery charging? Deals with unavailable bat OR ac-adapter info.'''

    # AC adapter states: 0, 1, unknown
    ac_data = shell(f"grep . -h {POWER_DIR}A*/online")
    if '1' in ac_data:
        # at least one online ac adapter
        return True
    elif '0' in ac_data:
        # at least one offline ac adapter
        ac_state = False
    else:
        # Unknown ac state
        ac_state = None

    # Possible values: Charging, Discharging, Unknown
    battery_data = shell(f"grep . {POWER_DIR}BAT*/status")

    # need to explicitly check for each state in this order
    # considering multiple batteries
    if "Discharging" in battery_data:
        battery_state = False
    elif "Charging" in battery_data:
        return True
    else:
        battery_state = None

    # At this point both ac and bat state can only be False or None
    if False in [ac_state, battery_state]:
        return False
    else:
        # both ac-adapter and battery states are unknown charging == True
        # Desktop computers should fall in this case
        return True


def read_power_draw() -> bool:
    '''Calculates power draw from battery current and voltage reporting.'''
    # This implementation assumes a single BATX directory, might have to revisit
    current = float(shell(f"grep . {POWER_DIR}BAT*/current_now")) / 10**6
    voltage = float(shell(f"grep . {POWER_DIR}BAT*/voltage_now")) / 10**6
    return current * voltage


# CPU

def cpu_ranges_to_list(cpu_ranges: str) -> list:
    '''Parses virtual cpu's (offline,online,present) files formatting '''
    cpus = []
    for cpu_range in cpu_ranges:
        if '-' in cpu_range:
            start, end = cpu_range.split('-')
            cpus.extend(list(range(int(start), int(end)+1)))
        else:
            cpus.append(int(cpu_range))
    return cpus

def list_cores(status='present') -> list:
    assert status in ['offline', 'online', 'present']
    cpu_ranges = read_datafile(SYSTEM_DIR + f'cpu/{status}').split(',')
    return cpu_ranges_to_list(cpu_ranges)

def read_process_cpu_mem(process):
    return process.cpu_percent(), process.memory_percent()

def read_cpu_utilization(mode='max'):
    '''
    CPU utilization
    mode : str =  ['avg', 'max', 'all']
    for mode in ['avg', 'max']
        returns : float, in range [0.0-100.0]
    for mode == 'all':
        returns dict of floats with cpu_id:utilization pairs
    '''
    if mode == 'avg':
        return psutil.cpu_percent()
    elif mode == 'max':
        return max(psutil.cpu_percent(percpu=True))
    elif mode == 'all':
        # Get online cores and return a dict from cpu_percent(percpu=True)
        cores_online = list_cores('online')
        percpu_utilization = psutil.cpu_percent(percpu=True)
        return dict(zip(cores_online, percpu_utilization))

def read_turbo_state():
    '''Read existing turbo file and invert value if appropriate (intel_pstate/no_turbo).'''
    if TURBO_FILE is None:
        return None
    else:
        return bool(int(TURBO_FILE.read_text())) ^ TURBO_INVERSE

def read_temperature() -> float:
    temperature_sensors = psutil.sensors_temperatures()
    allowed_sensors = ['coretemp', 'k10temp', 'zenpower', 'acpitz']

    for sensor in allowed_sensors:
        if sensor not in temperature_sensors:
            continue
        return temperature_sensors[sensor][0].current
    else:
        msg = ("Couldn't detect a known CPU temperature sensor."
               f"\n\tKnown CPU temp sensors are: {allowed_sensors}"
               f"\n\tDetected sensors were: {temperature_sensors.keys()}"
               "\n\tPlease open an issue at https://www.github.org/haptein/cpuauto")
        log_warning(msg)
        return -1

def read_crit_temp() -> int:
    core_temp = psutil.sensors_temperatures()

    # the order in this list embodies priority
    cpu_temp_names = ['coretemp', 'k10temp', 'zenpower', 'acpitz']

    for name in cpu_temp_names:
        if name in core_temp:
            return int(core_temp[name][0].critical)
    else:
        # If no crit temp found default to 100
        return 100

def read_cpu_info() -> dict:
    '''Reads cpufreq data from filesystem, returns dict'''

    cpudir = SYSTEM_DIR + 'cpu/cpu0/cpufreq/'

    return dict(
        name=shell('grep model\ name /proc/cpuinfo').split(':')[-1].strip(),
        core_count=len(list_cores()),
        crit_temp=read_crit_temp(),
        minfreq=read_datafile(cpudir+'cpuinfo_min_freq', dtype=int),
        maxfreq=read_datafile(cpudir+'cpuinfo_max_freq', dtype=int),
        governors=read_datafile(cpudir+'scaling_available_governors').split(' '),
        policies=read_datafile(cpudir+'energy_performance_available_preferences').split(' ')
    )


# CPU CONTROL

def set_governor():
    raise NotImplementedError

def set_policy():
    raise NotImplementedError

def set_freq_range():
    raise NotImplementedError

def set_perf_range():
    raise NotImplementedError

def set_turbo():
    raise NotImplementedError

def set_cores_online():
    # chcpu
    raise NotImplementedError


# main
if __name__ == '__main__':
    pprint(read_cpu_info())
