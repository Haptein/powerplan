# powerplan

Powerplan allows you to switch between CPU power configurations depending on charging state, temperature (wip), specified running processes and the current workload (wip), optimizing battery life and system responsivity. It interacts directly with the Linux Kernel userspace tools in order to do so.

With powerplan you could for example, have your device automatically target low temperatures (therefore quieter fans) when opening your favourite document reader while on battery, or target maximum performance whenever you run a specific compute intensive program while on AC. Whether it be for battery savings, quieter runtimes, or maximum performance, the idea is to give you more control over the power usage of your device.

While it ships with sensible defaults, in practice, every use case is different. Creating different power profiles (or editing the default one) is pretty simple. These are the main configurable options:
- Turbo on/off
- Frequency range
- Online core count
- Frequency scaling governors
- Energy performance preference (intel_pstate)
- TDP limits (intel CPUs)
- Performance range (intel_pstate)
- Temperature target (wip)
- Trigger applications

This software also gives you tools to understand your specific machine power/temperature characteristics, aiding you in the creation of these profiles (wip).

## Installation
```
git clone https://github.com/Haptein/powerplan.git
cd powerplan && sudo ./install
```

**Dependencies:**
- python >= 3.6
- [psutil](https://github.com/giampaolo/psutil)


## Usage

```
usage: powerplan [-h] [-l] [-p PROFILE] [-r] [-s] [--daemon] [--log]
                 [--persistent] [--system] [--uninstall] [--verbose]
                 [--version]

Automatic CPU power configuration control.

optional arguments:
  -h, --help            show this help message and exit
  -l, --list            list profiles and exit
  -p PROFILE, --profile PROFILE
                        activate the specified profile and exit
  -r, --reload          enable config file hot-reloading
  -s, --status          display system status periodically
  --daemon              install and enable as a system daemon (systemd)
  --log                 print daemon log
  --persistent          use this if your profile is reset by your computer
  --system              show system info and exit
  --uninstall           uninstall program
  --verbose             print runtime info
  --version             show program version and exit
```

### Main modes:
**default mode:**
powerplan will periodically monitor cpu temps, runnining processes, and charging state to switch between the  profiles specified in /etc/powerplan.toml.

**--daemon:**
powerplan will install and enable itself as a systemd daemon. It runs exactly as if no arguments were provided, at boot time.
**note:** If you make changes to your configuration make sure to restart the daemon (ie. ```sudo systemctl restart powerplan```)

**--status**
powerplan displays system configuration periodically. It will also apply such configurations (**active mode**) unless an instance of powerplan is already running (**monitor mode**).

**--profile**
Single profile activation mode. Useful if you'd rather define profiles and switch between them manually.

**--reload**
Enable hot-reloading the configuration file. Usefull for trying out different profile paremeters.


## Config guide
The configuration is located at **/etc/powerplan.conf**. A DEFAULT profile is included and is defined with parameters specific to your machine's CPU. Creating your own profiles (or editing the DEFAULT one) is simple. These are the available parameters:

- **turbo:** Frequency boost on/off.
- **cores_online:** Number of physical cores online.
- **minfreq, maxfreq:** CPU frequency (MHz) range.
- **governor:** Frequency scaling governor.
- **triggerapps:** List of process names that trigger the profile automatically.
- **pollingperiod:** Time (ms) between system readings, lower makes it more responsive.
- **priority:** If several profiles are triggered, the one with the lower value gets selected.
- **templimit:** Temperature target (not yet implemented).
- **tdp_sutained, tdp_burst:** CPU sustained and burst TDP limits (PL1 & PL2) in Watt units, intel only.

intel_pstate driver only:
- **policy:** Energy performance preference.
- **minperf, maxfreq:** Performance percent range (recommended instead of minfreq/maxfreq).
  
**Important:** these options must be pre-fixed with either **ac_** or **bat_** to determine the charging situation in which the values should be set (use ac_ for desktop). It's also not necessary to specify every property for every additional profile, the unspecified ones will get filled in by the DEFAULT profile.

The DEFAULT profile is needed, and it will be created together with /etc/poweprlan.conf if the config file doesn't exist.
