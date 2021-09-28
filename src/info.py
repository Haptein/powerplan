import csv
import platform
import subprocess
from pathlib import Path
from datetime import datetime
from time import time, sleep
from multiprocessing import Pool

import psutil

import shell
import cpu
import powersupply
from cpu import CPU, RAPL

VERSION = '0.4'

# Information display

SYSTEM_INFO = f'''
    System
    OS:\t\t\t{platform.platform()}
    cpuauto:\t\t{VERSION} running on Python{platform.python_version()}
    CPU model:\t\t{CPU.name}
    Core configuraton:\t{CPU.physical_cores}/{CPU.logical_cores}\
    {' '.join([f"{sib[0]}-{sib[1]}" for sib in CPU.thread_siblings])}
    Frequency range:\t{" - ".join([str(freq) for freq in (CPU.minfreq, CPU.basefreq, CPU.maxfreq) if freq])} KHz
    Driver:\t\t{CPU.driver}
    Turbo:\t\t{CPU.turbo_path}
    Governors:\t\t{', '.join(CPU.governors)}
    Policies:\t\t{', '.join(CPU.policies)}
    AC adapter:\t\t{powersupply.AC.parent.name}
    Battery:\t\t{powersupply.BAT.parent.name}
    Power method:\t{powersupply.POWER_READING_METHOD}
'''


def show_system_status(profile, monitor_mode=False):
    '''Prints System status during runtime'''

    time_now = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    active_profile = f'{time_now}\t\tActive: {profile.name}'
    power_plan = f'Power plan: {cpu.read_governor()}/{cpu.read_policy()}'
    power_status = f'Charging: {powersupply.charging()}\t\tBattery draw: {powersupply.power_draw():.1f}W'
    if RAPL.enabled:
        power_status += f'\tPackage: {RAPL.read_power():.2f}W'

    cores_online = cpu.list_cores('online')
    num_cores_online = len(cores_online)
    # Per cpu stats
    cpus = '\t'.join(['CPU'+str(coreid) for coreid in cpu.list_cores('online')])
    utils = '\t'.join([str(util) for util in psutil.cpu_percent(percpu=True)])

    # Read current frequencies in MHz
    freq_list = cpu.read_current_freq().values()
    avg_freqs = int(sum(freq_list)/num_cores_online)
    freqs = '\t'.join([str(freq) for freq in freq_list])

    # CPU average line
    cpu_cores_turbo = '\t'.join([f'Cores online: {num_cores_online}',
                                 f"Turbo: {'enabled' if cpu.read_turbo_state() else 'disabled'}"])

    cpu_avg = '\t'.join([f"Avg. Usage: {cpu.read_cpu_utilization('avg')}%",
                         f'Avg. Freq.: {avg_freqs}MHz',
                         f'Package temp: {cpu.read_temperature()}°C'])

    monitor_mode_indicator = '[MONITOR MODE]' if monitor_mode else '[ACTIVE MODE]'
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
    power_supply_tree = powersupply.tree()
    [print('/'.join(info.split('/')[4:])) for info in power_supply_tree.splitlines()]
    print(f'Present temperature sensors: {list(psutil.sensors_temperatures())}')

def read_process_cpu_mem(process):
    return process.cpu_percent(), process.memory_percent()

def debug_runtime_info(process, profile, iteration_start):
    cpuauto_util, cpuauto_mem = read_process_cpu_mem(process)
    time_iter = (time() - iteration_start) * 1000  # ms
    print(f'Process resources: CPU {cpuauto_util:.2f}%, Memory {cpuauto_mem:.2f}%, Time {time_iter:.3f}ms')

# CPU power / performance profiling

class Status:
    def __init__(self, name_suffix=''):
        self.cores_online = len(cpu.list_cores('online'))
        self.charging_state = powersupply.charging()
        self.time = []
        self.avg_util = []
        self.avg_freq = []
        self.package_temp = []
        self.package_power = []
        self.core_power = []
        self.battery_power = []
        self.freq_lim = []
        self.max_freq = []
        self.running_threads = []
        self.intelrapl = cpu.IntelRapl()
        gov, pol = cpu.read_governor(), cpu.read_policy()
        self.name_suffix = name_suffix + gov + pol

    def update(self, running_threads=None):
        freq_list = cpu.read_current_freq().values()
        self.time.append(time())
        self.avg_util.append(cpu.read_cpu_utilization('avg'))
        self.avg_freq.append(int(sum(freq_list)/self.cores_online))
        self.package_temp.append(cpu.read_temperature())
        self.package_power.append(self.intelrapl.read_power())
        self.core_power.append(self.intelrapl.read_power('core'))
        self.battery_power.append(powersupply.power_draw())
        self.freq_lim.append(shell.read(cpu.CPUFREQ_DIR + 'scaling_max_freq', dtype=int)/1000)
        self.max_freq.append(max(freq_list))
        self.running_threads.append(running_threads)

    def display(self):
        print(f'{self.avg_util[-1]:3.1f}%\tAvg:{self.avg_freq[-1]}MHz\t'
              f'Pkg:{self.package_power[-1]:2.2f}W  {self.package_temp[-1]:3.2f}°C')

    def save(self):
        file_name = f'cores:{self.cores_online}_charging:{self.charging_state}{self.name_suffix}.csv'
        self.time = [t-self.time[0] for t in self.time]
        with open(file_name, 'w', newline='') as file:
            writer = csv.writer(file, delimiter=',')
            header = ['time', 'running_threads', 'freq_lim', 'max_freq', 'avg_freq', 'avg_util',
                      'package_power', 'core_power', 'battery_power', 'package_temp']
            data = list(zip(self.time, self.running_threads, self.freq_lim, self.max_freq, self.avg_freq, self.avg_util,
                            self.package_power, self.core_power, self.battery_power, self.package_temp))
            writer.writerow(header)
            writer.writerows(data)

def fudgel(n):
    while True:
        _ = eval('"Help me! I can\'t stop D="')

def profile_system(threads: list = [1], T=0.5, step_time=5, step_freq=100_000, resting_temp=46):
    # Setup
    print(f'Power Plan: {cpu.read_governor()} {cpu.read_policy()}\n')
    # Print tdp limits maybe

    minfreq = CPU.minfreq
    maxfreq = CPU.maxfreq
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
                cpu.set_freq_range(CPU.minfreq, freq)
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


# Bench
def fudgel_n_times(n):
    for i in range(n):
        _ = eval('"Help me! I can\'t stop D="')

def bench_freq_lim(freq_lim: int, n_iter: int = 1000):
    # Start vars
    cpu.set_freq_range(min_freq=CPU.minfreq, max_freq=freq_lim*1000)  # in MHz
    time_start = time()
    charge_start = powersupply.charge_left()
    # Work
    fudgel_n_times(n_iter)
    # End vars
    time_end = time()
    charge_end = powersupply.charge_left()
    time_delta = time_end - time_start
    charge_delta = charge_end - charge_start
    result = str(f'freq_lim:{freq_lim:5}\tTime elapsed: {time_delta:.3f}s, Charge consumed: {charge_delta}mAH')
    print(result)
    return result

def bench_freqs(freqs: list, n_iter: int, output='output.txt'):
    output_path = Path(output)
    power_plan = f'Settings: {cpu.read_governor()} {cpu.read_policy()}\n'
    output_path.write_text(power_plan)
    for freq in freqs:
        results = bench_freq_lim(freq, n_iter)
        with output_path.open('a') as file:
            file.write(results + '\n')
        sleep(1)


if __name__ == '__main__':
    debug_power_info()
    exit()
    # profile_system(threads=[1, 3, 6, 12])
    freqs = range(int(CPU.minfreq/1000), int(CPU.maxfreq/1000), 200)
    bench_freqs(freqs, 20_000_000)
