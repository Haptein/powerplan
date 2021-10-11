
## Proyect Structure:
    - config : reading and parsing profile data
    - cpu : processor configuration interface
    - powerplan : main file
    - status : system information/status
    - log : logging
    - powersupply : ac-adapter/battery interface
    - process : Process reading
    - shell : shell interface and misc funcs


## TODO

### Core Function
- Status Object (wip)
- System profiling (wip)
- Temperature control system (researching...)
- Check that power_supply interfaces don't raise ENODEV on power_method
- Implement power draw methods:
    - energy_tracking: energy_now {mWh}
    - charge_tracking: charge_now (mAh) * voltage_now
- Enforce persistent flag on --reload

### QoL
- Look further into optimization
- Profile editing GUI
- Check dependencies on install