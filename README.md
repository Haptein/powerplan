# cpuauto

Actively monitors charging, CPU utilization and temperature to automatically switch between CPU power configurations, optimizing battery life and system responsivity. This software is still WIP, and some functionalities might not yet be implemented. This software interacts directly with Linux kernel userspace tools to change the CPU's configuration.

While it ships with sensible defaults, in practice, every use case is different. It's easy to create different power profiles (or edit the default one) that switch on and off automatically whenever specified processes are running. You could have a low temperature target profile that switches on whenever you open your preferred pdf viewer or a highly performant profile whenever you run blender, for example.

This software also gives you the tools to understand your specific machine power/temperature characteristics, aiding you in the creation of these profiles (WIP, that's the plan).

These are the configurable options:
- TDP limits (intel_pstate)
- Temperature target (Not yet implemented)
- Online core count
- Turbo on/off
- Performance range (intel_pstate)
- Frequency range
- Frequency scaling governors
- Energy performance preference

## How to
```
# install
git clone https://github.com/Haptein/cpuauto.git
cd cpuauto && sudo ./install

# uninstall
sudo cpuauto --uninstall
```

## Usage
```
usage: cpuauto [-h] [-l] [-s] [-p PROFILE] [-r] [--uninstall] [-v]

Automatic CPU power configuration control.

optional arguments:
  -h, --help            show this help message and exit
  -l, --list            list profiles and exit
  -s, --status          show system status
  -p PROFILE, --profile PROFILE
                        activate a given profile and exit
  -r, --reload          hot-reload profiles (for testing)
  --uninstall           uninstall program
  -v, --version         show program version and exit
```

## Config guide
Configuring a profile is simple with the toml format, these are the following configurable properties for profiles:

- **turbo:** Turbo boost/core on or off.
- **cores_online:** Number of physical cores online.
- **minfreq, maxfreq:** CPU frequency (kHz) range.
- **governor:** Frequency scaling governor.
- **policy:** Energy performance preference.
- **triggerapps:** List of process names that trigger the profile automatically.
- **pollingperiod:** Time (ms) between system readings, lower makes it more responsive.
- **priority:** If several profiles are triggered, the one with the lower value gets selected.
- **templimit:** Temperature target (not yet implemented).

intel_pstate only:
- **minperf, maxfreq:** Performance percent range (recommended instead of minfreq/maxfreq). 
- **tdp_sutained, tdp_burst:** CPU sustained and burst TDP limits (PL1 & PL2) in Watt units.


**Important:** these options must be pre-fixed with either **ac_** or **bat_** to determine the charging situation in which the values should be set (desktop just use ac_). It's also not necessary to specify every property for new profiles, the missing ones will get filled in by the DEFAULT profile's values.
