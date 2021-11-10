import csv
import platform
from time import time
from statistics import mean
from collections import deque
from datetime import datetime
import psutil

import log
from cpu import Cpu
from __init__ import __version__
from process import ProcessReader

def time_stamp():
    return datetime.now().strftime('%H:%M:%S.%f')[:-3]

class System:
    def __init__(self, cpu: Cpu, powersupply):
        self.cpu = cpu
        self.powersupply = powersupply
        self.info = self.system_info(self.cpu.spec, self.powersupply)

    def system_info(self, cpuspec, powersupply) -> str:
        '''Generate system info string'''
        # Variable string, None's will get filtered out
        info = ('\n'+' '*4).join(filter(None, (
            ' '*4+'System',
            f'OS:\t\t\t{platform.platform()}',
            f'powerplan:\t\t{__version__} running on Python{platform.python_version()} with psutil{psutil.__version__}',
            f'CPU model:\t\t{cpuspec.name}',
            f'Core configuraton:\t{cpuspec.physical_cores}/{cpuspec.logical_cores}  {cpuspec.sibling_cores_repr}',
            f'Frequency range:\t{cpuspec.freq_range_repr}',
            f'Driver:\t\t{cpuspec.driver_repr}',
            f'Turbo:\t\t{cpuspec.turbo_path}',
            f'Governors:\t\t{cpuspec.governors_repr}',
            f'Policies:\t\t{cpuspec.policies_repr}' if cpuspec.policies else None,
            f'Temperature:\t{cpuspec.temp_sensor_repr}',
            f'AC adapter:\t\t{powersupply.ac_adapter.name}' if powersupply.ac_adapter.name else None,
            f'Battery:\t\t{powersupply.battery.name}' if powersupply.battery.name else None
        )))
        return info


class History(deque):
    '''
    A double ended queue with methods for streaming data,
    change detection and delta computation
    '''
    def __init__(self, maxlen=2):
        super().__init__(maxlen=maxlen)

    def update(self, value):
        '''Stream value into deque'''
        if self.__len__() == self.maxlen:
            _ = self.popleft()
            self.append(value)
        else:
            self.append(value)

    def delta(self):
        '''Returns the difference between the last and first value'''
        if self.__len__() > 1:
            return self[-1] - self[0]
        else:
            return None

    def changed(self) -> bool:
        '''Returns true if field's last value is different from the second last one'''
        if self.__len__() > 1:
            return self[-1] != self[-2]
        else:
            return None


class SystemStatus():

    def __init__(self, system: System, profiles: dict,
                 fields: list, custom_fields: dict = None, history_len=2):
        '''
        Initializes dict of deques of length history_len
        '''
        assert history_len > 0 or history_len is None
        # Hardware components
        self.system = system
        self.cpu: Cpu = system.cpu
        self.rapl = system.cpu.rapl
        self.powersupply = system.powersupply
        self.battery = system.powersupply.battery
        self.process_reader = ProcessReader(profiles=profiles)
        # Setup fields' history objects
        self._check_custom_fields(custom_fields)
        self.field_methods = self._get_field_methods(fields=fields, custom_fields=custom_fields)
        self.fields = set(self.field_methods.keys())
        self.history = {field: History(maxlen=history_len) for field in self.field_methods}
        self.history_len = history_len
        self.partially_updated = set()

    def __getitem__(self, field):
        '''Get latest value of field'''
        assert field in self.fields
        return self.history[field][-1]

    def _check_custom_fields(self, custom_fields: dict):
        '''
        check that custom fields are correct
        '''
        if custom_fields is None:
            return
        if type(custom_fields) is not dict:
            log.error('custom_fields must be of type dict.')
        for key in custom_fields:
            value = custom_fields[key]
            if (type(value) is not tuple) or (len(value) != 2) or (not callable(value[1])):
                log.error(f'Value of {key} in custom_fields must be a tuple of length 2 (name, callable).')
            if type(value[0]) is not str:
                log.error('Keys in custom_fields must be of type str.')

    def _get_field_methods(self, fields: list, custom_fields: dict) -> dict:
        # dict{field:(function, kwargs)}
        builtin_fields = dict(
            time=(time, {}),
            time_stamp=(time_stamp, {}),
            triggered_profile=(self.process_reader.triggered_profile, {}),
            # Battery
            ac_power=(self.powersupply.ac_power, {}),
            battery_draw=(self.battery.power_draw, {}),
            battery_charge_left=(self.battery.charge_left, {}),
            battery_energy_left=(self.battery.energy_left, {}),
            # RAPL
            package_temp=(self.cpu.read_temperature, {}),
            package_power=(self.rapl.read_power, {}),
            core_power=(self.rapl.read_power, {'name': 'core'}),
            dram_power=(self.rapl.read_power, {'name': 'dram'}),
            uncore_power=(self.rapl.read_power, {'name': 'uncore'}),
            # Configurables
            frequency=(self.cpu.read_current_freq, {}),
            governor=(self.cpu.read_governor, {}),
            policy=(self.cpu.read_policy, {}),
            cores_online=(self.cpu.list_cores, {'status': 'online'}),
            turbo=(self.cpu.read_turbo_state, {}),
            cpu_util_all=(self.cpu.read_cpu_utilization, {'mode': 'all'}),
            cpu_util_avg=(self.cpu.read_cpu_utilization, {'mode': 'avg'}),
            cpu_util_max=(self.cpu.read_cpu_utilization, {'mode': 'max'}),
            # Split read freq range in min and max
            frequency_range_max=(lambda: self.cpu.read_freq_range()[1], {}),
            frequency_avg=(lambda: int(mean(self.cpu.read_current_freq().values())), {}),
            frequency_max=(lambda: int(max(self.cpu.read_current_freq().values())), {})
        )

        field_methods = {key: builtin_fields[key] for key in builtin_fields if key in fields}
        if custom_fields is not None:
            field_methods.update(custom_fields)
        return field_methods

    def reset(self, profiles=None):
        '''Resets internal processReader, needed for hot reloading'''
        if profiles is not None:
            self.process_reader.reset(profiles)
        self.partially_updated = set()

    def update(self):
        '''
        Updates all fielfds' history
        '''
        for key in self.history:
            func, kwargs = self.field_methods[key]
            self.history[key].update(func(**kwargs))
        self.partially_updated = set()

    def partial_update(self, fields: list = None):
        '''
        Updates specified fields' values
        if fields==None, updates all the fields that haven't been partially updated
        '''
        # Default updates all fields not updated
        if fields is None:
            fields = [field for field in self.history if field not in self.partially_updated]
            self.partially_updated = set()
        else:
            self.partially_updated.update(fields)
            if self.partially_updated == self.fields:
                self.partially_updated = set()

        # Update status of fields
        for key in fields:
            func, kwargs = self.field_methods[key]
            self.history[key].update(func(**kwargs))

    def manual_partial_update(self, field_values: dict):
        '''Updates fields' with provided values'''
        assert all([key in self.history for key in field_values])
        for key, value in field_values.items():
            self.history[key].update(value)
        # Update partially updated set and reset it if al fields have been updated
        self.partially_updated.update(field_values.keys())
        if self.partially_updated == self.fields:
            self.partially_updated = set()

    def changed(self, fields: list = None) -> bool:
        '''
        Returns true if at least one field's last value is different from the second last one
        '''
        if fields is None:
            return any([self.history[field].changed() for field in self.field_methods])
        else:
            return any([self.history[field].changed() for field in fields])

    def query(self, field):
        '''
        Return latest value in history of field
        '''
        field_history = self.history[field]
        if field_history:
            return field_history[-1]
        else:
            return None

    def save(self, file_name: str):
        '''
        Saves history as a CSV file
        '''
        with open(file_name, 'w', newline='') as file:
            writer = csv.writer(file, delimiter=',')
            # Write header
            writer.writerow(self.history.keys())
            # and data
            writer.writerows(zip(*self.history.values()))

class StatusMinimal(SystemStatus):
    def __init__(self, system: System, profiles: dict):
        fields = ('triggered_profile', 'ac_power')
        super().__init__(system, profiles, fields)

class StatusMonitor(SystemStatus):
    def __init__(self, system: System, profiles: dict):
        fields = ['time_stamp',
                  'frequency',
                  'triggered_profile',
                  'ac_power',
                  'governor',
                  'policy',
                  'cores_online',
                  'turbo',
                  'package_power',
                  'battery_draw',
                  'package_temp']
        super().__init__(system, profiles, fields)

class StatusLog(SystemStatus):
    def __init__(self, system: System, profiles: dict):
        fields = ['time',
                  'cores_online',
                  'frequency',
                  'ac_power',
                  'governor',
                  'policy',
                  'cores_online',
                  'turbo',
                  'package_power',
                  'battery_draw',
                  'package_temp']
        super().__init__(system, profiles, fields)
