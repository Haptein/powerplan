#!/usr/bin/python3

import psutil
import subprocess
from pathlib import Path


POWER_DIR = "/sys/class/power_supply/"

# Turbo
p_state_path = Path("/sys/devices/system/cpu/intel_pstate/no_turbo")
cpufreq_path = Path("/sys/devices/system/cpu/cpufreq/boost")

# Set TURBO_FILE and TURBO_INVERSE
if p_state_path.exists():
    TURBO_FILE = p_state_path
    TURBO_INVERSE = True
elif cpufreq_path.exists():
    TURBO_FILE = cpufreq_path
    TURBO_INVERSE
else:
    TURBO_FILE = None

# Shell interface
PIPE = subprocess.PIPE

def shell_output(command: str) -> str:
    return subprocess.run(command, stdout=PIPE, shell=True).stdout.decode('utf-8')

# INPUT

def read_datafile(path: str, dtype=str):
    '''Reads first line of a file, strips and converts to dtype.'''
    with open(path, "r") as f:
        data = f.readline().strip()
    return dtype(data)

def read_procs() -> set:
    return set(shell_output("grep -h . /proc/*/comm").splitlines())  # 2000 : 17.95s

def read_charging_state() -> bool:
    ''' Is battery charging? Deals with unavailable bat OR ac-adapter info.'''

    # AC adapter states: 0, 1, unknown
    ac_data = shell_output(f"grep . -h {POWER_DIR}A*/online")
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
    battery_data = shell_output(f"grep . {POWER_DIR}BAT*/status")

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
    current = float(shell_output(f"grep . {POWER_DIR}BAT*/current_now")) / 10**6
    voltage = float(shell_output(f"grep . {POWER_DIR}BAT*/voltage_now")) / 10**6
    return current * voltage


def read_cores_online() -> list:
    '''Parses cores online from online ranges file'''

    cores_online = []
    online_ranges = read_datafile('/sys/devices/system/cpu/online').split(',')

    for online_range in online_ranges:
        if '-' in online_range:
            start, end = online_range.split('-')
            cores_online.extend(list(range(int(start), int(end)+1)))
        else:
            cores_online.append(int(online_range))
    return cores_online


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
        cores_online = read_cores_online()
        percpu_utilization = psutil.cpu_percent(percpu=True)
        return dict(zip(cores_online, percpu_utilization))


def read_turbo_state():
    '''Read existing turbo file and invert value if appropriate (intel_pstate/no_turbo).'''
    if TURBO_FILE is None:
        return None
    else:
        return bool(int(TURBO_FILE.read_text())) ^ TURBO_INVERSE


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

    cpudir = '/sys/devices/system/cpu/cpu0/cpufreq/'

    return dict(
        name=shell_output('grep model\ name /proc/cpuinfo').split(':')[-1].strip(),
        core_count=int(shell_output('grep siblings /proc/cpuinfo').split(':')[-1]),
        crittemp=read_crit_temp(),
        minfreq=read_datafile(cpudir+'cpuinfo_min_freq', dtype=int),
        maxfreq=read_datafile(cpudir+'cpuinfo_max_freq', dtype=int),
        governors=read_datafile(cpudir+'scaling_available_governors').split(' '),
        policies=read_datafile(cpudir+'energy_performance_available_preferences').split(' ')
    )


# OUTPUT

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
    cpu_info = read_cpu_info()
    for key in cpu_info:
        print(f'{key}:\t{cpu_info[key]}')