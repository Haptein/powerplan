import csv
import platform
import subprocess
from datetime import datetime
from time import time, sleep
from multiprocessing import Pool

import psutil

import cpu
from cpu import CPU, RAPL

VERSION = '0.2'

# Information display

SYSTEM_INFO = f'''
    System
    OS:\t\t\t{platform.platform()}
    cpuauto:\t\t{VERSION} running on Python{platform.python_version()}
    CPU model:\t\t{CPU['name']}
    Core configuraton:\t{CPU['physical_cores']}/{len(cpu.list_cores())}\
    {' '.join([f"{sib[0]}-{sib[1]}" for sib in CPU['thread_siblings']])}
    Frequency range:\t{CPU['freq_info']}
    Driver:\t\t{CPU['scaling_driver']}
    Governors:\t\t{', '.join(CPU['governors'])}
    Policies:\t\t{', '.join(CPU['policies'])}

    Paths
    Turbo:\t\t{CPU['turbo_path']}
    AC adapter:\t\t{CPU['ac_path'].parent}
    Battery:\t\t{CPU['bat_path'].parent}
    Power method:\t{CPU['power_reading_method']}
'''


def show_system_status(profile, monitor_mode=False):
    '''Prints System status during runtime'''

    charging = cpu.read_charging_state()
    time_now = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    active_profile = f'{time_now}\t\tActive: {profile.name}'
    power_plan = f'Power plan: {cpu.read_governor()}/{cpu.read_policy()}'
    power_status = f'Charging: {charging}\t\tBattery draw: {cpu.read_power_draw():.1f}W'
    if RAPL.enabled:
        power_status += f'\tPackage: {RAPL.read_power():.2f}W'

    cores_online = cpu.list_cores('online')
    num_cores_online = len(cores_online)
    # Per cpu stats
    cpus = '\t'.join(['CPU'+str(coreid) for coreid in cpu.list_cores('online')])
    utils = '\t'.join([str(util) for util in psutil.cpu_percent(percpu=True)])

    # Read current frequencies in MHz
    freq_list = cpu.read_current_freq(divisor=1000).values()
    avg_freqs = int(sum(freq_list)/num_cores_online)
    freqs = '\t'.join([str(freq) for freq in freq_list])

    # CPU average line
    cpu_cores_turbo = '\t'.join([f'Cores online: {num_cores_online}',
                                 f"Turbo: {'enabled' if cpu.read_turbo_state() else 'disabled'}"])

    cpu_avg = '\t'.join([f"Avg. Usage: {cpu.read_cpu_utilization('avg')}%",
                         f"Avg. Freq.: {avg_freqs}MHz",
                         f'Package temp: {cpu.read_temperature()}°C'])

    monitor_mode_indicator = '[MONITOR MODE]' if monitor_mode else ''
    status_lines = ['',
                    active_profile,
                    power_plan,
                    power_status,
                    cpu_cores_turbo,
                    cpu_avg,
                    '',
                    cpus,
                    utils,
                    freqs]

    subprocess.run('clear')
    print(monitor_mode_indicator)
    print(SYSTEM_INFO)
    print('\n'.join(status_lines))


def debug_power_info():
    # POWER SUPPLY TREE
    power_supply_info = cpu.shell('grep . /sys/class/power_supply/*/* -d skip')
    [print('/'.join(info.split('/')[4:])) for info in power_supply_info.splitlines()]


# CPU power / performance profiling

class Status:
    def __init__(self, name_suffix=''):
        self.cores_online = len(cpu.list_cores('online'))
        self.charging_state = cpu.read_charging_state()
        self.time = []
        self.avg_util = []
        self.avg_freq = []
        self.package_temp = []
        self.package_power = []
        self.battery_power = []
        self.freq_lim = []
        self.max_freq = []
        self.running_threads = []
        self.rapl = cpu.Rapl()
        gov, pol = cpu.read_governor(), cpu.read_policy()
        self.name_suffix = name_suffix + gov + pol

    def update(self, running_threads=None):
        freq_list = cpu.read_current_freq(divisor=1000).values()
        self.time.append(time())
        self.avg_util.append(cpu.read_cpu_utilization('avg'))
        self.avg_freq.append(int(sum(freq_list)/self.cores_online))
        self.package_temp.append(cpu.read_temperature())
        self.package_power.append(self.rapl.read_power())
        self.battery_power.append(cpu.read_power_draw())
        self.freq_lim.append(cpu.read_datafile(cpu.CPUFREQ_DIR + 'scaling_max_freq', dtype=int)/1000)
        self.max_freq.append(max(freq_list))
        self.running_threads.append(running_threads)

    def display(self):
        print(f'{self.avg_util[-1]:3.1f}%\tAvg:{self.avg_freq[-1]}MHz\tPkg:{self.package_power[-1]:2.2f}W  {self.package_temp[-1]:3.2f}°C    ')

    def save(self):
        file_name = f'cores:{self.cores_online}_charging:{self.charging_state}{self.name_suffix}.csv'
        self.time = [t-self.time[0] for t in self.time]
        with open(file_name, 'w', newline='') as file:
            writer = csv.writer(file, delimiter=',')
            writer.writerow(['time', 'freq_lim', 'max_freq', 'avg_freq',
                             'avg_util', 'package_power', 'battery_power', 'package_temp'])
            writer.writerows(list(zip(self.time, self.running_threads, self.freq_lim, self.max_freq, self.avg_freq,
                                      self.avg_util, self.package_power, self.battery_power, self.package_temp)))

def fudgel(n):
    while True:
        _ = eval("""'Help me! I can\\'t stop D='""")

def profile_system(threads: list = [1, 2, 4, 6], T=0.2, step_time=10, step_freq=100_000, resting_temp=46):
    # Setup
    minfreq = cpu.CPU['minfreq']
    maxfreq = cpu.CPU['maxfreq']
    freq_steps = list(range(minfreq, maxfreq, step_freq))
    if maxfreq not in freq_steps:
        freq_steps.append(maxfreq)
    status = Status(name_suffix=f'_stress:{threads}')

    # maybe include a pre warmup routine here
    try:  # KeyboardInterruptable
        for n_threads in threads:

            # Reach resting temp
            temp = cpu.read_temperature()
            while temp > resting_temp:
                print(f'Waiting for temp to reach {resting_temp}°C, current:{temp:.2f}°C')
                freq_iter_start = time()
                # Sampling period, record cooling down period
                while time()-freq_iter_start < step_time:
                    iter_start = time()
                    status.update(running_threads=0)
                    sleep_time = T - time() + iter_start
                    if sleep_time > 0:
                        sleep(sleep_time)
                temp = cpu.read_temperature()

            # Begin stressing
            pool = Pool(n_threads)
            pool.map_async(fudgel, range(n_threads), callback=lambda: print(1))

            # Frequency sweep
            for freq in freq_steps:
                cpu.set_freq_range(cpu.CPU['minfreq'], freq)
                freq_iter_start = time()
                # Sampling period
                while time()-freq_iter_start < step_time:
                    iter_start = time()
                    status.update(running_threads=n_threads)
                    sleep_time = T - time() + iter_start
                    if sleep_time > 0:
                        sleep(sleep_time)
                status.display()
            pool.terminate()

    except KeyboardInterrupt:
        pool.terminate()
    status.save()


if __name__ == '__main__':
    profile_system(threads=[1, 3, 6, 12])