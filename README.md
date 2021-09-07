# cpuauto

Actively monitors charging, CPU utilization and temperature to automatically switch between CPU power configurations, optimizing battery life and system responsivity. This software is still WIP, and some functionalities might not yet be implemented. This software interacts directly with the Linux kernel userspace tools to change the CPU's configuration.

While it ships with sensible defaults, in practice, every use case is different. With cpuauto it's easy to create different power profiles (or edit the default one) that switch on and off automatically whenever specified processes are running. You could have a low temperature target profile that switches on whenever you open your preferred pdf viewer or a highly performant profile whenever you run blender, for example.

This software also gives you the tools to understand your specific machine power/temperature characteristics, aiding you in the creation of these profiles.

These are the configurable options:
- TDP limits (TBD)
- Temperature target (Not yet implemented)
- Online core count
- Turbo states
- Performance range (intel_pstate)
- Frequency range
- Frequency scaling governors
- Energy performance preference


### Structure:
    - cpuauto : main file
    - cpu : cpu API
    - config : well, umm config stuffs.
    - log : error and performance logging.

# TODO

### Core Function
- Demand / Power curves (?)
- Demand / Corecount curves (?)
- TDP Limiting (researching)
- Temperature control system

### Diagnostics
- Error Logging
- Performance Logging/Monitoring

### QoL
- Only log temperature sensor warning on initialization, sensor detection at init
- Warn if no power reading method available
- GUI
- Further Optimize

