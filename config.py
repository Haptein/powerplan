#!/usr/bin/python3

import os
import toml
from time import time
from dataclasses import dataclass

import cpu
from cpu import CPU
from log import log_error, log_warning

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = CONFIG_DIR + "/cpuauto.toml"

DEFAULT_CONFIG = dict(DEFAULT=dict(
    priority=99,
    ac_pollingperiod=1000,
    bat_pollingperiod=2000,
    ac_cores_online=CPU['physical_cores'],
    bat_cores_online=CPU['physical_cores'],
    ac_templimit=CPU['crit_temp'] - 5,
    bat_templimit=CPU['crit_temp'] - 5,
    ac_minfreq=CPU['minfreq'],
    ac_maxfreq=CPU['maxfreq'],
    bat_minfreq=CPU['minfreq'],
    bat_maxfreq=int(CPU['minfreq']*0.75 + CPU['maxfreq']*0.25),
    ac_minperf=1,
    ac_maxperf=100,
    bat_minperf=1,
    bat_maxperf=96,
    ac_tdp_sutained=0,
    ac_tdp_burst=0,
    bat_tdp_sutained=0,
    bat_tdp_burst=0,
    ac_turbo=True,
    bat_turbo=False,
    ac_governor='powersave',
    bat_governor='powersave',
    ac_policy='balance_performance',
    bat_policy='power',
    triggerapps=[]
))

@dataclass(order=True)
class CpuProfile:
    priority: int
    name: str
    ac_pollingperiod: int
    bat_pollingperiod: int
    ac_cores_online: int
    bat_cores_online: int
    ac_templimit: int
    bat_templimit: int
    ac_minfreq: int
    ac_maxfreq: int
    bat_minfreq: int
    bat_maxfreq: int
    ac_minperf: int
    ac_maxperf: int
    bat_minperf: int
    bat_maxperf: int
    ac_tdp_sutained: int
    ac_tdp_burst: int
    bat_tdp_sutained: int
    bat_tdp_burst: int
    ac_turbo: bool
    bat_turbo: bool
    ac_governor: str
    bat_governor: str
    ac_policy: str
    bat_policy: str
    triggerapps: list

    def apply(self) -> float:
        ''' Applies profile configuration and returns sleep time needed (after compensation)'''
        time_start = time()
        charging = cpu.read_charging_state()
        if charging:
            cpu.set_physical_cores_online(self.ac_cores_online)
            cpu.set_freq_range(self.ac_minfreq, self.ac_maxfreq)
            cpu.set_perf_range(self.ac_minperf, self.ac_maxperf)
            cpu.set_turbo_state(self.ac_turbo)
            cpu.set_governor(self.ac_governor)
            cpu.set_policy(self.ac_policy)
            polling_period = self.ac_pollingperiod / 1000
        else:
            cpu.set_physical_cores_online(self.bat_cores_online)
            cpu.set_freq_range(self.bat_minfreq, self.bat_maxfreq)
            cpu.set_perf_range(self.bat_minperf, self.bat_maxperf)
            cpu.set_turbo_state(self.bat_turbo)
            cpu.set_governor(self.bat_governor)
            cpu.set_policy(self.bat_policy)
            polling_period = self.bat_pollingperiod / 1000

        # Time compensation
        time_delta = time() - time_start
        sleep_time = polling_period - time_delta
        if sleep_time < 0:
            log_warning(f'Process takes {time_delta} seconds. Polling period is too low.')
        return sleep_time

    def triggerapp_present(self, procs: set):
        for app in self.triggerapps:
            if app[:15] in procs:
                return True
        return False

    def _check_value_in_range(self, value_name, value, allowed_range) -> bool:
        minimum, maximum = allowed_range
        if not (minimum <= value and value <= maximum):  # range is limit inclusive
            error_msg = f'Error found in profile "{self.name}": value of {value_name} is outside allowed range.' + \
                f'\nAllowed range for this value is: {allowed_range}.'
            log_error(error_msg)

    def _check_value_order(self, range_name, minimum, maximum):
        if minimum > maximum:
            error_msg = f'Error found in profile "{self.name}": value of {range_name} is invalid.' + \
                '\nMaximum must be greater than or equal to minimum.'
            log_error(error_msg)

    def __post_init__(self):
        # Validates profile values

        # Polling period
        for value_name, value in zip(('ac_pollingperiod', 'bat_pollingperiod'),
                                     (self.ac_pollingperiod, self.bat_pollingperiod)):
            if value <= 0:
                log_error(f'Error found in profile "{self.name}": value of {value_name} is invalid.'
                          '\nThis value must be greater than zero.')

        # Online Cores
        self._check_value_in_range('', self.ac_cores_online, [1, CPU['physical_cores']])
        self._check_value_in_range('', self.bat_cores_online, [1, CPU['physical_cores']])

        # Freq ranges
        allowed_freq_range = [CPU['minfreq'], CPU['maxfreq']]
        self._check_value_order('ac_minfreq/ac_maxfreq', self.ac_minfreq, self.ac_maxfreq)
        self._check_value_in_range('ac_minfreq', self.ac_minfreq, allowed_freq_range)
        self._check_value_in_range('ac_maxfreq', self.ac_maxfreq, allowed_freq_range)
        self._check_value_order('bat_minfreq/bat_maxfreq', self.bat_minfreq, self.bat_maxfreq)
        self._check_value_in_range('bat_minfreq', self.bat_minfreq, allowed_freq_range)
        self._check_value_in_range('bat_maxfreq', self.bat_maxfreq, allowed_freq_range)

        # Perf ranges
        allowed_perf_range = [1, 100]
        self._check_value_order('ac_minperf/ac_maxperf', self.ac_minperf, self.ac_maxperf)
        self._check_value_in_range('ac_minperf', self.ac_minperf, allowed_perf_range)
        self._check_value_in_range('ac_maxperf', self.ac_maxperf, allowed_perf_range)
        self._check_value_order('bat_minperf/bat_maxperf', self.bat_minperf, self.bat_maxperf)
        self._check_value_in_range('bat_minperf', self.bat_minperf, allowed_perf_range)
        self._check_value_in_range('bat_maxperf', self.bat_maxperf, allowed_perf_range)

        # TDP Limits PL1 <= PL2
        self._check_value_order('ac_tdp_sustain/ac_tdp_burst', self.ac_tdp_sutained, self.ac_tdp_burst)
        self._check_value_order('bat_tdp_sustain/bat_tdp_burst', self.bat_tdp_sutained, self.bat_tdp_burst)

        # Governor available
        if self.ac_governor not in CPU['governors']:
            error_msg = (f'ac_governor value "{self.ac_governor}" '
                         f'in profile "{self.name}" not in available governors.'
                         f'\nAvailable governors: {CPU["governors"]}')
            log_error(error_msg)
        if self.bat_governor not in CPU['governors']:
            error_msg = (f'bat_governor value "{self.bat_governor}" '
                         f'in profile "{self.name}" not in available governors.'
                         f'\nAvailable governors: {CPU["governors"]}')
            log_error(error_msg)

        # Policy available
        if self.ac_policy not in CPU['policies']:
            error_msg = (f'ac_policy value "{self.ac_policy}" '
                         f'in profile "{self.name}" not in available policies.'
                         f'\nAvailable policies: {CPU["policies"]}')
            log_error(error_msg)
        if self.bat_policy not in CPU['policies']:
            error_msg = (f'bat_policy value "{self.bat_policy}" '
                         f'in profile "{self.name}" not in available policies.'
                         f'\nAvailable policies: {CPU["policies"]}')
            log_error(error_msg)

        # Governor - Policy compatibility:
        if self.ac_governor == 'performance':
            if self.ac_policy != 'performance':
                log_error(f'ac_governor value {self.ac_governor} is incompatible with ac_policy {self.ac_policy} '
                          f'in profile "{self.name}".')

        if self.bat_governor == 'performance':
            if self.bat_policy != 'performance':
                log_error(f'bat_governor value {self.bat_governor} is incompatible with bat_policy {self.bat_policy} '
                          f'in profile "{self.name}".')


# Config IO

def check_config_keys(config):
    '''Checks config keys present'''

    # Default profile checks
    if 'DEFAULT' not in config:
        log_error('DEFAULT profile not present in config file.')
    else:
        # Check that all needed keys are present in DEFAULT profile
        provided_default_keys = dict(name='', **config['DEFAULT']).keys()
        needed_default_keys = DEFAULT_CONFIG['DEFAULT'].keys()
        for needed_key in needed_default_keys:
            if needed_key not in provided_default_keys:
                log_error(f'DEFAULT profile is missing the following key:{needed_key}')

    # Check keys in all profiles against DEFAULT_CONFIG['DEFAULT']
    for profile_name in config:
        for key in config[profile_name]:
            if key not in DEFAULT_CONFIG['DEFAULT'].keys():
                log_error(f'invalid key "{key}" in profile {profile_name}.')


def read_config():
    '''Reads config file, checks values and returns config dict'''
    if not os.path.isfile(CONFIG_PATH):
        write_config(DEFAULT_CONFIG)

    config = toml.load(CONFIG_PATH)
    check_config_keys(config)
    return config


def write_config(config):
    '''Writes a dict as a toml file'''
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as file:
        toml.dump(config, file)


def read_profiles():
    '''Reads profiles from config file, returns a dict of CpuProfile objs'''
    config = read_config()

    # Add profile names to profile dicts
    for profile_name in config:
        config[profile_name]['name'] = profile_name

    # Load default profile first
    PROFILES = dict(DEFAULT=CpuProfile(**config['DEFAULT']))

    for profile_name in config:
        # Default profile already loaded
        if profile_name == 'DEFAULT':
            continue

        # Specifying profiles with a few descriptors is allowed,
        # the rest are filled with values in DEFAULT
        full_profile = config['DEFAULT'].copy()
        full_profile.update(config[profile_name])
        PROFILES[profile_name] = CpuProfile(**full_profile)

    return PROFILES


if __name__ == '__main__':
    PROFILES = read_profiles()
    print(PROFILES)
    print('max priority:', max(list(PROFILES)))
