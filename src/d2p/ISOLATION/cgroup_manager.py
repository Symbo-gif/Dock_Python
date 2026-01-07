# Copyright 2024 Michael Maillet, Damien Davison, Sacha Davison
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Linux cgroup v2 management for resource limits.
Provides CPU, memory, and I/O resource constraints.
"""

import os
import sys
from typing import Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ResourceLimits:
    """Resource limits for a container."""
    # CPU limits
    cpu_shares: Optional[int] = None  # Relative CPU weight (1-10000)
    cpu_quota: Optional[int] = None   # CPU quota in microseconds per period
    cpu_period: int = 100000          # CPU period in microseconds (default 100ms)
    cpus: Optional[float] = None      # Number of CPUs (e.g., 0.5 = half a CPU)
    
    # Memory limits
    memory_limit: Optional[int] = None      # Memory limit in bytes
    memory_soft_limit: Optional[int] = None # Memory soft limit in bytes
    memory_swap_limit: Optional[int] = None # Memory + swap limit in bytes
    oom_kill_disable: bool = False          # Disable OOM killer
    
    # I/O limits
    io_weight: Optional[int] = None         # I/O weight (1-10000)
    io_read_bps: Optional[int] = None       # Max read bytes/s
    io_write_bps: Optional[int] = None      # Max write bytes/s
    
    # PIDs limit
    pids_limit: Optional[int] = None        # Max number of PIDs
    
    def __post_init__(self):
        """Compute cpu_quota from cpus if cpus is set."""
        if self.cpus is not None and self.cpu_quota is None:
            self.cpu_quota = int(self.cpus * self.cpu_period)


class CgroupManager:
    """
    Manages Linux cgroups v2 for resource isolation.
    Falls back gracefully when cgroups are not available.
    """
    
    CGROUP_V2_ROOT = "/sys/fs/cgroup"
    
    def __init__(self, name: str, limits: Optional[ResourceLimits] = None):
        """
        Initialize the cgroup manager.
        
        Args:
            name: Name for this cgroup (usually container/service name).
            limits: Resource limits to apply.
        """
        self.name = self._sanitize_name(name)
        self.limits = limits or ResourceLimits()
        self._is_linux = sys.platform.startswith('linux')
        self._cgroup_path: Optional[Path] = None
        self._is_v2 = False
        self._initialized = False
        
        if self._is_linux:
            self._detect_cgroup_version()
    
    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Sanitize a name for use as a cgroup path component."""
        # Replace problematic characters
        sanitized = name.replace('/', '_').replace('..', '_')
        # Remove leading dots
        while sanitized.startswith('.'):
            sanitized = sanitized[1:]
        return sanitized or "container"
    
    def _detect_cgroup_version(self) -> None:
        """Detect which cgroup version is available."""
        # Check for cgroup v2 (unified hierarchy)
        cgroup_v2_path = Path(self.CGROUP_V2_ROOT)
        if cgroup_v2_path.exists():
            controllers_path = cgroup_v2_path / "cgroup.controllers"
            if controllers_path.exists():
                self._is_v2 = True
                return
        
        # Could add cgroup v1 support here if needed
        print("Warning: cgroup v2 not detected, resource limits will not be enforced")
    
    @property
    def is_available(self) -> bool:
        """Check if cgroup management is available."""
        return self._is_linux and self._is_v2
    
    def create(self) -> bool:
        """
        Create a cgroup for this container.
        
        Returns:
            True if successful, False otherwise.
        """
        if not self.is_available:
            return False
        
        # Create under d2p namespace
        cgroup_base = Path(self.CGROUP_V2_ROOT) / "d2p"
        if not cgroup_base.exists():
            try:
                cgroup_base.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                print(f"Warning: No permission to create cgroup at {cgroup_base}")
                return False
        
        self._cgroup_path = cgroup_base / self.name
        
        try:
            if not self._cgroup_path.exists():
                self._cgroup_path.mkdir(parents=True, exist_ok=True)
            
            # Enable controllers
            self._enable_controllers()
            
            self._initialized = True
            return True
            
        except PermissionError:
            print(f"Warning: No permission to create cgroup at {self._cgroup_path}")
            return False
        except Exception as e:
            print(f"Warning: Failed to create cgroup: {e}")
            return False
    
    def _enable_controllers(self) -> None:
        """Enable required controllers for the cgroup."""
        if not self._cgroup_path or not self._cgroup_path.exists():
            return
        
        parent_path = self._cgroup_path.parent
        subtree_control = parent_path / "cgroup.subtree_control"
        
        if subtree_control.exists():
            try:
                # Enable common controllers
                controllers = ["+cpu", "+memory", "+io", "+pids"]
                with open(subtree_control, 'w') as f:
                    f.write(" ".join(controllers))
            except (PermissionError, OSError):
                # Not all controllers may be available
                pass
    
    def apply_limits(self) -> bool:
        """
        Apply resource limits to the cgroup.
        
        Returns:
            True if any limits were applied, False otherwise.
        """
        if not self._initialized or not self._cgroup_path:
            return False
        
        applied = False
        
        # Apply CPU limits
        applied |= self._apply_cpu_limits()
        
        # Apply memory limits
        applied |= self._apply_memory_limits()
        
        # Apply I/O limits
        applied |= self._apply_io_limits()
        
        # Apply PIDs limit
        applied |= self._apply_pids_limit()
        
        return applied
    
    def _apply_cpu_limits(self) -> bool:
        """Apply CPU resource limits."""
        if not self._cgroup_path:
            return False
        
        applied = False
        
        # CPU weight (shares)
        if self.limits.cpu_shares is not None:
            weight_path = self._cgroup_path / "cpu.weight"
            if weight_path.exists():
                try:
                    # Convert from shares (1-1024) to weight (1-10000)
                    weight = max(1, min(10000, self.limits.cpu_shares))
                    with open(weight_path, 'w') as f:
                        f.write(str(weight))
                    applied = True
                except (PermissionError, OSError):
                    pass
        
        # CPU quota
        if self.limits.cpu_quota is not None or self.limits.cpus is not None:
            max_path = self._cgroup_path / "cpu.max"
            if max_path.exists():
                try:
                    quota = self.limits.cpu_quota
                    if quota is None and self.limits.cpus is not None:
                        quota = int(self.limits.cpus * self.limits.cpu_period)
                    with open(max_path, 'w') as f:
                        f.write(f"{quota} {self.limits.cpu_period}")
                    applied = True
                except (PermissionError, OSError):
                    pass
        
        return applied
    
    def _apply_memory_limits(self) -> bool:
        """Apply memory resource limits."""
        if not self._cgroup_path:
            return False
        
        applied = False
        
        # Memory max
        if self.limits.memory_limit is not None:
            max_path = self._cgroup_path / "memory.max"
            if max_path.exists():
                try:
                    with open(max_path, 'w') as f:
                        f.write(str(self.limits.memory_limit))
                    applied = True
                except (PermissionError, OSError):
                    pass
        
        # Memory high (soft limit)
        if self.limits.memory_soft_limit is not None:
            high_path = self._cgroup_path / "memory.high"
            if high_path.exists():
                try:
                    with open(high_path, 'w') as f:
                        f.write(str(self.limits.memory_soft_limit))
                    applied = True
                except (PermissionError, OSError):
                    pass
        
        # Memory swap
        if self.limits.memory_swap_limit is not None:
            swap_path = self._cgroup_path / "memory.swap.max"
            if swap_path.exists():
                try:
                    with open(swap_path, 'w') as f:
                        f.write(str(self.limits.memory_swap_limit))
                    applied = True
                except (PermissionError, OSError):
                    pass
        
        return applied
    
    def _apply_io_limits(self) -> bool:
        """Apply I/O resource limits."""
        if not self._cgroup_path:
            return False
        
        applied = False
        
        # I/O weight
        if self.limits.io_weight is not None:
            weight_path = self._cgroup_path / "io.weight"
            if weight_path.exists():
                try:
                    weight = max(1, min(10000, self.limits.io_weight))
                    with open(weight_path, 'w') as f:
                        f.write(f"default {weight}")
                    applied = True
                except (PermissionError, OSError):
                    pass
        
        return applied
    
    def _apply_pids_limit(self) -> bool:
        """Apply PIDs limit."""
        if not self._cgroup_path:
            return False
        
        if self.limits.pids_limit is not None:
            max_path = self._cgroup_path / "pids.max"
            if max_path.exists():
                try:
                    with open(max_path, 'w') as f:
                        f.write(str(self.limits.pids_limit))
                    return True
                except (PermissionError, OSError):
                    pass
        
        return False
    
    def add_process(self, pid: int) -> bool:
        """
        Add a process to this cgroup.
        
        Args:
            pid: Process ID to add.
            
        Returns:
            True if successful, False otherwise.
        """
        if not self._initialized or not self._cgroup_path:
            return False
        
        procs_path = self._cgroup_path / "cgroup.procs"
        try:
            with open(procs_path, 'w') as f:
                f.write(str(pid))
            return True
        except (PermissionError, OSError) as e:
            print(f"Warning: Failed to add process {pid} to cgroup: {e}")
            return False
    
    def get_stats(self) -> dict:
        """
        Get current resource usage statistics.
        
        Returns:
            Dictionary with usage statistics.
        """
        stats = {}
        
        if not self._initialized or not self._cgroup_path:
            return stats
        
        # CPU stats
        cpu_stat_path = self._cgroup_path / "cpu.stat"
        if cpu_stat_path.exists():
            try:
                with open(cpu_stat_path, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) == 2:
                            stats[f"cpu.{parts[0]}"] = int(parts[1])
            except (PermissionError, OSError):
                pass
        
        # Memory stats
        memory_current_path = self._cgroup_path / "memory.current"
        if memory_current_path.exists():
            try:
                with open(memory_current_path, 'r') as f:
                    stats["memory.current"] = int(f.read().strip())
            except (PermissionError, OSError, ValueError):
                pass
        
        # PIDs count
        pids_current_path = self._cgroup_path / "pids.current"
        if pids_current_path.exists():
            try:
                with open(pids_current_path, 'r') as f:
                    stats["pids.current"] = int(f.read().strip())
            except (PermissionError, OSError, ValueError):
                pass
        
        return stats
    
    def cleanup(self) -> bool:
        """
        Remove the cgroup.
        
        Returns:
            True if successful or not initialized, False on error.
        """
        if not self._initialized or not self._cgroup_path:
            return True
        
        try:
            # Cgroup directories can only be removed when empty
            if self._cgroup_path.exists():
                self._cgroup_path.rmdir()
            self._initialized = False
            return True
        except OSError as e:
            print(f"Warning: Failed to remove cgroup: {e}")
            return False
    
    @staticmethod
    def parse_memory_string(memory_str: str) -> Optional[int]:
        """
        Parse a memory string like "512m" or "1g" to bytes.
        
        Args:
            memory_str: Memory size string.
            
        Returns:
            Size in bytes, or None if parsing fails.
        """
        if not memory_str:
            return None
        
        memory_str = memory_str.strip().lower()
        
        suffixes = {
            'b': 1,
            'k': 1024,
            'kb': 1024,
            'm': 1024 ** 2,
            'mb': 1024 ** 2,
            'g': 1024 ** 3,
            'gb': 1024 ** 3,
            't': 1024 ** 4,
            'tb': 1024 ** 4,
        }
        
        for suffix, multiplier in sorted(suffixes.items(), key=lambda x: -len(x[0])):
            if memory_str.endswith(suffix):
                try:
                    value = float(memory_str[:-len(suffix)])
                    return int(value * multiplier)
                except ValueError:
                    return None
        
        try:
            return int(memory_str)
        except ValueError:
            return None
