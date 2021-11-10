
## Proyect Structure:
    - config : reading and parsing and application of profile data
    - cpu : processor configuration interface
    - powerplan : main file
    - system : system and system status classes
    - monitor : system status monitoring
    - log : logging
    - powersupply : ac-adapter/battery/UPS interface
    - process : Process reading
    - shell : shell interface and misc funcs
    - systemstatus : system and status objects


## TODO

### Core Function
- System Efficiency modeling (wip, researching...)
- Temperature control system (researching...)
- Add support for amd-pstate (after it lands in mainline)

### QoL
- Profile editing GUI
- Check dependencies on install
- Write optimized temp reading (psutil reads ALL sensors each time)
- Add global config parameters: notify/persistence
