
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
- change battery power_method if active one fails (?)
- Add UPS as powersupply
- Add support for amd-pstate (after it lands in mainline)

### QoL
- Profile editing GUI
- Check dependencies on install
- Reuse History object in IntelLayer.power_read