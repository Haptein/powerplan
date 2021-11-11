#!/usr/bin/python3
import configparser
from pathlib import Path
from time import time, sleep

import log
from shell import is_root

CONFIG_DIR = Path('/etc/powerplan')
CONFIG_PATH = CONFIG_DIR / 'powerplan.conf'
PROFILES_PATH = CONFIG_DIR / 'profiles.conf'

DEFAULT_CONFIG = dict(
    persistence='0 # Enable this if another application overrides power configurations',
    notifications='1'
)

def generate_default_profile(system) -> dict:
    '''Generates a defaul profile depending on system specifications'''

    def preferred_available(preference, available):
        '''Returns the first element in preference of available'''
        for p in preference:
            if p in available:
                return p
        else:
            log.info(f'Only unknown governors present: {available}. Default will be {available[0]}.')
            return available[0]

    # Governor priorities depending on power situation
    default_ac_governor_preference = dict(
        cpufreq=('schedutil', 'ondemand', 'performance', 'conservative', 'powersave'),
        intel_pstate=('powersave', 'performance')
    )

    default_bat_governor_preference = dict(
        cpufreq=('schedutil', 'ondemand', 'conservative', 'powersave', 'performance'),
        intel_pstate=('powersave', 'performance')
    )

    cpu_spec = system.cpu.spec
    default_profile = dict(
        priority=99,
        ac_pollingperiod=1000,
        bat_pollingperiod=2000,
        ac_cores_online=cpu_spec.physical_cores,
        bat_cores_online=cpu_spec.physical_cores,
        ac_templimit=cpu_spec.crit_temp - 5,
        bat_templimit=cpu_spec.crit_temp - 5,
        ac_minfreq=cpu_spec.minfreq // 1000,
        ac_maxfreq=cpu_spec.maxfreq // 1000,
        bat_minfreq=cpu_spec.minfreq // 1000,
        bat_maxfreq=int(cpu_spec.minfreq*0.6 + cpu_spec.maxfreq*0.4) // 1000,
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
        ac_governor=preferred_available(default_ac_governor_preference[cpu_spec.driver], cpu_spec.governors),
        bat_governor=preferred_available(default_bat_governor_preference[cpu_spec.driver], cpu_spec.governors),
        ac_policy='balance_performance' if cpu_spec.policies else '',
        bat_policy='power' if cpu_spec.policies else '',
        triggerapps=''
    )

    return default_profile


class PowerProfile:
    def __init__(self, name: str, section: configparser.SectionProxy, system):
        self.name = name
        self.ac_governor = section['ac_governor']
        self.bat_governor = section['bat_governor']
        self.ac_policy = section['ac_policy']
        self.bat_policy = section['bat_policy']
        self.triggerapps = [app.strip() for app in section['triggerapps'].split(',') if app]
        self.has_trigger = bool(self.triggerapps)
        self.system = system
        self.description = self._description()

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
                log.error(f'Invalid profile "{self.name}": {attr} must be of {type_name} type.')

        # Value checks
        self._validate()
        self._set_freqs_to_khz()

    def _description(self) -> str:
        description = self.name
        if self.has_trigger:
            description += f'\t\ttriggered by {", ".join(self.triggerapps)}'
        return description

    def apply(self, status):
        ''' Applies profile configuration'''
        cpu = self.system.cpu
        if status['ac_power']:
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

    def sleep(self, iteration_start, status):
        if status['ac_power']:
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
            log.error(f'Invalid profile "{self.name}": {value_name} is outside allowed range. '
                      f'Allowed range for this value is: {allowed_range}.')

    def _check_value_order(self, range_name, minimum, maximum):
        if minimum > maximum:
            log.error(f'Invalid profile "{self.name}": range {range_name} is invalid. '
                      'Maximum must be greater than or equal to minimum.')

    def _validate(self):
        cpu_spec = self.system.cpu.spec
        # Validates profile values
        if self.name != 'DEFAULT' and not self.has_trigger:
            log.info(f'Profile "{self.name}" has no trigger applications configured.')

        # Polling period
        for value_name, value in zip(('ac_pollingperiod', 'bat_pollingperiod'),
                                     (self.ac_pollingperiod, self.bat_pollingperiod)):
            if value <= 0:
                log.error(f'Invalid profile "{self.name}": {value_name} must be greater than zero.')

        # Online Cores
        self._check_value_in_range('', self.ac_cores_online, [1, cpu_spec.physical_cores])
        self._check_value_in_range('', self.bat_cores_online, [1, cpu_spec.physical_cores])

        # Freq ranges, check them as MHz so errors are not confusing
        allowed_freq_range = [cpu_spec.minfreq // 1000, cpu_spec.maxfreq // 1000]
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
        if self.ac_governor not in cpu_spec.governors:
            log.error(f'Invalid profile "{self.name}": ac_governor "{self.ac_governor}" not in available governors.'
                      f'\nAvailable governors: {cpu_spec.governors}')

        if self.bat_governor not in cpu_spec.governors:
            log.error(f'Invalid profile "{self.name}": bat_governor "{self.bat_governor}" not in available governors.'
                      f'\nAvailable governors: {cpu_spec.governors}')

        # Policy available
        if cpu_spec.policies:
            if self.ac_policy not in cpu_spec.policies:
                log.error(f'Invalid profile "{self.name}": ac_policy "{self.ac_policy}" not in available policies.'
                          f'\nAvailable policies: {cpu_spec.policies}')

            if self.bat_policy not in cpu_spec.policies:
                log.error(f'Invalid profile "{self.name}": bat_policy "{self.bat_policy}" not in available policies.'
                          f'\nAvailable policies: {cpu_spec.policies}')

            # Governor - Policy compatibility:
            if self.ac_governor == 'performance':
                if self.ac_policy != 'performance':
                    log.error(f'Invalid profile "{self.name}": '
                              f'ac_governor {self.ac_governor} is incompatible with ac_policy {self.ac_policy}.')

            if self.bat_governor == 'performance':
                if self.bat_policy != 'performance':
                    log.error(f'Invalid profile "{self.name}": '
                              f'bat_governor {self.bat_governor} is incompatible with bat_policy {self.bat_policy}.')

        # Warn if policy key but no policies available
        if self.ac_policy and not cpu_spec.policies:
            log.warning(f'ac_policy present in profile "{self.name}" but CPU does not support policies.')
        if self.bat_policy and not cpu_spec.policies:
            log.warning(f'bat_policy present in profile "{self.name}" but CPU does not support policies.')

# Config IO
def guarantee_config_dir():
    CONFIG_DIR.mkdir(exist_ok=True)

def check_config_keys(config):
    '''Check for unknown keys in config file'''
    for key in config.keys():
        if key not in DEFAULT_CONFIG:
            log.error(f'Unknown key "{key}" found in config file.')

def parse_config() -> configparser.SectionProxy:
    '''Parse config file and check for errors'''
    # make sure file exists (create default if it doesn't)
    guarantee_config_dir()
    if not CONFIG_PATH.exists():
        log.info('Configuration file does not exist.')
        write_config(DEFAULT_CONFIG)
        log.info(f'New configuration file has been created at {CONFIG_PATH}.')

    # configparser requires a section header but it's pointless here
    config_as_str = '[config]\n' + CONFIG_PATH.read_text()  # the workaround
    config = configparser.ConfigParser(defaults=DEFAULT_CONFIG, inline_comment_prefixes=(';', '#'))
    config.read_string(config_as_str)

    check_config_keys(config['config'])
    return config['config']

def read_config() -> dict:
    config = parse_config()
    config_dict = {key: config.getboolean(key) for key in config}
    return config_dict

def write_config(config: dict):
    config_str = '\n'.join(f'{key}={value}' for (key, value) in config.items())
    CONFIG_PATH.write_text(config_str)

def check_profiles_keys(config, default_profile):
    '''Checks config keys present'''

    # Default profile must exist
    if 'DEFAULT' not in config:
        log.error('DEFAULT profile not present in config file.')

    # Check that all needed keys are present in DEFAULT profile
    provided_default_keys = dict(name='', **config['DEFAULT']).keys()
    needed_default_keys = default_profile.keys()
    for needed_key in needed_default_keys:
        if needed_key not in provided_default_keys:
            log.error(f'DEFAULT profile is missing the following key: {needed_key}.')

    # Look for invalid keys in every profile
    for profile_name in config:
        for key in config[profile_name]:
            if key not in needed_default_keys:
                log.error(f'Invalid profile "{profile_name}": invalid key "{key}".')


def parse_profiles(system) -> configparser.ConfigParser:
    '''Reads profiles file, checks values and returns profiles dict'''
    guarantee_config_dir()
    PROFILES_PATH = CONFIG_DIR / 'profiles.conf'
    default_profile = generate_default_profile(system)
    if not PROFILES_PATH.exists():
        log.info('Profiles file does not exist.')
        write_default_profile(system)
        log.info(f'New profiles file has been created at {PROFILES_PATH}.')

    profile_parser = configparser.ConfigParser(inline_comment_prefixes=(';', '#'))
    profile_parser.read(PROFILES_PATH)
    check_profiles_keys(profile_parser, default_profile)
    return profile_parser

def write_default_profile(system):
    if not is_root():
        print('Configuration file does not exist.')
        log.error('Root privileges needed to write configuration file.')
    profileparser = configparser.ConfigParser()
    profileparser['DEFAULT'] = generate_default_profile(system)
    write_profiles(profileparser)

def write_profiles(profile_parser: configparser.ConfigParser):
    profiles_file = CONFIG_DIR / 'profiles.conf'
    with profiles_file.open(mode='w') as file:
        profile_parser.write(file)

def read_profiles(system) -> dict:
    '''returns a dict of PowerProfile objects, sorted by ascending priority'''
    profile_parser = parse_profiles(system)
    profiles = {key: PowerProfile(name=key, section=section, system=system) for (key, section) in profile_parser.items()}
    # Sort and return
    sorted_names = sorted(profiles, key=lambda name: profiles[name].priority)
    return {name: profiles[name] for name in sorted_names}


if __name__ == '__main__':
    PROFILES = read_profiles()
    print(PROFILES)
    print('max priority:', max(list(PROFILES)))
