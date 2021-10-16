import errno
from time import time
from pathlib import Path
from collections import deque
from abc import ABC, abstractmethod

import log
from shell import read, shell


class History(deque):
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


class PowerSupply(ABC):
    def __init__(self, path: Path = None):
        '''path: device's dir Path'''
        self.path = path
        self.name = path.name
        self.present = path is not None
        if self.present:
            self._set_paths()
        self._set_supplying_power_method()
        self.ENODEV_flag = False

    @abstractmethod
    def _set_paths(self):
        '''Sets up needed sysfs interfaces'''
        pass

    @abstractmethod
    def _present_supplying_power(self) -> bool:
        pass

    def _absent_supplying_power(self) -> None:
        return None

    def _set_supplying_power_method(self):
        '''Sets suppliying_power method, indended to run after subclass's __init__'''
        if self.present:
            self.supplying_power = self._present_supplying_power
        else:
            self.supplying_power = self._absent_supplying_power

    def _read(self, path, dtype=int):
        '''
        Reads data from path and parses as dtype
        Returns None if OS raises ENODEV (errno 19)
        '''
        try:
            return read(path, dtype)
        except OSError as err:
            if err.errno is errno.ENODEV:
                # https://github.com/torvalds/linux/blob/master/drivers/acpi/battery.c#L200
                # Kernel raises ENODEV when acpi battery values are unkown
                if not self.ENODEV_flag:
                    # Only warn once to avoid flooding logs
                    self.ENODEV_flag = True
                    log.log_warning(f'Kernel: ACPI_BATTERY_VALUE_UNKNOWN when reading {path}.')
                return None
            else:
                raise

    def _available(self, path: Path) -> bool:
        '''Check if path exists and returns values properly'''
        exists = path.exists()
        reading = self._read(path) if exists else None
        if exists and reading is None:
            log.log_info(f'Battery interface "{path.name}" detected but doesn\'t work.')
        return exists and reading is not None


class ACAdapter(PowerSupply):
    def _set_paths(self):
        self.online = self.path/'online'

    def _present_supplying_power(self) -> bool:
        online = self._read(self.online, str)
        if online is None:
            # Kernel ENODEV for some reason
            return None
        else:
            # AC adapter states: 0, 1, unknown
            if '1' in online:
                return True
            elif '0' in online:
                return False
            else:
                # Unknown ac state
                return None


class Battery(PowerSupply):
    def __init__(self, path):
        super().__init__(path)
        self.available_methods = self._available_power_methods()
        # set self.power_draw method
        self._set_power_draw_method()

    def _present_supplying_power(self):
        if self.present:
            # Possible values: "Unknown", "Charging", "Discharging", "Not charging", "Full"
            status = self._read(self.status, str)
            if status == 'Discharging':
                return True
            elif status in ['Charging', 'Not charging', 'Full']:
                return False
            else:
                return None
        else:
            return None

    def _set_paths(self):
        self.status = self.path/'status'
        self.capacity = self.path/'capacity'
        self.power_now = self.path/'power_now'
        self.energy_now = self.path/'energy_now'
        self.voltage_now = self.path/'voltage_now'
        self.current_now = self.path/'current_now'
        self.charge_now = self.path/'charge_now'

    def charge_left(self) -> int:
        '''Returns charge left (mAh)'''
        return self._read(self.charge_now)

    def energy_left(self) -> int:
        '''Returns energy left (mWh)'''
        return self._read(self.energy_now)

    # power_draw_methods
    def _available_power_methods(self) -> dict:
        '''Returns dict of available power draw estimation name:callable'''
        available_methods = dict()
        if self._available(self.power_now):
            available_methods['DirectRead'] = self._power_read
        if self._available(self.energy_now):
            available_methods['EnergyDelta'] = self._power_energy_delta
        if self._available(self.voltage_now):
            if self._available(self.current_now):
                available_methods['CurrentVoltage'] = self._power_current_voltage
            if self._available(self.charge_now):
                available_methods['ChargeDeltaVoltage'] = self._power_charge_delta_voltage

        log.log_info(f'Available power method(s): {available_methods}')
        return available_methods

    def _set_power_draw_method(self, method: str = None, history_len: int = 5):
        '''Sets power_draw method to the one specified'''
        if method is None:
            method = list(self.available_methods)[0]
        self.power_draw = self.available_methods[method]
        self.selected_power_method = method
        log.log_info(f'Power method selected: {method}')
        # Prepare history objs if needed
        if method == 'EnergyDelta':
            self.time_history = History(maxlen=history_len)
            self.energy_history = History(maxlen=history_len)
        elif method == 'ChargeDeltaVoltage':
            self.time_history = History(maxlen=history_len)
            self.charge_history = History(maxlen=history_len)

    def _power_read(self):
        power = self._read(self.power_now, int)  # µW
        if power is None:
            return power / 10**6
        else:
            return None

    def _power_energy_delta(self):
        read_time = time()
        energy = self._read(self.energy_now)  # mWh
        if energy is not None:
            # only update history if value changed
            if not self.energy_history or energy != self.energy_history[-1]:
                self.time_history.update(read_time)
                self.energy_history.update(energy)

            energy_delta = self.energy_history.delta()
            if energy_delta is None:
                return None
            else:
                return - energy_delta * 3.6 / self.time_history.delta()
        else:
            return None

    def _power_current_voltage(self):
        current = read(self.current_now, int)  # µA
        voltage = read(self.voltage_now, int)  # µV
        if current is None or voltage is None:
            return None
        else:
            return current * voltage / 10**12

    def _power_charge_delta_voltage(self):
        read_time = time()
        charge = self._read(self.charge_now)
        if charge is not None:
            # only update history if value changed
            if not self.charge_history or charge != self.charge_history[-1]:
                self.time_history.update(read_time)
                self.charge_history.update(charge)

            voltage = self._read(self.voltage_now, int)  # µV
            charge_delta = self.charge_history.delta()   # mAh
            if voltage is None or charge_delta is None:
                return None
            else:
                current = - charge_delta * 3.6 / self.time_history.delta()  # mA
                return current * voltage / 10**9
        else:
            return None


def power_supply_detection() -> tuple:
    '''Returns tuple of ACAdapter, Battery'''
    power_supply_dir = Path('/sys/class/power_supply/')
    # /type values: "Battery", "UPS", "Mains", "USB", "Wireless"

    # AC detection
    for dev_type in power_supply_dir.glob('A*/type'):
        # If type Mains and needed interface exists stop looking
        if read(dev_type) == 'Mains' and dev_type.with_name('online').exists():
            ac_path = Path(dev_type).parent
            break
    else:
        ac_path = None

    # Batery detection
    for dev_type in power_supply_dir.glob('BAT*/type'):
        # If type Battery and needed interface exists stop looking
        if read(dev_type) == 'Battery' and dev_type.with_name('status').exists():
            bat_path = Path(dev_type).parent
            break
    else:
        bat_path = None

    # Log
    if ac_path is not None:
        log.log_info(f'AC-adapter detected: {ac_path.name}')
    if bat_path is not None:
        log.log_info(f'Battery detected: {bat_path.name}')

    return ACAdapter(ac_path), Battery(bat_path)


def charging() -> bool:
    ''' Is battery charging? Deals with unavailable bat OR ac-adapter info.'''

    if AC is not None:
        # AC adapter states: 0, 1, unknown
        ac_data = AC.read_text()
        if '1' in ac_data:
            # at least one online ac adapter
            return True
        elif '0' in ac_data:
            # at least one offline ac adapter
            ac_state = False
        else:
            # Unknown ac state
            ac_state = None
    else:
        ac_state = None

    if BAT is not None:
        # Possible values: "Unknown", "Charging", "Discharging", "Not charging", "Full"
        battery_data = BAT.read_text()
        if "Discharging" in battery_data:
            battery_state = False
        elif "Charging" in battery_data:
            return True
        else:
            battery_state = None
    else:
        battery_state = None

    # At this point both ac and bat state can only be False or None
    if False in [ac_state, battery_state]:
        return False
    else:
        # both ac-adapter and battery states are unknown charging == True
        # Desktop computers should fall in this case
        return True


def tree() -> str:
    return shell('grep . /sys/class/power_supply/*/* -d skip')


#  Globals
AC, BAT = power_supply_detection()

if __name__ == '__main__':
    print(tree())
