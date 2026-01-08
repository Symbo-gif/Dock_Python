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
Volume management for services, handling mounting, bind mounts, tmpfs, and named volumes.
"""
import os
import sys
import shutil
import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone

from ..MODELS.service_definition import VolumeMount


@dataclass
class NamedVolume:
    """Represents a named Docker volume."""

    name: str
    path: str
    driver: str = "local"
    created_at: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    options: Dict[str, str] = field(default_factory=dict)


@dataclass
class TmpfsMount:
    """Configuration for a tmpfs mount."""

    target: str
    size: Optional[int] = None  # Size in bytes
    mode: int = 0o1777  # Permissions


class VolumeManager:
    """
    Manages volume mappings including bind mounts, named volumes, and tmpfs.
    """

    def __init__(self, base_dir: str = ".", volumes_root: str = ".d2p/volumes"):
        """
        Initializes the volume manager.

        :param base_dir: The base directory for resolving relative paths.
        :param volumes_root: The root directory for internal volume storage.
        """
        self.base_dir = os.path.abspath(base_dir)
        self.volumes_root = os.path.abspath(os.path.join(base_dir, volumes_root))
        self.index_file = os.path.join(self.volumes_root, "volumes.json")
        self._is_linux = sys.platform.startswith("linux")

        os.makedirs(self.volumes_root, exist_ok=True)

        # Load volume index
        self._volumes: Dict[str, NamedVolume] = self._load_index()

    def _load_index(self) -> Dict[str, NamedVolume]:
        """Load volume index from disk."""
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, "r") as f:
                    data = json.load(f)
                    return {
                        name: NamedVolume(**vol_data)
                        for name, vol_data in data.get("volumes", {}).items()
                    }
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save_index(self) -> None:
        """Save volume index to disk."""
        data = {
            "volumes": {
                name: {
                    "name": vol.name,
                    "path": vol.path,
                    "driver": vol.driver,
                    "created_at": vol.created_at,
                    "labels": vol.labels,
                    "options": vol.options,
                }
                for name, vol in self._volumes.items()
            }
        }
        with open(self.index_file, "w") as f:
            json.dump(data, f, indent=2)

    def create_volume(
        self,
        name: str,
        driver: str = "local",
        labels: Optional[Dict[str, str]] = None,
        options: Optional[Dict[str, str]] = None,
    ) -> NamedVolume:
        """
        Create a named volume.

        Args:
            name: Volume name.
            driver: Volume driver (only 'local' supported).
            labels: Volume labels.
            options: Driver options.

        Returns:
            Created NamedVolume object.
        """
        if name in self._volumes:
            return self._volumes[name]

        # Create volume directory
        vol_path = os.path.join(self.volumes_root, name)
        os.makedirs(vol_path, exist_ok=True)

        volume = NamedVolume(
            name=name,
            path=vol_path,
            driver=driver,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            labels=labels or {},
            options=options or {},
        )

        self._volumes[name] = volume
        self._save_index()

        print(f"Created volume: {name}")
        return volume

    def remove_volume(self, name: str, force: bool = False) -> bool:
        """
        Remove a named volume.

        Args:
            name: Volume name.
            force: Force removal even if data exists.

        Returns:
            True if removed.
        """
        if name not in self._volumes:
            return False

        vol = self._volumes[name]

        # Remove directory
        if os.path.exists(vol.path):
            if force:
                shutil.rmtree(vol.path)
            else:
                # Only remove if empty
                try:
                    os.rmdir(vol.path)
                except OSError:
                    print(f"Volume {name} is not empty. Use force=True to remove.")
                    return False

        del self._volumes[name]
        self._save_index()

        print(f"Removed volume: {name}")
        return True

    def list_volumes(self) -> List[NamedVolume]:
        """List all named volumes."""
        return list(self._volumes.values())

    def get_volume(self, name: str) -> Optional[NamedVolume]:
        """Get a named volume by name."""
        return self._volumes.get(name)

    def prepare_volumes(
        self, mounts: List[VolumeMount], service_working_dir: Optional[str] = None
    ):
        """
        Prepares volumes for a service.

        :param mounts: List of volume mounts.
        :param service_working_dir: The directory where the service will run.
        """
        for mount in mounts:
            source_path = self.resolve_source(mount.source)
            target_path = self.resolve_target(mount.target, service_working_dir)

            if not os.path.exists(source_path):
                os.makedirs(source_path, exist_ok=True)

            print(f"Mapping volume: {source_path} -> {target_path}")

            # Ensure target parent directory exists
            target_parent = os.path.dirname(target_path)
            if target_parent:
                os.makedirs(target_parent, exist_ok=True)

            try:
                if os.path.exists(target_path):
                    if os.path.islink(target_path) or os.path.isdir(target_path):
                        # If it's already there, we might want to skip or update
                        # For now, let's just skip if it's the same
                        if os.path.abspath(
                            os.path.realpath(target_path)
                        ) == os.path.abspath(source_path):
                            continue
                        # Otherwise, we might need to remove and re-link
                        if os.path.islink(target_path):
                            os.unlink(target_path)
                        else:
                            shutil.rmtree(target_path)
                    else:
                        os.remove(target_path)

                # Try to create a symlink (or junction on Windows)
                try:
                    is_dir = os.path.isdir(source_path)
                    os.symlink(source_path, target_path, target_is_directory=is_dir)
                except (OSError, NotImplementedError):
                    # Fallback to copy if symlink fails
                    print(f"Symlink failed for {target_path}, falling back to copy.")
                    if os.path.isdir(source_path):
                        shutil.copytree(source_path, target_path, dirs_exist_ok=True)
                    else:
                        shutil.copy2(source_path, target_path)
            except Exception as e:
                print(f"Error preparing volume {mount.source}: {e}")

    def prepare_tmpfs(
        self, tmpfs_mounts: List[str], rootfs: Optional[str] = None
    ) -> List[str]:
        """
        Prepare tmpfs mounts.

        Args:
            tmpfs_mounts: List of tmpfs target paths.
            rootfs: Optional rootfs path for container.

        Returns:
            List of successfully mounted paths.
        """
        mounted = []

        for tmpfs_spec in tmpfs_mounts:
            # Parse tmpfs spec (can be just path or "path:opts")
            if ":" in tmpfs_spec:
                target, opts = tmpfs_spec.split(":", 1)
            else:
                target = tmpfs_spec
                opts = ""

            # Resolve path
            if rootfs:
                full_path = os.path.join(rootfs, target.lstrip("/"))
            else:
                full_path = target

            # Create directory
            os.makedirs(full_path, exist_ok=True)

            # On Linux, try to mount actual tmpfs
            if self._is_linux:
                try:
                    if os.geteuid() == 0:
                        import ctypes

                        libc = ctypes.CDLL("libc.so.6", use_errno=True)

                        # Parse options
                        mount_opts = ""
                        if opts:
                            mount_opts = opts

                        ret = libc.mount(
                            b"tmpfs",
                            full_path.encode("utf-8"),
                            b"tmpfs",
                            0,
                            mount_opts.encode("utf-8") if mount_opts else None,
                        )

                        if ret == 0:
                            mounted.append(full_path)
                            print(f"Mounted tmpfs at {full_path}")
                            continue
                except Exception as e:
                    print(f"Warning: Failed to mount tmpfs at {full_path}: {e}")

            # Fallback: just create an empty directory (data won't persist anyway)
            print(f"Using regular directory for tmpfs at {full_path}")
            mounted.append(full_path)

        return mounted

    def resolve_source(self, source: str) -> str:
        """
        Resolves the source path of a volume.

        :param source: The source path or volume name.
        :return: The absolute path to the source.
        """
        # Check if it's a named volume
        if source in self._volumes:
            return self._volumes[source].path

        # Check if it looks like a named volume (no path separators, no dots at start)
        if (
            not os.path.isabs(source)
            and not source.startswith(".")
            and "/" not in source
            and "\\" not in source
        ):
            # Create as named volume
            vol = self.create_volume(source)
            return vol.path

        return os.path.abspath(os.path.join(self.base_dir, source))

    def resolve_target(self, target: str, working_dir: Optional[str] = None) -> str:
        """
        Resolves the target path of a volume.

        :param target: The target path inside the "container".
        :param working_dir: The working directory of the service.
        :return: The absolute path to the target.
        """
        if os.path.isabs(target):
            # On Windows, absolute paths like /app/data are problematic.
            # We'll treat them as relative to the base_dir or root of drive if they look like /...
            if target.startswith("/") or target.startswith("\\"):
                return os.path.abspath(
                    os.path.join(self.base_dir, target.lstrip("/\\"))
                )
            return target

        # Relative to working_dir if provided, else base_dir
        root = working_dir if working_dir else self.base_dir
        return os.path.abspath(os.path.join(root, target))

    def get_volume_size(self, name: str) -> int:
        """
        Get the size of a named volume in bytes.

        Args:
            name: Volume name.

        Returns:
            Size in bytes.
        """
        vol = self._volumes.get(name)
        if not vol or not os.path.exists(vol.path):
            return 0

        total = 0
        for dirpath, dirnames, filenames in os.walk(vol.path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.isfile(fp):
                    total += os.path.getsize(fp)
        return total

    def prune(self, all_unused: bool = False) -> Dict[str, Any]:
        """
        Remove unused volumes.

        Args:
            all_unused: Remove all unused volumes.

        Returns:
            Dictionary with removal statistics.
        """
        # For now, just remove empty volumes
        removed = []
        freed = 0

        for name, vol in list(self._volumes.items()):
            if os.path.exists(vol.path):
                try:
                    # Check if empty
                    if not os.listdir(vol.path):
                        os.rmdir(vol.path)
                        removed.append(name)
                        del self._volumes[name]
                except OSError:
                    pass

        self._save_index()

        return {"volumes_removed": removed, "space_reclaimed": freed}
