import os
from glob import glob

import config


class ProcessReader:
    '''
    Keeps track of previously found pids and avoids re-reading those
    comm files if not of interest
    '''

    def __init__(self, profiles=None, max_retries=5):
        self.triggerapps_found = set()
        self.pid_names = dict()
        self.pid_last = 0
        self.max_retries = max_retries
        self.update_triggerapps(profiles)
        self.update()

    def update(self):
        # ensure previously identified pids are checked
        comms = [f'/proc/{pid}/comm' for pid in self.pid_names]
        for i in range(self.max_retries):
            try:
                comms += sorted(glob('/proc/[0-9]*/comm'), key=os.path.getmtime)
            except FileNotFoundError:
                # procs can come and go very quickly, this is expected
                continue
            else:
                break

        for comm in comms:
            pid = int(comm.split('/')[2])
            if pid not in self.pid_names and pid <= self.pid_last:
                # need to check for pid_max
                continue
            try:
                with open(comm, 'r') as file:
                    proc_name = file.readline().strip()
                    if proc_name in self.triggerapps:
                        self.pid_names[pid] = proc_name
            except FileNotFoundError:
                # process exited before being read
                if pid in self.pid_names:
                    _ = self.pid_names.pop(pid)

        self.pid_last = pid
        self.triggerapps_found = set(self.pid_names.values())

    def update_triggerapps(self, profiles):
        '''Updates self.triggerapps, useful for hot-reloading profiles'''
        self.triggerapps = self._get_triggerapps(profiles)

    def _get_triggerapps(self, profiles=None) -> set:
        if profiles is None:
            profiles = config.read_profiles()
        triggerapps = set()
        for profile_name in profiles:
            triggerapps.update([p[:15] for p in profiles[profile_name].triggerapps])
        return triggerapps

    def triggered_profile(self, profiles) -> config.CpuProfile:
        '''Returns triggered CpuProfile object according to running processes'''
        # Check running processes
        if self.triggerapps:
            self.update()

            # check profile trigger apps against procs
            for cpuprofile in profiles.values():
                if cpuprofile.triggerapp_present(self.triggerapps_found):
                    return cpuprofile
            else:
                return profiles['DEFAULT']
        else:
            return profiles['DEFAULT']
