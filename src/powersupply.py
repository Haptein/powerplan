from glob import glob
from pathlib import Path

from shell import read_datafile, shell

POWER_DIR = '/sys/class/power_supply/'


def power_supply_detection() -> tuple:
    '''Returns tuple of ac_device_path, bat_device_path, power_path'''

    # /type values: "Battery", "UPS", "Mains", "USB", "Wireless"
    ac_devices = glob(f'{POWER_DIR}A*/type')
    for ac in ac_devices:
        if read_datafile(ac) == 'Mains':
            ac_device_path = Path(ac).with_name('online')
            if ac_device_path.exists():
                break
    else:
        ac_device_path = None

    bat_devices = glob(f'{POWER_DIR}BAT*/type')
    for bat in bat_devices:
        if read_datafile(bat) == 'Battery':
            bat_device_path = Path(bat).with_name('status')
            if bat_device_path.exists():
                break
    else:
        bat_device_path = None

    return ac_device_path, bat_device_path


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


def charge_left() -> int:
    '''Returns battery charge left (mAH)'''
    charge_now = BAT.with_name('charge_now')
    if charge_now.exists():
        return read_datafile(charge_now, int)
    else:
        return -1


def power_reading_method(bat_device_path=None):
    '''
    Tests possible power reading paths
    returns ['power', 'current_and_voltage', None]
    '''
    if bat_device_path is None:
        return None
    power_now_path = bat_device_path.with_name('power_now')
    current_now_path = bat_device_path.with_name('current_now')
    voltage_now_path = bat_device_path.with_name('voltage_now')
    if power_now_path.exists():
        return 'power'
    elif current_now_path.exists() and voltage_now_path.exists():
        return 'current_and_voltage'
    else:
        return None


def power_draw():
    '''Returns battery power draw in Watt units'''
    if POWER_READING_METHOD == 'power':
        power_data = BAT.with_name('power_now').read_text()
        return float(power_data) / 10**6
    elif POWER_READING_METHOD == 'current_and_voltage':
        current_data = BAT.with_name('current_now').read_text()
        voltage_data = BAT.with_name('voltage_now').read_text()
        return float(current_data) * float(voltage_data) / 10**12
    else:
        return -1


def tree() -> str:
    return shell('grep . /sys/class/power_supply/*/* -d skip')


#  Globals
AC, BAT = power_supply_detection()
POWER_READING_METHOD = power_reading_method(BAT)

if __name__ == '__main__':
    print(AC, BAT, POWER_READING_METHOD)
    print(tree())

# Checks#############
#if POWER_READING_METHOD is None:
#    log.log_info('No power reading method available.')