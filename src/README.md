
## Proyect Structure:
    - config : reading and parsing and application of profile data
    - cpu : processor configuration interface
    - powerplan : main file
    - status : system status, information display
    - log : logging
    - powersupply : ac-adapter/battery/UPS interface
    - process : Process reading
    - shell : shell interface and misc funcs


## TODO

### Core Function
- Status history, SystemStatus Object (wip)
- System Efficiency modeling (wip, researching...)
- Temperature control system (researching...)
- Implement powersupply devices as classes, needed for the following:
    - Remember kernel raising ENODEV for each power_method (warn only once, change power_method)
    - Implement power draw methods:
        - energy_tracking: energy_now {mWh}
        - charge_tracking: charge_now (mAh) * voltage_now
- Add UPS as powersupply
- Add support for amd-pstate (after it lands in mainline)
- Selectively display powersupply names in status.SYSTEM_INFO

### QoL
- Profile editing GUI
- Check dependencies on install