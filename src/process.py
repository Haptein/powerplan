from glob import glob

import shell
import config


class ProcessReader:
    '''
    Keeps track of previously found pids and avoids re-reading those
    comm files if not of interest
    '''

    def __init__(self, profiles=None):
        self.triggerapps = self._get_triggerapps(profiles)
        self.triggerapps_found = set()
        self.profiles = profiles
        self.pid_names = dict()
        self.pids_last = set()
        self.update()

    def update(self):
        # ensure previously identified pids are checked
        pids_new = set()
        comms = glob('/proc/[0-9]*/comm')
        for comm in comms + [f'/proc/{pid}/comm' for pid in self.pid_names]:
            pid = int(comm.split('/')[2])

            # If pid was seen last time but wasn't of interest
            if pid in self.pids_last and pid not in self.pid_names:
                pids_new.add(pid)
                continue

            try:
                with open(comm, 'r') as file:
                    proc_name = file.readline().strip()
                    if proc_name in self.triggerapps:
                        self.pid_names[pid] = proc_name
            except (FileNotFoundError, ProcessLookupError):
                # FileNotFoundError : process exited before being read
                # ProcessLookupError: process exited while being open, before readline()
                if pid in self.pid_names:
                    _ = self.pid_names.pop(pid)
            else:
                pids_new.add(pid)

        self.pids_last = pids_new
        self.triggerapps_found = set(self.pid_names.values())

    def reset(self, profiles):
        '''
        Updates self.triggerapps and clears self.pids_last
        useful for hot-reloading profiles
        '''
        self.__init__(profiles=profiles)

    def _get_triggerapps(self, profiles=None) -> set:
        if profiles is None:
            profiles = config.read_profiles()
        triggerapps = set()
        for profile_name in profiles:
            triggerapps.update([p[:15] for p in profiles[profile_name].triggerapps])
        return triggerapps

    def triggered_profile(self) -> config.PowerProfile:
        '''Returns triggered PowerProfile object according to running processes'''
        # Check running processes
        if self.triggerapps:
            self.update()

            # check profile trigger apps against procs
            for profile in self.profiles.values():
                if profile.triggerapp_present(self.triggerapps_found):
                    return profile
            else:
                return self.profiles['DEFAULT']
        else:
            return self.profiles['DEFAULT']


def already_running(name: str = 'powerplan') -> bool:
    process_instances = shell.shell("grep -sh . /proc/[0-9]*/comm").splitlines().count(name)
    return process_instances > 1
