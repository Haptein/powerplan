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


## Usage
```
usage: cpuauto.py [-h] [-d] [-i] [-p PROFILE] [-l]

Automatic CPU power configuration control.

optional arguments:
  -h, --help            show this help message and exit
  -d, --debug           display runtime info
  -i, --info            show system info
  -p PROFILE, --profile PROFILE
                        activate a given profile
  -l, --list            list configured profiles
```

## Config guide
Configuring a profile is simple with the toml format, these are the following configurable properties for profiles:

- **priority:** If several profiles are triggered, the one with the lower value gets selected.
- **pollingperiod:** Time (ms) between readings, lower makes it more responsive.
- **cores_online:** Number of physical cores online.
- **templimit:** Temperature target (not yet implemented).
- **minfreq:** Minimum CPU frequency (kHz).
- **maxfreq:** Maximum CPU frequency (kHz).
- **turbo:** Turbo boost/core on or off.
- **governor:** Frequency scaling governor.
- **policy:** Energy performance preference.
- **triggerapps:** List of process names that trigger the profile.

intel_pstate only:

- **minperf:** Minimum performance percent (recommended instead of minfreq). 
- **maxperf:** Maximum performance percent (recommended instead of maxfreq).
- **tdp_sutained:** CPU sustained TDP limit (PL1).
- **tdp_burst:** CPU burst TDP limit (PL2).

**Important:** these options must be pre-fixed with either **ac_** or **bat_** to determine the charging situation in which the values should be set (desktop just use ac_). It's also not necessary to specify every property for new profiles, the missing ones will get filled in by the DEFAULT profile's values.


# TODO

### Core Function
- Look into Demand/Power curves
- Look into Demand/Corecount curves
- Temperature control system

### Diagnostics
- Error Logging
- Performance Logging/Monitoring
- Proper CLI monitor mode

### QoL
- Only log temperature sensor warning on initialization, sensor detection at init
- Warn if no power reading method available
- Profile editing GUI
- Look further into optimization

## Proyect Structure:
    - cpuauto : main file
    - cpu : cpu API
    - config : well, umm config stuffs.
    - log : error and performance logging, basically a placeholder for now.
