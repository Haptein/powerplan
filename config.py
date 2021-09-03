#!/usr/bin/python3

import os
import toml
import psutil
from dataclasses import dataclass
from cpu import read_procs, read_cpu_info

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
# CONFIG_DIR = './' # debugging
CONFIG_PATH = CONFIG_DIR + "/cpuauto.toml"

@dataclass(order=True)
class CpuProfile:
    priority: int
    name: str
    pollingperiod: int
    templimit: int
    ac_minfreq: int
    ac_maxfreq: int
    bat_minfreq: int
    bat_maxfreq: int
    ac_minperf: int
    ac_maxperf: int
    bat_minperf: int
    bat_maxperf: int
    ac_turbo: bool
    bat_turbo: bool
    ac_governor: str
    bat_governor: str
    ac_policy: str
    bat_policy: str
    triggerapps: list

    def triggerapp_present(self, procs: set):
        for app in self.triggerapps:
            if app in procs:
                return True
        return False


# Config IO

def check_config(config):
    '''Checks config values for correctness'''
    pass


def read_config():
    '''Reads config file, checks values and returns config dict'''
    if not os.path.isfile(CONFIG_PATH):
        write_default_config()

    config = toml.load(CONFIG_PATH)
    check_config(config)
    return config


def write_config(config):
    '''Writes a dict as a toml file'''
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as file:
        toml.dump(config, file)


def write_default_config():
    cpu_info = read_cpu_info()
    config = dict(DEFAULT=dict(
        priority=99,
        pollingperiod=2000,
        templimit=cpu_info['crittemp'],
        ac_minfreq=cpu_info['minfreq'],
        ac_maxfreq=cpu_info['maxfreq'],
        bat_minfreq=cpu_info['minfreq'],
        bat_maxfreq=int(cpu_info['minfreq']*0.75 + cpu_info['maxfreq']*0.25),
        ac_minperf=0,
        ac_maxperf=100,
        bat_minperf=0,
        bat_maxperf=96,
        ac_turbo=True,
        bat_turbo=False,
        ac_governor='performance',
        bat_governor='powersave',
        ac_policy='balance_performance',
        bat_policy='power',
        triggerapps=[]
    ))

    write_config(config)


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
    for profile in PROFILES:
        print(profile)
        print(PROFILES[profile])
    print('max priority:', max(list(PROFILES)))
