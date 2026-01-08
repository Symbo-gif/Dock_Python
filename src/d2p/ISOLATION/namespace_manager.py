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
Linux namespace management for process isolation.
Supports PID, NET, MNT, IPC, UTS namespaces with graceful degradation.
"""

import os
import sys
import ctypes
from typing import Optional, List, Set
from dataclasses import dataclass, field
from enum import IntFlag

# Linux namespace flags
CLONE_NEWNS = 0x00020000  # Mount namespace
CLONE_NEWUTS = 0x04000000  # UTS namespace (hostname)
CLONE_NEWIPC = 0x08000000  # IPC namespace
CLONE_NEWUSER = 0x10000000  # User namespace
CLONE_NEWPID = 0x20000000  # PID namespace
CLONE_NEWNET = 0x40000000  # Network namespace
CLONE_NEWCGROUP = 0x02000000  # Cgroup namespace


class NamespaceType(IntFlag):
    """Available Linux namespaces for isolation."""

    NONE = 0
    MOUNT = CLONE_NEWNS
    UTS = CLONE_NEWUTS
    IPC = CLONE_NEWIPC
    USER = CLONE_NEWUSER
    PID = CLONE_NEWPID
    NET = CLONE_NEWNET
    CGROUP = CLONE_NEWCGROUP

    # Commonly used combinations
    BASIC = MOUNT | UTS | IPC  # Basic isolation
    STANDARD = MOUNT | UTS | IPC | PID  # Standard container isolation
    FULL = MOUNT | UTS | IPC | PID | NET  # Full isolation (except user)


@dataclass
class NamespaceConfig:
    """Configuration for namespace isolation."""

    namespaces: NamespaceType = NamespaceType.BASIC
    hostname: Optional[str] = None
    uid_map: Optional[str] = None  # Format: "inside_uid outside_uid count"
    gid_map: Optional[str] = None  # Format: "inside_gid outside_gid count"


class NamespaceManager:
    """
    Manages Linux namespaces for process isolation.
    Falls back gracefully when running on non-Linux or without privileges.
    """

    def __init__(self, config: Optional[NamespaceConfig] = None):
        """
        Initialize the namespace manager.

        Args:
            config: Namespace configuration. If None, uses default (no isolation).
        """
        self.config = config or NamespaceConfig(namespaces=NamespaceType.NONE)
        self._is_linux = sys.platform.startswith("linux")
        self._libc: Optional[ctypes.CDLL] = None
        self._available_namespaces: Set[NamespaceType] = set()
        self._initialized = False

        if self._is_linux:
            self._init_linux()

    def _init_linux(self) -> None:
        """Initialize Linux-specific resources."""
        try:
            self._libc = ctypes.CDLL("libc.so.6", use_errno=True)
            self._detect_available_namespaces()
        except OSError as e:
            print(f"Warning: Could not load libc: {e}")
            self._libc = None

    def _detect_available_namespaces(self) -> None:
        """Detect which namespaces are available on this system."""
        # Check if we're root or have CAP_SYS_ADMIN
        is_root = os.geteuid() == 0

        # Check for user namespace support (doesn't require root)
        user_ns_path = "/proc/sys/kernel/unprivileged_userns_clone"
        user_ns_enabled = False
        if os.path.exists(user_ns_path):
            try:
                with open(user_ns_path, "r") as f:
                    user_ns_enabled = f.read().strip() == "1"
            except PermissionError:
                pass

        if user_ns_enabled:
            self._available_namespaces.add(NamespaceType.USER)

        if is_root:
            # Root can use all namespaces
            for ns_type in [
                NamespaceType.MOUNT,
                NamespaceType.UTS,
                NamespaceType.IPC,
                NamespaceType.PID,
                NamespaceType.NET,
                NamespaceType.CGROUP,
            ]:
                self._available_namespaces.add(ns_type)
        elif user_ns_enabled:
            # With user namespace, we can potentially use other namespaces
            self._available_namespaces.add(NamespaceType.MOUNT)
            self._available_namespaces.add(NamespaceType.UTS)
            self._available_namespaces.add(NamespaceType.IPC)
            self._available_namespaces.add(NamespaceType.PID)

    @property
    def is_available(self) -> bool:
        """Check if namespace isolation is available."""
        return self._is_linux and self._libc is not None

    @property
    def available_namespaces(self) -> Set[NamespaceType]:
        """Get the set of available namespaces."""
        return self._available_namespaces.copy()

    def get_effective_namespaces(self) -> NamespaceType:
        """
        Get the namespaces that will actually be used.
        This intersects requested namespaces with available ones.
        """
        if not self.is_available:
            return NamespaceType.NONE

        effective = NamespaceType.NONE
        for ns_type in NamespaceType:
            if (self.config.namespaces & ns_type) and (
                ns_type in self._available_namespaces
            ):
                effective |= ns_type
        return effective

    def unshare(self, namespaces: Optional[NamespaceType] = None) -> bool:
        """
        Create new namespaces and move the current process into them.

        Args:
            namespaces: The namespaces to create. Uses config if not specified.

        Returns:
            True if successful, False otherwise.
        """
        if not self.is_available:
            print(
                "Warning: Namespace isolation not available, running without isolation"
            )
            return False

        ns_to_create = namespaces if namespaces is not None else self.config.namespaces
        effective_ns = NamespaceType.NONE

        # Calculate effective namespaces
        for ns_type in NamespaceType:
            if (ns_to_create & ns_type) and (ns_type in self._available_namespaces):
                effective_ns |= ns_type

        if effective_ns == NamespaceType.NONE:
            return True  # Nothing to do

        # Call unshare syscall
        try:
            if self._libc is None:
                print("Warning: libc not available")
                return False
            ret = self._libc.unshare(int(effective_ns))
            if ret != 0:
                errno = ctypes.get_errno()
                print(f"Warning: unshare failed with errno {errno}")
                return False

            self._initialized = True

            # Set hostname if UTS namespace was created
            if (effective_ns & NamespaceType.UTS) and self.config.hostname:
                self._set_hostname(self.config.hostname)

            return True

        except Exception as e:
            print(f"Warning: Failed to create namespaces: {e}")
            return False

    def _set_hostname(self, hostname: str) -> bool:
        """Set the hostname in the UTS namespace."""
        try:
            if self._libc is None:
                return False
            hostname_bytes = hostname.encode("utf-8")
            ret = self._libc.sethostname(hostname_bytes, len(hostname_bytes))
            return ret == 0
        except Exception as e:
            print(f"Warning: Failed to set hostname: {e}")
            return False

    def setup_uid_gid_map(self) -> bool:
        """
        Set up UID/GID mappings for user namespace.

        Returns:
            True if successful, False otherwise.
        """
        if not (self.config.namespaces & NamespaceType.USER):
            return True  # Not using user namespace

        pid = os.getpid()

        # Write UID map
        if self.config.uid_map:
            uid_map_path = f"/proc/{pid}/uid_map"
            try:
                with open(uid_map_path, "w") as f:
                    f.write(self.config.uid_map + "\n")
            except PermissionError:
                # Try with setgroups deny first
                setgroups_path = f"/proc/{pid}/setgroups"
                try:
                    with open(setgroups_path, "w") as f:
                        f.write("deny\n")
                    with open(uid_map_path, "w") as f:
                        f.write(self.config.uid_map + "\n")
                except Exception as e:
                    print(f"Warning: Failed to set UID map: {e}")
                    return False

        # Write GID map
        if self.config.gid_map:
            gid_map_path = f"/proc/{pid}/gid_map"
            try:
                with open(gid_map_path, "w") as f:
                    f.write(self.config.gid_map + "\n")
            except Exception as e:
                print(f"Warning: Failed to set GID map: {e}")
                return False

        return True

    def get_isolation_level(self) -> str:
        """
        Get a human-readable description of the current isolation level.

        Returns:
            Description of isolation level.
        """
        if not self.is_available:
            return "none (not on Linux or missing privileges)"

        effective = self.get_effective_namespaces()
        if effective == NamespaceType.NONE:
            return "none (no namespaces configured)"

        ns_names = []
        if effective & NamespaceType.MOUNT:
            ns_names.append("mount")
        if effective & NamespaceType.UTS:
            ns_names.append("uts")
        if effective & NamespaceType.IPC:
            ns_names.append("ipc")
        if effective & NamespaceType.PID:
            ns_names.append("pid")
        if effective & NamespaceType.NET:
            ns_names.append("net")
        if effective & NamespaceType.USER:
            ns_names.append("user")
        if effective & NamespaceType.CGROUP:
            ns_names.append("cgroup")

        return f"namespaces: {', '.join(ns_names)}"
