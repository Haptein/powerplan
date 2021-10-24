import subprocess
from time import time

import psutil
from systemstatus import System, SystemStatus

def show_system_status(system: System, status: SystemStatus, monitor_mode: bool):
    '''Prints System status during runtime'''
    cpu = system.cpu
    cpu_spec = system.cpu.spec

    time_now = status['time_stamp']
    active_profile = f'{time_now}\t\tActive: {status["triggered_profile"].name}'

    # governor/policy
    governor = status['governor']
    policy = '/'+status['policy'] if cpu_spec.policies else ''
    power_plan = f'Power plan: {governor+policy}'

    # power
    ac_power = status['ac_power']
    power_source = 'AC'+' '*5 if ac_power else 'Battery'
    power_draw = status['battery_draw']
    if (ac_power or power_draw is None):
        power_draw_repr = 'N/A '
    else:
        power_draw_repr = f'{power_draw:.1f}W'

    power_status = f'Power source: {power_source}\tBattery draw: {power_draw_repr}'

    if status['package_power']:
        power_status += f'\tPackage: {status["package_power"]:.2f}W'

    cores_online = status['cores_online']
    num_cores_online = len(cores_online)
    # Per cpu stats
    cpus = '\t'.join(['CPU'+str(coreid) for coreid in cores_online])
    utils = '\t'.join([str(util) for util in psutil.cpu_percent(percpu=True)])

    # Read current frequencies in MHz
    freq_list = status['frequency'].values()
    avg_freqs = int(sum(freq_list)/num_cores_online)
    freqs = '\t'.join([str(freq) for freq in freq_list])

    # CPU average line
    cpu_cores_turbo = '\t'.join([f'Cores online: {num_cores_online} ',
                                 f"Turbo: {'enabled' if status['turbo'] else 'disabled'}"])

    cpu_avg = '\t'.join([f"Avg. Usage: {cpu.read_cpu_utilization('avg')}%",
                         f'Avg. Freq.: {avg_freqs}MHz',
                         f'Package temp: {status["package_temp"]}°C'])

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
    print(system.info)
    print(*status_lines, sep='\n')

def read_process_cpu_mem(running_process):
    return running_process.cpu_percent(), running_process.memory_percent()

def debug_runtime_info(process, profile, iteration_start):
    process_util, process_mem = read_process_cpu_mem(process)
    time_iter = (time() - iteration_start) * 1000  # ms
    print(f'Process resources: CPU {process_util:.2f}%, Memory {process_mem:.2f}%, Time {time_iter:.3f}ms')


if __name__ == '__main__':
    debug_power_info()
