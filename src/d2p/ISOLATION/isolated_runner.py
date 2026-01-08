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
Isolated process runner that combines namespaces, cgroups, and filesystem isolation.
Provides a unified interface for running processes with container-like isolation.
"""

import os
import sys
import subprocess
import signal
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from pathlib import Path

from .namespace_manager import NamespaceManager, NamespaceConfig, NamespaceType
from .cgroup_manager import CgroupManager, ResourceLimits
from .filesystem_isolation import FilesystemIsolation, FilesystemConfig


@dataclass
class IsolationConfig:
    """Complete configuration for process isolation."""

    # Namespace configuration
    namespaces: NamespaceType = NamespaceType.NONE
    hostname: Optional[str] = None

    # Resource limits
    cpu_limit: Optional[float] = None  # Number of CPUs
    memory_limit: Optional[str] = None  # Memory limit (e.g., "512m")
    pids_limit: Optional[int] = None  # Max processes

    # Filesystem configuration
    rootfs: Optional[str] = None  # Container rootfs path
    working_dir: Optional[str] = None  # Working directory
    bind_mounts: List[tuple] = field(default_factory=list)
    tmpfs_mounts: List[tuple] = field(default_factory=list)

    # User configuration
    uid: Optional[int] = None  # Run as this UID
    gid: Optional[int] = None  # Run as this GID

    # Misc
    drop_capabilities: bool = True  # Drop Linux capabilities
    no_new_privileges: bool = True  # Prevent privilege escalation


class IsolatedRunner:
    """
    Runs processes with configurable isolation using namespaces, cgroups, and chroot.
    Provides graceful degradation when isolation features are not available.
    """

    def __init__(self, name: str, config: Optional[IsolationConfig] = None):
        """
        Initialize the isolated runner.

        Args:
            name: Identifier for this runner (used for cgroup naming).
            config: Isolation configuration.
        """
        self.name = name
        self.config = config or IsolationConfig()
        self._process: Optional[subprocess.Popen] = None
        self._pid: Optional[int] = None
        self._isolation_active = False

        # Initialize managers
        ns_config = NamespaceConfig(
            namespaces=self.config.namespaces, hostname=self.config.hostname
        )
        self._namespace_mgr = NamespaceManager(ns_config)

        resource_limits = ResourceLimits(
            cpus=self.config.cpu_limit,
            memory_limit=(
                CgroupManager.parse_memory_string(self.config.memory_limit)
                if self.config.memory_limit
                else None
            ),
            pids_limit=self.config.pids_limit,
        )
        self._cgroup_mgr = CgroupManager(name, resource_limits)

        fs_config = FilesystemConfig(
            rootfs=self.config.rootfs,
            working_dir=self.config.working_dir,
            bind_mounts=self.config.bind_mounts,
            tmpfs_mounts=self.config.tmpfs_mounts,
        )
        self._fs_mgr = FilesystemIsolation(fs_config)

    @property
    def is_linux(self) -> bool:
        """Check if running on Linux."""
        return sys.platform.startswith("linux")

    @property
    def isolation_available(self) -> bool:
        """Check if any isolation features are available."""
        return (
            self._namespace_mgr.is_available
            or self._cgroup_mgr.is_available
            or self._fs_mgr.is_available
        )

    def get_isolation_summary(self) -> Dict[str, str]:
        """Get a summary of available isolation features."""
        return {
            "namespaces": self._namespace_mgr.get_isolation_level(),
            "cgroups": (
                "available" if self._cgroup_mgr.is_available else "not available"
            ),
            "filesystem": "available" if self._fs_mgr.is_available else "not available",
        }

    def run(
        self,
        command: List[str],
        env: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None,
        stdout: Optional[int] = None,
        stderr: Optional[int] = None,
    ) -> subprocess.Popen:
        """
        Run a command with isolation.

        Args:
            command: Command and arguments to run.
            env: Environment variables.
            working_dir: Override working directory.
            stdout: File descriptor for stdout.
            stderr: File descriptor for stderr.

        Returns:
            The subprocess.Popen object.
        """
        # Prepare environment
        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        # Use configured working_dir or parameter
        cwd = working_dir or self.config.working_dir

        # Set up cgroup first (before spawning process)
        cgroup_created = self._cgroup_mgr.create()
        if cgroup_created:
            self._cgroup_mgr.apply_limits()

        # For full isolation, we need to fork and exec with setup
        if self._should_use_full_isolation():
            return self._run_isolated(command, run_env, cwd, stdout, stderr)

        # Fallback to basic subprocess with cgroup
        return self._run_basic(command, run_env, cwd, stdout, stderr, cgroup_created)

    def _should_use_full_isolation(self) -> bool:
        """Check if we should use full isolation (fork model)."""
        # Need at least namespace support for full isolation
        if not self._namespace_mgr.is_available:
            return False

        # Check if any namespaces are requested
        effective_ns = self._namespace_mgr.get_effective_namespaces()
        return effective_ns != NamespaceType.NONE

    def _run_basic(
        self,
        command: List[str],
        env: Dict[str, str],
        cwd: Optional[str],
        stdout: Optional[int],
        stderr: Optional[int],
        cgroup_created: bool,
    ) -> subprocess.Popen:
        """
        Run with basic isolation (cgroups only, no namespaces).
        """
        try:
            self._process = subprocess.Popen(
                command,
                env=env,
                cwd=cwd,
                stdout=stdout if stdout else subprocess.PIPE,
                stderr=stderr if stderr else subprocess.PIPE,
                text=True,
                shell=False,
                preexec_fn=self._get_preexec_fn(cgroup_created),
            )
            self._pid = self._process.pid
            self._isolation_active = cgroup_created
            return self._process

        except Exception as e:
            print(f"[{self.name}] Failed to start process: {e}")
            raise

    def _run_isolated(
        self,
        command: List[str],
        env: Dict[str, str],
        cwd: Optional[str],
        stdout: Optional[int],
        stderr: Optional[int],
    ) -> subprocess.Popen:
        """
        Run with full isolation (namespaces + cgroups + filesystem).
        Uses a wrapper script that applies isolation before exec.
        """
        # Create an isolation wrapper
        # This is necessary because some namespace operations (like PID namespace)
        # need to be done before exec

        wrapper_code = self._generate_isolation_wrapper(command, env, cwd)

        try:
            self._process = subprocess.Popen(
                [sys.executable, "-c", wrapper_code],
                stdout=stdout if stdout else subprocess.PIPE,
                stderr=stderr if stderr else subprocess.PIPE,
                text=True,
                shell=False,
                env=env,
                preexec_fn=self._get_preexec_fn(True),
            )
            self._pid = self._process.pid
            self._isolation_active = True
            return self._process

        except Exception as e:
            print(f"[{self.name}] Failed to start isolated process: {e}")
            raise

    def _get_preexec_fn(self, add_to_cgroup: bool) -> Optional[Callable]:
        """Get a preexec function for subprocess setup."""
        cgroup_mgr = self._cgroup_mgr if add_to_cgroup else None
        config = self.config

        def preexec():
            # Add to cgroup
            if cgroup_mgr and cgroup_mgr._initialized:
                cgroup_mgr.add_process(os.getpid())

            # Set UID/GID if specified
            if config.gid is not None:
                try:
                    os.setgid(config.gid)
                except PermissionError:
                    pass

            if config.uid is not None:
                try:
                    os.setuid(config.uid)
                except PermissionError:
                    pass

            # Set no_new_privileges (prevents setuid binaries from gaining privileges)
            if config.no_new_privileges and sys.platform.startswith("linux"):
                try:
                    import ctypes

                    libc = ctypes.CDLL("libc.so.6", use_errno=True)
                    PR_SET_NO_NEW_PRIVS = 38
                    libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
                except Exception:
                    pass

        return preexec

    def _generate_isolation_wrapper(
        self, command: List[str], env: Dict[str, str], cwd: Optional[str]
    ) -> str:
        """Generate Python code for the isolation wrapper."""
        import json

        cmd_json = json.dumps(command)
        env_json = json.dumps(env)
        cwd_json = json.dumps(cwd)

        ns_flags = int(self.config.namespaces)
        hostname = json.dumps(self.config.hostname)

        return f"""
import os
import sys
import ctypes
import json

# Configuration
command = {cmd_json}
env = {env_json}
cwd = {cwd_json}
ns_flags = {ns_flags}
hostname = {hostname}

# Try to apply namespaces
try:
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    
    # Create new namespaces
    if ns_flags > 0:
        ret = libc.unshare(ns_flags)
        if ret != 0:
            print("Warning: unshare failed", file=sys.stderr)
    
    # Set hostname if provided and UTS namespace is used
    UTS_FLAG = 0x04000000
    if (ns_flags & UTS_FLAG) and hostname:
        hostname_bytes = hostname.encode('utf-8')
        libc.sethostname(hostname_bytes, len(hostname_bytes))

except Exception as e:
    print(f"Warning: Isolation setup failed: {{e}}", file=sys.stderr)

# Set environment
os.environ.clear()
os.environ.update(env)

# Change directory
if cwd:
    try:
        os.chdir(cwd)
    except Exception:
        pass

# Execute command
os.execvp(command[0], command)
"""

    def stop(self, timeout: int = 10) -> None:
        """
        Stop the running process.

        Args:
            timeout: Seconds to wait for graceful termination.
        """
        if self._process is None:
            return

        try:
            self._process.terminate()
            self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()
        except Exception as e:
            print(f"[{self.name}] Error stopping process: {e}")
        finally:
            self._cleanup()

    def is_running(self) -> bool:
        """Check if the process is still running."""
        if self._process is None:
            return False
        return self._process.poll() is None

    def get_exit_code(self) -> Optional[int]:
        """Get the exit code of the process."""
        if self._process is None:
            return None
        return self._process.poll()

    def get_stats(self) -> Dict[str, Any]:
        """Get resource usage statistics."""
        stats = {
            "pid": self._pid,
            "running": self.is_running(),
            "isolation_active": self._isolation_active,
        }

        if self._cgroup_mgr._initialized:
            stats.update(self._cgroup_mgr.get_stats())

        return stats

    def _cleanup(self) -> None:
        """Clean up isolation resources."""
        # Clean up cgroup
        if self._cgroup_mgr._initialized:
            self._cgroup_mgr.cleanup()

        self._process = None
        self._pid = None
        self._isolation_active = False


def create_isolation_config_from_service(service_def) -> IsolationConfig:
    """
    Create an IsolationConfig from a ServiceDefinition.

    Args:
        service_def: ServiceDefinition object.

    Returns:
        IsolationConfig object.
    """
    config = IsolationConfig(
        hostname=service_def.hostname,
        working_dir=service_def.working_dir,
    )

    # Set CPU limit
    if service_def.cpu_limit is not None:
        config.cpu_limit = service_def.cpu_limit

    # Set memory limit
    if service_def.memory_limit is not None:
        config.memory_limit = service_def.memory_limit

    # Convert volumes to bind mounts
    for vol in service_def.volumes:
        config.bind_mounts.append((vol.source, vol.target, vol.read_only))

    # Convert tmpfs to tmpfs mounts
    for tmpfs_path in service_def.tmpfs:
        config.tmpfs_mounts.append((tmpfs_path, None))

    # Determine namespace isolation level
    # For now, use basic isolation which doesn't require root
    config.namespaces = NamespaceType.NONE

    return config
