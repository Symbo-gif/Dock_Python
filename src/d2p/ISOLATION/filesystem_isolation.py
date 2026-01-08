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
Filesystem isolation using chroot, pivot_root, and bind mounts.
Provides container-like filesystem views.
"""

import os
import sys
import shutil
import tempfile
from typing import Optional, List
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FilesystemConfig:
    """Configuration for filesystem isolation."""

    rootfs: Optional[str] = None  # Path to container root filesystem
    working_dir: Optional[str] = None  # Working directory inside container
    read_only: bool = False  # Make rootfs read-only

    # Bind mounts: list of (source, target, read_only) tuples
    bind_mounts: List[tuple] = field(default_factory=list)

    # tmpfs mounts: list of (target, size) tuples (size in bytes, None for default)
    tmpfs_mounts: List[tuple] = field(default_factory=list)

    # Mask paths (replaced with empty dir or /dev/null)
    masked_paths: List[str] = field(
        default_factory=lambda: [
            "/proc/kcore",
            "/proc/sched_debug",
            "/proc/scsi",
            "/sys/firmware",
        ]
    )

    # Read-only paths
    readonly_paths: List[str] = field(
        default_factory=lambda: [
            "/proc/asound",
            "/proc/bus",
            "/proc/fs",
            "/proc/irq",
            "/proc/sys",
            "/proc/sysrq-trigger",
        ]
    )


class FilesystemIsolation:
    """
    Provides filesystem isolation using chroot and bind mounts.
    Falls back gracefully when isolation is not available.
    """

    def __init__(self, config: Optional[FilesystemConfig] = None):
        """
        Initialize filesystem isolation.

        Args:
            config: Filesystem configuration.
        """
        self.config = config or FilesystemConfig()
        self._is_linux = sys.platform.startswith("linux")
        self._is_root = os.geteuid() == 0
        self._old_root: Optional[str] = None
        self._initialized = False

    @property
    def is_available(self) -> bool:
        """Check if filesystem isolation is available."""
        # chroot requires root on Linux
        return self._is_linux and self._is_root

    def prepare_rootfs(self, base_path: str) -> Optional[str]:
        """
        Prepare a minimal root filesystem.

        Args:
            base_path: Base path where the rootfs should be created.

        Returns:
            Path to the prepared rootfs, or None on failure.
        """
        rootfs = Path(base_path) / "rootfs"

        try:
            rootfs.mkdir(parents=True, exist_ok=True)

            # Create minimal directory structure
            for d in [
                "bin",
                "dev",
                "etc",
                "home",
                "lib",
                "lib64",
                "proc",
                "root",
                "run",
                "sbin",
                "sys",
                "tmp",
                "usr",
                "var",
            ]:
                (rootfs / d).mkdir(exist_ok=True)

            # Create /usr subdirectories
            for d in ["bin", "lib", "lib64", "sbin"]:
                (rootfs / "usr" / d).mkdir(exist_ok=True)

            # Create /var subdirectories
            for d in ["cache", "lib", "log", "run", "tmp"]:
                (rootfs / "var" / d).mkdir(exist_ok=True)

            # Create basic device nodes if we're root
            if self._is_root:
                self._create_devices(rootfs / "dev")

            # Create /etc files
            self._create_etc_files(rootfs / "etc")

            return str(rootfs)

        except Exception as e:
            print(f"Warning: Failed to prepare rootfs: {e}")
            return None

    def _create_devices(self, dev_path: Path) -> None:
        """Create basic device nodes."""
        # Device node creation requires root and mknod
        try:
            import stat

            # null device (major 1, minor 3)
            null_path = dev_path / "null"
            if not null_path.exists():
                os.mknod(str(null_path), stat.S_IFCHR | 0o666, os.makedev(1, 3))

            # zero device (major 1, minor 5)
            zero_path = dev_path / "zero"
            if not zero_path.exists():
                os.mknod(str(zero_path), stat.S_IFCHR | 0o666, os.makedev(1, 5))

            # random device (major 1, minor 8)
            random_path = dev_path / "random"
            if not random_path.exists():
                os.mknod(str(random_path), stat.S_IFCHR | 0o666, os.makedev(1, 8))

            # urandom device (major 1, minor 9)
            urandom_path = dev_path / "urandom"
            if not urandom_path.exists():
                os.mknod(str(urandom_path), stat.S_IFCHR | 0o666, os.makedev(1, 9))

            # tty device (major 5, minor 0)
            tty_path = dev_path / "tty"
            if not tty_path.exists():
                os.mknod(str(tty_path), stat.S_IFCHR | 0o666, os.makedev(5, 0))

            # Create symlinks
            pts_path = dev_path / "pts"
            pts_path.mkdir(exist_ok=True)

            stdin_link = dev_path / "stdin"
            if not stdin_link.exists():
                stdin_link.symlink_to("/proc/self/fd/0")

            stdout_link = dev_path / "stdout"
            if not stdout_link.exists():
                stdout_link.symlink_to("/proc/self/fd/1")

            stderr_link = dev_path / "stderr"
            if not stderr_link.exists():
                stderr_link.symlink_to("/proc/self/fd/2")

        except Exception as e:
            print(f"Warning: Failed to create some devices: {e}")

    def _create_etc_files(self, etc_path: Path) -> None:
        """Create basic /etc files."""
        # Create /etc/passwd
        passwd_path = etc_path / "passwd"
        if not passwd_path.exists():
            with open(passwd_path, "w") as f:
                f.write("root:x:0:0:root:/root:/bin/sh\n")
                f.write("nobody:x:65534:65534:nobody:/:/sbin/nologin\n")

        # Create /etc/group
        group_path = etc_path / "group"
        if not group_path.exists():
            with open(group_path, "w") as f:
                f.write("root:x:0:\n")
                f.write("nobody:x:65534:\n")

        # Create /etc/hosts
        hosts_path = etc_path / "hosts"
        if not hosts_path.exists():
            with open(hosts_path, "w") as f:
                f.write("127.0.0.1 localhost\n")
                f.write("::1 localhost\n")

        # Create /etc/resolv.conf
        resolv_path = etc_path / "resolv.conf"
        if not resolv_path.exists():
            # Copy from host if available
            host_resolv = Path("/etc/resolv.conf")
            if host_resolv.exists():
                shutil.copy2(str(host_resolv), str(resolv_path))
            else:
                with open(resolv_path, "w") as f:
                    f.write("nameserver 8.8.8.8\n")
                    f.write("nameserver 8.8.4.4\n")

    def mount_bind(self, source: str, target: str, read_only: bool = False) -> bool:
        """
        Create a bind mount.

        Args:
            source: Source path on host.
            target: Target path in container.
            read_only: Whether to mount read-only.

        Returns:
            True if successful, False otherwise.
        """
        if not self.is_available:
            return False

        try:
            import ctypes

            libc = ctypes.CDLL("libc.so.6", use_errno=True)

            # Mount flags
            MS_BIND = 4096
            MS_RDONLY = 1
            MS_REMOUNT = 32

            # Ensure target exists
            target_path = Path(target)
            if Path(source).is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.touch()

            # First mount
            source_b = source.encode("utf-8")
            target_b = target.encode("utf-8")
            ret = libc.mount(source_b, target_b, None, MS_BIND, None)

            if ret != 0:
                return False

            # Remount read-only if requested
            if read_only:
                ret = libc.mount(
                    source_b, target_b, None, MS_BIND | MS_REMOUNT | MS_RDONLY, None
                )

            return ret == 0

        except Exception as e:
            print(f"Warning: Failed to create bind mount: {e}")
            return False

    def mount_tmpfs(self, target: str, size: Optional[int] = None) -> bool:
        """
        Mount a tmpfs filesystem.

        Args:
            target: Target path.
            size: Size limit in bytes (None for default).

        Returns:
            True if successful, False otherwise.
        """
        if not self.is_available:
            return False

        try:
            import ctypes

            libc = ctypes.CDLL("libc.so.6", use_errno=True)

            # Ensure target exists
            Path(target).mkdir(parents=True, exist_ok=True)

            target_b = target.encode("utf-8")
            fstype_b = b"tmpfs"

            options = ""
            if size is not None:
                options = f"size={size}"
            options_b = options.encode("utf-8") if options else None

            ret = libc.mount(b"tmpfs", target_b, fstype_b, 0, options_b)
            return ret == 0

        except Exception as e:
            print(f"Warning: Failed to mount tmpfs: {e}")
            return False

    def mount_proc(self, target: str) -> bool:
        """
        Mount the proc filesystem.

        Args:
            target: Target path (usually /proc in container).

        Returns:
            True if successful, False otherwise.
        """
        if not self.is_available:
            return False

        try:
            import ctypes

            libc = ctypes.CDLL("libc.so.6", use_errno=True)

            Path(target).mkdir(parents=True, exist_ok=True)

            ret = libc.mount(b"proc", target.encode("utf-8"), b"proc", 0, None)
            return ret == 0

        except Exception as e:
            print(f"Warning: Failed to mount proc: {e}")
            return False

    def chroot(self, rootfs: str) -> bool:
        """
        Change the root directory.

        Args:
            rootfs: Path to new root.

        Returns:
            True if successful, False otherwise.
        """
        if not self.is_available:
            print("Warning: chroot not available, running without filesystem isolation")
            return False

        try:
            self._old_root = os.getcwd()
            os.chroot(rootfs)
            os.chdir("/")
            self._initialized = True
            return True

        except Exception as e:
            print(f"Warning: Failed to chroot: {e}")
            return False

    def pivot_root(self, new_root: str, put_old: str) -> bool:
        """
        Use pivot_root for more complete isolation than chroot.
        Requires being in a mount namespace.

        Args:
            new_root: Path to new root.
            put_old: Path under new_root to mount old root.

        Returns:
            True if successful, False otherwise.
        """
        if not self.is_available:
            return False

        try:
            import ctypes

            libc = ctypes.CDLL("libc.so.6", use_errno=True)

            # Ensure put_old path exists
            put_old_path = Path(new_root) / put_old.lstrip("/")
            put_old_path.mkdir(parents=True, exist_ok=True)

            # Make new_root a mount point (bind mount to itself)
            MS_BIND = 4096
            MS_REC = 16384
            new_root_b = new_root.encode("utf-8")
            libc.mount(new_root_b, new_root_b, None, MS_BIND | MS_REC, None)

            # Perform pivot_root via syscall
            SYS_pivot_root = 155  # x86_64
            ret = libc.syscall(
                SYS_pivot_root, new_root_b, str(put_old_path).encode("utf-8")
            )

            if ret != 0:
                return False

            os.chdir("/")

            # Unmount old root
            MNT_DETACH = 2
            old_root_in_new = "/" + put_old.lstrip("/")
            libc.umount2(old_root_in_new.encode("utf-8"), MNT_DETACH)

            # Remove old root directory
            try:
                os.rmdir(old_root_in_new)
            except OSError:
                pass

            self._initialized = True
            return True

        except Exception as e:
            print(f"Warning: Failed to pivot_root: {e}")
            return False

    def apply_configuration(self, rootfs: str) -> bool:
        """
        Apply full filesystem configuration including mounts.

        Args:
            rootfs: Path to container rootfs.

        Returns:
            True if at least basic isolation was set up.
        """
        if not self.is_available:
            return False

        success = True

        # Mount proc
        proc_path = os.path.join(rootfs, "proc")
        if not self.mount_proc(proc_path):
            success = False

        # Apply bind mounts
        for mount_spec in self.config.bind_mounts:
            if len(mount_spec) >= 2:
                source, target = mount_spec[0], mount_spec[1]
                read_only = mount_spec[2] if len(mount_spec) > 2 else False
                full_target = os.path.join(rootfs, target.lstrip("/"))
                if not self.mount_bind(source, full_target, read_only):
                    success = False

        # Apply tmpfs mounts
        for mount_spec in self.config.tmpfs_mounts:
            if len(mount_spec) >= 1:
                target = mount_spec[0]
                size = mount_spec[1] if len(mount_spec) > 1 else None
                full_target = os.path.join(rootfs, target.lstrip("/"))
                if not self.mount_tmpfs(full_target, size):
                    success = False

        # chroot into the filesystem
        if not self.chroot(rootfs):
            return False

        # Change to working directory
        if self.config.working_dir:
            try:
                os.chdir(self.config.working_dir)
            except OSError:
                pass

        return success

    def copy_host_binaries(self, rootfs: str, binaries: List[str]) -> bool:
        """
        Copy binaries and their library dependencies from host.

        Args:
            rootfs: Path to container rootfs.
            binaries: List of binary paths to copy.

        Returns:
            True if all binaries were copied.
        """
        import subprocess

        for binary in binaries:
            if not os.path.exists(binary):
                # Try to find it in PATH
                result = subprocess.run(
                    ["which", binary], capture_output=True, text=True
                )
                if result.returncode != 0:
                    continue
                binary = result.stdout.strip()

            if not binary or not os.path.exists(binary):
                continue

            # Copy binary
            dest_path = Path(rootfs) / binary.lstrip("/")
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(binary, str(dest_path))

            # Get library dependencies
            try:
                result = subprocess.run(["ldd", binary], capture_output=True, text=True)
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        parts = line.strip().split()
                        if len(parts) >= 3 and "=>" in line:
                            lib_path = parts[2]
                            if lib_path and os.path.exists(lib_path):
                                dest_lib = Path(rootfs) / lib_path.lstrip("/")
                                dest_lib.parent.mkdir(parents=True, exist_ok=True)
                                if not dest_lib.exists():
                                    shutil.copy2(lib_path, str(dest_lib))
                        elif len(parts) >= 1 and parts[0].startswith("/"):
                            lib_path = parts[0]
                            if os.path.exists(lib_path):
                                dest_lib = Path(rootfs) / lib_path.lstrip("/")
                                dest_lib.parent.mkdir(parents=True, exist_ok=True)
                                if not dest_lib.exists():
                                    shutil.copy2(lib_path, str(dest_lib))
            except Exception:
                pass

        return True
