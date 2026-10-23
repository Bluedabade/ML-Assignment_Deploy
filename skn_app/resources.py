"""Host/cgroup-aware guards calibrated from measured ~557–597MiB SKN process peaks."""
import os
from pathlib import Path
import sys

from .errors import AppError

MIB = 1024**2


def memory_snapshot():
    candidates = []
    details = {'host_available_bytes': None, 'cgroup_limit_bytes': None,
               'cgroup_used_bytes': None, 'process_rss_bytes': None,
               'cgroup_inactive_file_bytes': None, 'cgroup_dirty_file_bytes': None,
               'cgroup_writeback_bytes': None}
    if sys.platform == 'win32':
        import ctypes
        class Memory(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)]+[(n, ctypes.c_ulonglong) for n in
                ('physical', 'available', 'page', 'available_page', 'virtual', 'available_virtual', 'extended')]
        status = Memory();status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            candidates.append(status.available)
            details['host_available_bytes'] = status.available
    else:
        try:
            fields = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
            candidates.append(int(fields['MemAvailable'].split()[0])*1024)
            details['host_available_bytes'] = candidates[-1]
        except (OSError, KeyError, ValueError):
            pass
        for maximum, current in [('/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory.current'),
                                  ('/sys/fs/cgroup/memory/memory.limit_in_bytes', '/sys/fs/cgroup/memory/memory.usage_in_bytes')]:
            try:
                text = Path(maximum).read_text().strip()
                if text != 'max':
                    limit, used = int(text), int(Path(current).read_text())
                    if 0 < limit < 2**60:
                        candidates.append(max(0, limit-used))
                        if details['cgroup_limit_bytes'] is None or limit < details['cgroup_limit_bytes']:
                            details.update(cgroup_limit_bytes=limit, cgroup_used_bytes=used)
                            try:
                                stat_path = Path(current).parent/'memory.stat'
                                stat = dict(line.split() for line in stat_path.read_text().splitlines())
                                prefix = '' if maximum.endswith('memory.max') else 'total_'
                                details.update(cgroup_inactive_file_bytes=int(stat.get(prefix+'inactive_file','0')),
                                    cgroup_dirty_file_bytes=int(stat.get('file_dirty' if not prefix else 'total_dirty','0')),
                                    cgroup_writeback_bytes=int(stat.get('file_writeback' if not prefix else 'total_writeback','0')))
                            except (OSError, ValueError):
                                pass
            except (OSError, ValueError):
                pass
        try:
            details['process_rss_bytes'] = int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        except (OSError, ValueError, IndexError):
            pass
    details['available_bytes'] = min(candidates) if candidates else None
    return details


def available_memory():
    return memory_snapshot()['available_bytes']


def guard_memory(cold=False, video=False):
    # Cold: measured native peak plus ~170MiB headroom. Warm: bounded media scratch.
    # These are application budgets, not the unrelated 2GiB evaluation gate.
    required = (768 if cold else (192 if video else 128))*MIB
    available = available_memory()
    if available is None:
        raise AppError('RESOURCE_UNKNOWN')
    if available < required:
        raise AppError('RESOURCE_LIMITED')
    return {'available_bytes': available, 'required_bytes': required}
