#!/usr/bin/python3
import sys
import time
from pathlib import Path

import psutil

import log
from shell import shell, is_root, read, path_is_writable

'''
File structure:
PATHS
CPUSpec
RAPL
CPU INPUT
CPU OUTPUT
'''

# PATHS
SYSTEM_DIR = '/sys/devices/system/'
CPU_DIR = SYSTEM_DIR + 'cpu/'
CPUFREQ_DIR = CPU_DIR + 'cpu0/cpufreq/'


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

def list_cores(status: str = 'present') -> list:
    """list coreid's with status: offline, online, present"""
    assert status in ['offline', 'online', 'present']
    cpu_ranges = read(CPU_DIR + status)
    if not cpu_ranges:
        return []
    else:
        return cpu_ranges_to_list(cpu_ranges.split(','))

def set_core_status(core_list: list, online: int):
    # Needed to initialize CPU properly
    assert online in [0, 1]
    online = str(online)
    for core_id in core_list:
        core_id_online_path = Path(CPU_DIR + f'cpu{core_id}/online')
        if core_id_online_path.exists():
            core_id_online_path.write_text(online)


class CPUSpecification:
    ''' Stores all static CPU attributes and paths (that vary between models and drivers) '''

    def __init__(self):
        # Check and warn if there are offline cores (when without root privilege and --system argument)
        cores_offline = list_cores('offline')
        if cores_offline:
            log.info('Offline cores detected: ' + read(CPU_DIR + 'offline'))
            if is_root():
                log.info('Setting all cores online to enable correct topology detection.')
                set_core_status(list_cores('present'), online=1)
            elif '--system' in sys.argv:
                log.warning("CPU topology can't be correctly read (without root privileges)"
                            ', since there are offline cores.')

        # Model
        self.name = shell('grep "model name" /proc/cpuinfo').split(':')[-1].strip()
        # Topology
        self.thread_siblings = self._thread_siblings()
        self.physical_cores = len(self.thread_siblings)
        self.logical_cores = len(list_cores())
        # Reset core status
        if cores_offline and is_root():
            log.info('Setting cores back to initial offline status.')
            set_core_status(cores_offline, online=0)

        # Limits
        self.minfreq = read(CPUFREQ_DIR + 'cpuinfo_min_freq', dtype=int)
        self.maxfreq = read(CPUFREQ_DIR + 'cpuinfo_max_freq', dtype=int)
        self.temp_sensor = self._available_temp_sensor()
        self.crit_temp = int(psutil.sensors_temperatures()[self.temp_sensor][0].critical)
        self._set_turbo_variables()

        # governors / policies
        self.governors = read(CPUFREQ_DIR + 'scaling_available_governors').split(' ')
        epp_available = Path(CPUFREQ_DIR + 'energy_performance_available_preferences')
        if epp_available.exists():
            self.policies = read(epp_available).split(' ')
        else:
            self.policies = []

        '''
        Scaling driver
        Hardware : intel_pstate
        Kernel (cpufreq) : intel_cpufreq, acpi-cpufreq, speedstep-lib, powernow-k8, pcc-cpufreq, p4-clockmod
        '''

        driver = read(CPU_DIR + 'cpufreq/policy0/scaling_driver').lower()
        if driver == 'intel_pstate':
            self.driver = driver
            self.basefreq = read(CPUFREQ_DIR + 'base_frequency', dtype=int)
            self.min_perf_pct = Path(CPU_DIR + 'intel_pstate/min_perf_pct')
            self.max_perf_pct = Path(CPU_DIR + 'intel_pstate/max_perf_pct')
            # here goes stuff unavailable with intel-pstate
        else:
            self.driver = 'cpufreq'
            # stuff unavailable in cpufreq drivers
            self.basefreq = ''

        # Lastly generate some system info strings

        # all cpufreq drivers are treated the same, driver_repr differentiates them in logs/status
        self.driver_repr = driver

        # sibling_cores_repr
        sibling_group_list = []
        for sibling_group in self.thread_siblings:
            sibling_group_list.append('-'.join(map(str, sibling_group)))
        self.sibling_cores_repr = ' '.join(sibling_group_list)

        # temp_sensor_repr
        temp_sensor_list = list(psutil.sensors_temperatures())
        if self.temp_sensor:
            # Mark used temp sensor with an *
            used_sensor = temp_sensor_list.index(self.temp_sensor)
            temp_sensor_list[used_sensor] = '*' + temp_sensor_list[used_sensor]
        self.temp_sensor_repr = ', '.join(temp_sensor_list)

        # freq_range_repr
        freqs = [str(freq) for freq in (self.minfreq, self.basefreq, self.maxfreq) if freq]
        self.freq_range_repr = " - ".join(freqs)

        # governors_repr, policies_repr
        self.governors_repr = ", ".join(self.governors)
        self.policies_repr = ', '.join(self.policies)
        log.info(f'Available governors: {self.governors_repr}')
        if self.policies:
            log.info(f'Available policies: {self.policies_repr}')

    def _thread_siblings(self) -> list:
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
        return sorted(siblings_set)

    def _available_temp_sensor(self):
        '''Returns first available sensor in allowed_sensors, or None '''
        temperature_sensors = psutil.sensors_temperatures()
        # the order in this list embodies lookup priority
        allowed_sensors = ['coretemp', 'k10temp', 'zenpower', 'acpitz', 'thinkpad']
        for sensor in allowed_sensors:
            if sensor in temperature_sensors:
                return sensor
        else:
            msg = ("Couldn't detect a known CPU temperature sensor."
                   f"\n\tKnown CPU temp sensors are: {allowed_sensors}"
                   f"\n\tDetected sensors were: {temperature_sensors}"
                   "\n\tPlease open an issue at https://www.github.org/haptein/powerplan")
            log.warning(msg)
            return None

    def _set_turbo_variables(self):
        '''Sets: turbo_allowed, turbo_file, turbo_inverse'''
        #  https://www.kernel.org/doc/Documentation/cpu-freq/boost.txt
        turbo_pstate = Path(CPU_DIR + 'intel_pstate/no_turbo')
        turbo_cpufreq = Path(CPU_DIR + 'cpufreq/boost')
        turbo_amd_legacy = Path(CPUFREQ_DIR + 'cpb')

        if turbo_pstate.exists():
            turbo_path = turbo_pstate
            turbo_inverse = True
        elif turbo_cpufreq.exists():
            turbo_path = turbo_cpufreq
            turbo_inverse = False
        elif turbo_amd_legacy.exists():
            turbo_path = turbo_amd_legacy
            turbo_inverse = False
        else:
            turbo_path = None
            turbo_allowed = None
            log.info('Turbo boost is not available.')

        if turbo_path is not None:
            turbo_allowed = path_is_writable(turbo_path)
            if not turbo_allowed and is_root():
                log.info('Turbo (boost/core) is disabled on BIOS or not available.')

        self.turbo_path = turbo_path
        self.turbo_inverse = turbo_inverse
        self.turbo_allowed = turbo_allowed

# Rapl
class RaplLayer:
    def __init__(self, layer_path: Path):
        # Assumes name, enabled, energy_uj and max_energy_range_uj exist
        self.name = read(layer_path/'name')
        self.enabled = read(layer_path/'enabled', int)
        self.max_energy_range_uj = read(layer_path/'max_energy_range_uj', int)
        self.energy_uj_path = layer_path/'energy_uj'
        # Initialize reading
        self.last_time, self.last_energy = self.read_time_energy()
        log.info(f'IntelRapl layer initialized: {self.name}')

    def read_time_energy(self):
        return time.time(), read(self.energy_uj_path, int)

    def read_power(self):
        # Read
        current_time, current_energy = self.read_time_energy()

        # Compute
        energy_delta = current_energy - self.last_energy
        time_delta = current_time - self.last_time

        # Max energy range correction
        if current_energy < self.last_energy:
            # Energy counter overflowed
            energy_delta += self.max_energy_range_uj
            log.info(f'energy range overflow detected for intel-rapl layer:{self.name}.'
                     f'time delta:{time_delta}, e_i:{current_energy}, e_i-1:{self.last_energy}'
                     f'energy delta:{energy_delta}')

        current_power = energy_delta / time_delta / 10**6  # in Watt

        # Update
        self.last_energy = current_energy
        self.last_time = current_time

        return current_power


class IntelRapl:
    def __init__(self):
        '''If exists and enabled, create RaplLayer objs for each layer found.'''
        enabled_path = Path('/sys/class/powercap/intel-rapl/enabled')
        if enabled_path.exists() and is_root():
            self.enabled = read(enabled_path, bool)
        else:
            self.enabled = False

        if self.enabled:
            log.info('IntelRapl is enabled.')
        else:
            log.info('IntelRapl is unavailable.')
            return

        # If reached this point rapl exists and is enabled
        self.layers = dict()
        layer_paths = Path('/sys/class/powercap/').glob('intel-rapl:*')
        for layer_path in layer_paths:
            layer = RaplLayer(layer_path)
            self.layers[layer.name] = layer

    def read_power(self, name: str = 'package-0'):
        if self.enabled and name in self.layers:
            return self.layers[name].read_power()
        else:
            return None

class Cpu:
    '''
    Cpu configuration I/O
    Contains:
    spec, CpuSpecification
    rapl, RAPL interface
    a bunch of I/O methods
    '''
    def __init__(self):
        self.spec = CPUSpecification()
        self.rapl = self.get_rapl()

    # CPU STATUS
    def list_cores(self, status: str = 'present') -> list:
        """list coreid's with status: offline, online, present"""
        return list_cores(status)

    def read_physical_core_status(self, core_num: int) -> bool:
        assert 0 <= core_num and core_num <= self.spec.physical_cores - 1
        core_ids = self.spec.thread_siblings[core_num]
        # Can't (and shouldn't) turn off core 0
        if 0 in core_ids:
            return True
        else:
            # Just test the first one,
            # not expecting a case where other processes turn off cores
            return bool(read(CPU_DIR + f'cpu{core_ids[0]}/online', int))

    def set_physical_cores_online(self, num_cores: int):
        '''Sets the number of online physical cores, turns off the rest'''
        assert 0 < num_cores and num_cores <= self.spec.physical_cores
        # Iterate over physical core_num and virtual core siblings
        for core_num, core_ids in enumerate(self.spec.thread_siblings):
            core_online = self.read_physical_core_status(core_num)
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

    def read_cpu_utilization(self, mode='max'):
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

    def read_temperature(self) -> float:
        if self.spec.temp_sensor:
            return psutil.sensors_temperatures()[self.spec.temp_sensor][0].current
        else:
            return -1

    def read_crit_temp(self) -> int:
        if self.spec.temp_sensor:
            return int(psutil.sensors_temperatures()[self.spec.temp_sensor][0].critical)
        else:
            # If no crit temp found default to 100
            return 100

    # CPU Freq Scaling

    def read_governor(self, core_id: int = 0) -> str:
        return read(CPU_DIR + f'cpu{core_id}/cpufreq/scaling_governor')

    def set_governor(self, governor):
        assert governor in self.spec.governors
        if self.read_governor() != governor:
            for core_id in list_cores('online'):
                Path(CPU_DIR + f'cpu{core_id}/cpufreq/scaling_governor').write_text(governor)

    def read_policy(self, core_id: int = 0) -> str:
        if self.spec.policies:
            return read(CPU_DIR + f'cpu{core_id}/cpufreq/energy_performance_preference')
        else:
            return ''

    def set_policy(self, policy):
        if self.spec.policies:
            assert policy in self.spec.policies
            if policy != self.read_policy():
                for core_id in list_cores('online'):
                    Path(CPU_DIR + f'cpu{core_id}/cpufreq/energy_performance_preference').write_text(policy)

    def read_current_freq(self) -> dict:
        ''' Returns dict of core_id:cur_freq'''
        cores_online = self.list_cores('online')
        cpuinfo = Path('/proc/cpuinfo')
        cur_freqs = [int(float(line.split(':')[-1])) for line in cpuinfo.read_text().splitlines()
                     if line.startswith('cpu M')]
        return dict(zip(cores_online, cur_freqs))

    def read_freq_range(self, core_id: int = 0) -> list:
        scaling_min_freq = read(CPU_DIR + f'cpu{core_id}/cpufreq/scaling_min_freq', int)
        scaling_max_freq = read(CPU_DIR + f'cpu{core_id}/cpufreq/scaling_max_freq', int)
        return [scaling_min_freq, scaling_max_freq]

    def set_freq_range(self, min_freq: int, max_freq: int):
        # Preferred for cpufreq
        assert min_freq <= max_freq
        # Write new freq values if different from current
        current_freq_range = self.read_freq_range()
        for core_id in self.list_cores('online'):
            if min_freq != current_freq_range[0]:
                Path(CPU_DIR + f'cpu{core_id}/cpufreq/scaling_min_freq').write_text(str(min_freq))
            if max_freq != current_freq_range[1]:
                Path(CPU_DIR + f'cpu{core_id}/cpufreq/scaling_max_freq').write_text(str(max_freq))

    def read_perf_range(self) -> tuple:
        if self.spec.driver == 'intel_pstate':
            return read(self.spec.min_perf_pct, int), read(self.spec.max_perf_pct, int)

    def set_perf_range(self, min_perf_pct: int, max_perf_pct: int):
        # This setting only exists for intel_pstate
        assert max_perf_pct >= min_perf_pct
        if self.spec.driver == 'intel_pstate':
            current_perf_range = self.read_perf_range()
            if min_perf_pct != current_perf_range[0]:
                self.spec.min_perf_pct.write_text(str(min_perf_pct))
            if max_perf_pct != current_perf_range[1]:
                self.spec.max_perf_pct.write_text(str(max_perf_pct))

    def read_turbo_state(self):
        '''Read existing turbo file and invert value if appropriate (intel_pstate/no_turbo).'''
        if self.spec.turbo_path is None:
            return None
        else:
            return bool(int(self.spec.turbo_path.read_text())) ^ self.spec.turbo_inverse

    def set_turbo_state(self, turbo_state: bool):
        if self.spec.turbo_allowed and (turbo_state != self.read_turbo_state()):
            self.spec.turbo_path.write_text(str(int(turbo_state ^ self.spec.turbo_inverse)))

    # TDP control

    @staticmethod
    def get_rapl():
        ''' Returns an instance of appropriate Rapl Class'''
        # a more generic rapl interface might be needed if AMD enables one
        # if Path('/sys/class/powercap/intel-rapl/enabled').exists():
        return IntelRapl()
        #  elif amd_pstate's path exists:
        #      return AMDRapl()

    def set_tdp_limits(self, PL1: int, PL2: int):
        '''
        Set PL1 and PL2 power limits (intel_pstate)
        If PL1 or PL2 is zero, this does nothing.
        '''
        assert PL1 <= PL2
        if self.rapl.enabled and PL1 and PL2:
            PL1_path = Path('/sys/class/powercap/intel-rapl:0/constraint_0_power_limit_uw')
            PL2_path = PL1_path.with_name('constraint_1_power_limit_uw')
            if PL1_path.exists() and PL2_path.exists():
                if PL1 > 0:
                    PL1_path.write_text(str(PL1*1_000_000))
                if PL2 > 0:
                    PL2_path.write_text(str(PL2*1_000_000))
                if PL1 > 0 or PL2 > 0:
                    PL1_path.with_name('enabled').write_text('1')
