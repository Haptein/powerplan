#!/usr/bin/python3

import psutil
import subprocess
from os import getuid
from pathlib import Path
from log import log_warning, log_error

'''
File structure:
PATHS
INTERFACE
SYSTEM
CPU INPUT
CPU OUTPUT
CPU
'''

# PATHS
POWER_DIR = '/sys/class/power_supply/'
SYSTEM_DIR = '/sys/devices/system/'
CPU_DIR = SYSTEM_DIR + 'cpu/'
CPUFREQ_DIR = CPU_DIR + 'cpu0/cpufreq/'

# Interface
PIPE = subprocess.PIPE

def shell(command: str, return_stdout: bool = True) -> str:
    shell_subprocess = subprocess.run(command, stdout=PIPE, shell=True)
    if return_stdout:
        return shell_subprocess.stdout.decode('utf-8')

def is_root():
    return getuid() == 0

def read_datafile(path: str, dtype=str):
    '''Reads first line of a file, strips and converts to dtype.'''
    with open(path, "r") as file:
        data = file.readline().strip()
    return dtype(data)


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

    # Possible values: "Unknown", "Charging", "Discharging", "Not charging", "Full"
    battery_data = shell(f"grep . -h {POWER_DIR}BAT*/status")

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
    # On some systems power_now isn't available
    power_data = shell(f"grep . {POWER_DIR}BAT*/power_now")
    if power_data:
        return float(power_data) / 10**6
    else:
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
    cpu_ranges = read_datafile(CPU_DIR + status)
    if not cpu_ranges:
        return []
    else:
        return cpu_ranges_to_list(cpu_ranges.split(','))

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


# CPU CONTROL
def read_governor(core_id: int = 0) -> str:
    return read_datafile(CPU_DIR + f'cpu{core_id}/cpufreq/scaling_governor')

def set_governor(governor):
    assert governor in CPU['governors']
    if read_governor() != governor:
        for core_id in list_cores('online'):
            Path(CPU_DIR + f'cpu{core_id}/cpufreq/scaling_governor').write_text(governor)

def read_policy(core_id: int = 0) -> str:
    return read_datafile(CPU_DIR + f'cpu{core_id}/cpufreq/energy_performance_preference')

def set_policy(policy):
    assert policy in CPU['policies']
    if policy != read_policy():
        for core_id in list_cores('online'):
            Path(CPU_DIR + f'cpu{core_id}/cpufreq/energy_performance_preference').write_text(policy)

def read_freq_range(core_id: int = 0) -> list:
    scaling_min_freq = read_datafile(CPU_DIR + f'cpu{core_id}/cpufreq/scaling_min_freq', int)
    scaling_max_freq = read_datafile(CPU_DIR + f'cpu{core_id}/cpufreq/scaling_max_freq', int)
    return [scaling_min_freq, scaling_max_freq]

def set_freq_range(min_freq: int, max_freq: int):
    # Preferred for cpufreq
    assert min_freq <= max_freq
    # Write new freq values if different from current
    current_freq_range = read_freq_range()
    for core_id in list_cores('online'):
        if min_freq != current_freq_range[0]:
            Path(CPU_DIR + f'cpu{core_id}/cpufreq/scaling_min_freq').write_text(str(min_freq))
        if max_freq != current_freq_range[1]:
            Path(CPU_DIR + f'cpu{core_id}/cpufreq/scaling_max_freq').write_text(str(max_freq))

def read_perf_range() -> list:
    min_perf_pct = int(CPU['min_perf_pct_path'].read_text())
    max_perf_pct = int(CPU['max_perf_pct_path'].read_text())
    return [min_perf_pct, max_perf_pct]

def set_perf_range(min_perf_pct: int, max_perf_pct: int):
    # This setting only exists for intel_pstate
    assert max_perf_pct >= min_perf_pct
    if CPU['scaling_driver'] == 'intel_pstate':
        current_perf_range = read_perf_range()
        if min_perf_pct != current_perf_range[0]:
            CPU['min_perf_pct_path'].write_text(str(min_perf_pct))
        if max_perf_pct != current_perf_range[1]:
            CPU['max_perf_pct_path'].write_text(str(max_perf_pct))

def read_turbo_state():
    '''Read existing turbo file and invert value if appropriate (intel_pstate/no_turbo).'''
    if CPU['turbo_path'] is None:
        return None
    else:
        return bool(int(CPU['turbo_path'].read_text())) ^ CPU['turbo_inverse']

def set_turbo_state(turbo_state: bool):
    if CPU['turbo_allowed'] and (turbo_state != read_turbo_state()):
        CPU['turbo_path'].write_text(str(int(turbo_state ^ CPU['turbo_inverse'])))

def set_all_cores_online():
    # Needed to initialize CPU properly
    for core_id in list_cores('present'):
        core_id_online_path = Path(CPU_DIR + f'cpu{core_id}/online')
        if core_id_online_path.exists():
            core_id_online_path.write_text('1')

def read_physical_core_status(core_num: int) -> bool:
    assert 0 <= core_num and core_num <= CPU['physical_cores']-1
    core_ids = CPU['thread_siblings'][core_num]
    # Can't (and shouldn't) turn off core 0
    if 0 in core_ids:
        return True
    else:
        # Just test the first one,
        # not expecting a case where other processes turn off cores
        return bool(read_datafile(CPU_DIR + f'cpu{core_ids[0]}/online', int))

def set_physical_cores_online(num_cores: int):
    '''Sets the number of online physical cores, turns off the rest'''
    assert 0 < num_cores and num_cores <= CPU['physical_cores']
    # Iterate over physical core_num and virtual core siblings
    for core_num, core_ids in enumerate(CPU['thread_siblings']):
        core_online = read_physical_core_status(core_num)
        # not <= bc core_num starts from zero
        if core_num < num_cores:
            # Set to Online
            if not core_online:
                for core_id in core_ids:
                    Path(CPU_DIR + f'cpu{core_id}/online').write_text('1')
        else:
            # Set to offline
            if core_online:
                for core_id in core_ids:
                    Path(CPU_DIR + f'cpu{core_id}/online').write_text('0')


# CPU: dict, stores all cpu_specs / Path_objs (except for individual core ones)

# Setting all cores online is needed for accurate physical/logical/sibling info retrival

if is_root():
    set_all_cores_online()
else:
    if list_cores('offline'):
        log_error('Root privileges needed. CPU topology can\'t be read properly since there are offline cores.')
    log_warning('Root privileges needed. Can\'t tell if turbo is available.')

CPU = dict(
    name=shell('grep model\ name /proc/cpuinfo').split(':')[-1].strip(),
    logical_cores=len(list_cores()),
    crit_temp=read_crit_temp(),
    minfreq=read_datafile(CPUFREQ_DIR + 'cpuinfo_min_freq', dtype=int),
    maxfreq=read_datafile(CPUFREQ_DIR + 'cpuinfo_max_freq', dtype=int),
    governors=read_datafile(CPUFREQ_DIR + 'scaling_available_governors').split(' '),
    policies=read_datafile(CPUFREQ_DIR + 'energy_performance_available_preferences').split(' ')
)

# scaling driver
# Hardware : intel_pstate
# Kernel (cpufreq) : intel_cpufreq, acpi-cpufreq, speedstep-lib, powernow-k8, pcc-cpufreq, p4-clockmod
scaling_driver_data = read_datafile(CPU_DIR + 'cpufreq/policy0/scaling_driver').lower()
if scaling_driver_data == 'intel_pstate':
    CPU['scaling_driver'] = 'intel_pstate'
    CPU['min_perf_pct_path'] = Path(CPU_DIR + 'intel_pstate/min_perf_pct')
    CPU['max_perf_pct_path'] = Path(CPU_DIR + 'intel_pstate/max_perf_pct')
else:
    CPU['scaling_driver'] = 'cpufreq'

# turbo_allowed, turbo_file, turbo_inverse
# https://www.kernel.org/doc/Documentation/cpu-freq/boost.txt
turbo_pstate = Path(CPU_DIR + 'intel_pstate/no_turbo')
turbo_cpufreq = Path(CPU_DIR + 'cpufreq/boost')
turbo_amd_legacy = Path(SYSTEM_DIR + 'cpu0/cpufreq/cpb')

if turbo_pstate.exists():
    CPU['turbo_path'] = turbo_pstate
    CPU['turbo_inverse'] = True
elif turbo_cpufreq.exists():
    CPU['turbo_path'] = turbo_cpufreq
    CPU['turbo_inverse'] = False
elif turbo_amd_legacy.exists():
    CPU['turbo_path'] = turbo_amd_legacy
    CPU['turbo_inverse'] = False
else:
    CPU['turbo_path'] = None
    log_warning('Turbo boost is not available.')

if CPU['turbo_path'] is not None:
    # Test if writing to CPU['turbo_path'] is possible
    try:
        turbo_file_contents = CPU['turbo_path'].read_text()
        CPU['turbo_path'].write_text(turbo_file_contents)
    except PermissionError:
        log_warning('Turbo (boost/core) is disabled on BIOS or not available.')
        CPU['turbo_allowed'] = False
    else:
        CPU['turbo_allowed'] = True

# Physical core / Thread sibling detection#set_cores_online()
siblings_set = set()
# Read thread_siblings_list for each virtual cpu
for core_id in list_cores():
    thread_siblings_list = Path(f'{CPU_DIR}cpu{core_id}/topology/thread_siblings_list')
    # File won't exist if cpu is offline
    if thread_siblings_list.exists():
        # add sibling pair to a set
        thread_siblings = thread_siblings_list.read_text().strip().split(',')
        siblings = tuple(int(ths) for ths in thread_siblings)
        siblings_set.add(siblings)
CPU['thread_siblings'] = sorted(siblings_set)
CPU['physical_cores'] = len(siblings_set)


def display_cpu_info():
    keys = 'name,physical_cores,logical_cores,thread_siblings,minfreq,maxfreq,' + \
           'scaling_driver,turbo_allowed,turbo_path,governors,policies'
    for key in keys.split(','):
        print(key, ':', CPU[key])


def debug_info():
    # POWER SUPPLY TREE
    power_supply_info = shell('grep . /sys/class/power_supply/*/*')
    [print('/'.join(info.split('/')[4:])) for info in power_supply_info.splitlines()]

# main
if __name__ == '__main__':
    display_cpu_info()
    debug_info()
