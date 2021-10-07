# powerplan

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
git clone https://github.com/Haptein/powerplan.git
cd powerplan && sudo ./install
```
**Dependencies:**
- python >= 3.6
- psutil
  

```
# uninstall
sudo powerplan --uninstall
```

## Usage

```
usage: powerplan.py [-h] [-l] [-p PROFILE] [-r] [-s] [--daemon] [--log]
                  [--persistent] [--test] [--uninstall] [--verbose]
                  [--version]

Automatic CPU power configuration control.

optional arguments:
  -h, --help            show this help message and exit
  -l, --list            list profiles and exit
  -p PROFILE, --profile PROFILE
                        activate the specified profile and exit
  -r, --reload          enable config file hot-reloading
  -s, --status          display system status periodically
  --daemon              install and enable as a daemon (systemd)
  --log                 print daemon log
  --persistent          use this if your profile is reset by your computer
  --test                stress CPU and record power/performance metrics to a csv file
  --uninstall           uninstall program
  --verbose             print runtime info
  --version             show program version and exit
```

### Main modes:
**default mode:**
powerplan will periodically monitor cpu temps, runnining processes, and charging state to switch between the  profiles specified in /etc/powerplan.toml.

**--daemon:**
powerplan will install and enable itself as a systemd daemon. It runs exactly as if no arguments were provided, at boot time.

**--status**
powerplan displays system configuration periodically. It will also apply such configurations (active mode) unless an instance of powerplan is already running (monitor mode).

**--profile**
Single profile activation mode. Useful if you'd rather define profiles and switch between them manually.

**--reload**
Enable hot-reloading the configuration file. Usefull for trying out different profile paremeters.


## Config guide
The configuration is located at **/etc/powerplan.conf**. A DEFAULT profile is included and is defined with parameters specific to your machine's CPU. Creating your own profiles (or editing the DEFAULT one) is simple. These are the available parameters:

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

  
**Important:** these options must be pre-fixed with either **ac_** or **bat_** to determine the charging situation in which the values should be set (use ac_ for desktop). It's also not necessary to specify every property for every additional profile, the unspecified ones will get filled in by the DEFAULT profile.
