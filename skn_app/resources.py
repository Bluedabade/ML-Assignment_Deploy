"""Host/cgroup-aware guards calibrated from measured ~557–597MiB SKN process peaks."""
import os
from pathlib import Path
import sys

from .errors import AppError

MIB = 1024**2


def available_memory():
    candidates = []
    if sys.platform == 'win32':
        import ctypes
        class Memory(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)]+[(n, ctypes.c_ulonglong) for n in
                ('physical', 'available', 'page', 'available_page', 'virtual', 'available_virtual', 'extended')]
        status = Memory();status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            candidates.append(status.available)
    else:
        try:
            fields = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
            candidates.append(int(fields['MemAvailable'].split()[0])*1024)
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
            except (OSError, ValueError):
                pass
    return min(candidates) if candidates else None


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
