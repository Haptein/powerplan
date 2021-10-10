#!/usr/bin/python3
import os
import configparser
from time import time, sleep

import powersupply
import cpu
from cpu import CPU
from shell import is_root
from log import log_error, log_info

CONFIG_PATH = '/etc/powerplan.conf'

def preferred_available(preference, available):
    '''Returns the first element in preference of available'''
    for p in preference:
        if p in available:
            return p
    else:
        log_info(f'Only unknown governors present: {available}. Default will be {available[0]}.')
        return available[0]


default_ac_governor_preference = dict(
    cpufreq=('schedutil', 'ondemand', 'performance', 'conservative', 'powersave'),
    intel_pstate=('powersave', 'performance')
)

default_bat_governor_preference = dict(
    cpufreq=('schedutil', 'ondemand', 'conservative', 'powersave', 'performance'),
    intel_pstate=('powersave', 'performance')
)

DEFAULT_PROFILE = dict(
    priority=99,
    ac_pollingperiod=1000,
    bat_pollingperiod=2000,
    ac_cores_online=CPU.physical_cores,
    bat_cores_online=CPU.physical_cores,
    ac_templimit=CPU.crit_temp - 5,
    bat_templimit=CPU.crit_temp - 5,
    ac_minfreq=CPU.minfreq // 1000,
    ac_maxfreq=CPU.maxfreq // 1000,
    bat_minfreq=CPU.minfreq // 1000,
    bat_maxfreq=int(CPU.minfreq*0.6 + CPU.maxfreq*0.4) // 1000,
    ac_minperf=1,
    ac_maxperf=100,
    bat_minperf=1,
    bat_maxperf=96,
    ac_tdp_sustained=0,
    ac_tdp_burst=0,
    bat_tdp_sustained=0,
    bat_tdp_burst=0,
    ac_turbo=True,
    bat_turbo=False,
    ac_governor=preferred_available(default_ac_governor_preference[CPU.driver], CPU.governors),
    bat_governor=preferred_available(default_bat_governor_preference[CPU.driver], CPU.governors),
    ac_policy='balance_performance' if hasattr(CPU, 'policies') else '',
    bat_policy='power' if hasattr(CPU, 'policies') else '',
    triggerapps=''
)


class PowerProfile:
    def __init__(self, name: str, section: configparser.SectionProxy):
        self.name = name
        self.ac_governor = section['ac_governor']
        self.bat_governor = section['bat_governor']
        self.ac_policy = section['ac_policy']
        self.bat_policy = section['bat_policy']
        self.triggerapps = [app.strip() for app in section['triggerapps'].split(',') if app]
        self.has_trigger = bool(self.triggerapps)

        # Type check / error handling
        i, b = section.getint, section.getboolean
        method_type_attr = (
            (i, 'integer', 'priority'),
            (i, 'integer', 'ac_pollingperiod'),
            (i, 'integer', 'bat_pollingperiod'),
            (i, 'integer', 'ac_cores_online'),
            (i, 'integer', 'bat_cores_online'),
            (i, 'integer', 'ac_templimit'),
            (i, 'integer', 'bat_templimit'),
            (i, 'integer', 'ac_minfreq'),
            (i, 'integer', 'ac_maxfreq'),
            (i, 'integer', 'bat_minfreq'),
            (i, 'integer', 'bat_maxfreq'),
            (i, 'integer', 'ac_minperf'),
            (i, 'integer', 'ac_maxperf'),
            (i, 'integer', 'bat_minperf'),
            (i, 'integer', 'bat_maxperf'),
            (i, 'integer', 'ac_tdp_sustained'),
            (i, 'integer', 'ac_tdp_burst'),
            (i, 'integer', 'bat_tdp_sustained'),
            (i, 'integer', 'bat_tdp_burst'),
            (b, 'boolean', 'ac_turbo'),
            (b, 'boolean', 'bat_turbo')
        )

        for (method, type_name, attr) in method_type_attr:
            try:
                setattr(self, attr, method(attr))
            except ValueError:
                log_error(f'Invalid profile "{self.name}": {attr} must be of {type_name} type.')

        # Value checks
        self._validate()
        self._set_freqs_to_khz()

    def apply(self, charging):
        ''' Applies profile configuration'''
        if charging:
            cpu.set_physical_cores_online(self.ac_cores_online)
            cpu.set_freq_range(self.ac_minfreq, self.ac_maxfreq)
            cpu.set_perf_range(self.ac_minperf, self.ac_maxperf)
            cpu.set_turbo_state(self.ac_turbo)
            cpu.set_governor(self.ac_governor)
            cpu.set_policy(self.ac_policy)
            cpu.set_tdp_limits(self.ac_tdp_sustained, self.ac_tdp_burst)
        else:
            cpu.set_physical_cores_online(self.bat_cores_online)
            cpu.set_freq_range(self.bat_minfreq, self.bat_maxfreq)
            cpu.set_perf_range(self.bat_minperf, self.bat_maxperf)
            cpu.set_turbo_state(self.bat_turbo)
            cpu.set_governor(self.bat_governor)
            cpu.set_policy(self.bat_policy)
            cpu.set_tdp_limits(self.bat_tdp_sustained, self.bat_tdp_burst)

    def triggerapp_present(self, procs: set) -> bool:
        for app in self.triggerapps:
            if app[:15] in procs:
                return True
        return False

    def sleep(self, iteration_start, charging_state=None):
        if charging_state is None:
            charging_state = powersupply.charging()
        if charging_state:
            pollingperiod = self.ac_pollingperiod / 1000
        else:
            pollingperiod = self.bat_pollingperiod / 1000

        sleep(max((0, pollingperiod - time() + iteration_start)))

    def _set_freqs_to_khz(self):
        self.ac_minfreq *= 1000
        self.ac_maxfreq *= 1000
        self.bat_minfreq *= 1000
        self.bat_maxfreq *= 1000

    def _check_value_in_range(self, value_name, value, allowed_range) -> bool:
        minimum, maximum = allowed_range
        if not (minimum <= value and value <= maximum):  # range is limit inclusive
            log_error(f'Invalid profile "{self.name}": {value_name} is outside allowed range. '
                      f'Allowed range for this value is: {allowed_range}.')

    def _check_value_order(self, range_name, minimum, maximum):
        if minimum > maximum:
            log_error(f'Invalid profile "{self.name}": range {range_name} is invalid. '
                      'Maximum must be greater than or equal to minimum.')

    def _validate(self):
        # Validates profile values
        if self.name != 'DEFAULT' and not self.has_trigger:
            log_info(f'Profile "{self.name}" has no trigger applications configured.')

        # Polling period
        for value_name, value in zip(('ac_pollingperiod', 'bat_pollingperiod'),
                                     (self.ac_pollingperiod, self.bat_pollingperiod)):
            if value <= 0:
                log_error(f'Invalid profile "{self.name}": {value_name} must be greater than zero.')

        # Online Cores
        self._check_value_in_range('', self.ac_cores_online, [1, CPU.physical_cores])
        self._check_value_in_range('', self.bat_cores_online, [1, CPU.physical_cores])

        # Freq ranges, check them as MHz so errors are not confusing
        allowed_freq_range = [CPU.minfreq // 1000, CPU.maxfreq // 1000]
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
        self._check_value_order('ac_tdp_sustain/ac_tdp_burst', self.ac_tdp_sustained, self.ac_tdp_burst)
        self._check_value_order('bat_tdp_sustain/bat_tdp_burst', self.bat_tdp_sustained, self.bat_tdp_burst)

        # Governor available
        if self.ac_governor not in CPU.governors:
            log_error(f'Invalid profile "{self.name}": ac_governor "{self.ac_governor}" not in available governors.'
                      f'\nAvailable governors: {CPU.governors}')

        if self.bat_governor not in CPU.governors:
            log_error(f'Invalid profile "{self.name}": bat_governor "{self.bat_governor}" not in available governors.'
                      f'\nAvailable governors: {CPU.governors}')

        # Policy available
        if hasattr(CPU, 'policies'):
            if self.ac_policy not in CPU.policies:
                log_error(f'Invalid profile "{self.name}": ac_policy "{self.ac_policy}" not in available policies.'
                          f'\nAvailable policies: {CPU.policies}')

            if self.bat_policy not in CPU.policies:
                log_error(f'Invalid profile "{self.name}": bat_policy "{self.bat_policy}" not in available policies.'
                          f'\nAvailable policies: {CPU.policies}')

            # Governor - Policy compatibility:
            if self.ac_governor == 'performance':
                if self.ac_policy != 'performance':
                    log_error(f'Invalid profile "{self.name}": '
                              f'ac_governor {self.ac_governor} is incompatible with ac_policy {self.ac_policy}.')

            if self.bat_governor == 'performance':
                if self.bat_policy != 'performance':
                    log_error(f'Invalid profile "{self.name}": '
                              f'bat_governor {self.bat_governor} is incompatible with bat_policy {self.bat_policy}.')


# Config IO

def check_config_keys(config):
    '''Checks config keys present'''

    # Default profile must exist
    if 'DEFAULT' not in config:
        log_error('DEFAULT profile not present in config file.')

    # Check that all needed keys are present in DEFAULT profile
    provided_default_keys = dict(name='', **config['DEFAULT']).keys()
    needed_default_keys = DEFAULT_PROFILE.keys()
    for needed_key in needed_default_keys:
        if needed_key not in provided_default_keys:
            log_error(f'DEFAULT profile is missing the following key: {needed_key}.')

    # Look for invalid keys in every profile
    for profile_name in config:
        for key in config[profile_name]:
            if key not in needed_default_keys:
                log_error(f'Invalid profile "{profile_name}": invalid key "{key}".')


def read_config():
    '''Reads config file, checks values and returns config dict'''
    if not os.path.isfile(CONFIG_PATH):
        log_info('Configuration file does not exist.')
        write_default_config()
        log_info(f'New config file has been created at {CONFIG_PATH}.')

    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    check_config_keys(config)
    return config

def write_default_config():
    if not is_root():
        print('Configuration file does not exist.')
        log_error('Root privileges needed to write configuration file.')
    config = configparser.ConfigParser()
    config['DEFAULT'] = DEFAULT_PROFILE
    with open(CONFIG_PATH, 'w') as file:
        config.write(file)

def read_profiles():
    '''returns a dict of PowerProfile objects, sorted by ascending priority'''
    config = read_config()
    profiles = {key: PowerProfile(key, config[key]) for key in config}
    # Sort and return
    sorted_names = sorted(profiles, key=lambda name: profiles[name].priority)
    return {name: profiles[name] for name in sorted_names}


if __name__ == '__main__':
    PROFILES = read_profiles()
    print(PROFILES)
    print('max priority:', max(list(PROFILES)))
