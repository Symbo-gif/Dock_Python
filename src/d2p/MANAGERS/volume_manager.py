"""
Volume management for services, handling mounting and synchronization.
"""
import os
import shutil
from typing import List, Optional
from ..MODELS.service_definition import VolumeMount

class VolumeManager:
    """
    Manages volume mappings by creating symlinks or copying directories.
    """
    def __init__(self, base_dir: str = ".", volumes_root: str = ".d2p/volumes"):
        """
        Initializes the volume manager.

        :param base_dir: The base directory for resolving relative paths.
        :param volumes_root: The root directory for internal volume storage.
        """
        self.base_dir = os.path.abspath(base_dir)
        self.volumes_root = os.path.abspath(os.path.join(base_dir, volumes_root))
        os.makedirs(self.volumes_root, exist_ok=True)

    def prepare_volumes(self, mounts: List[VolumeMount], service_working_dir: Optional[str] = None):
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
                        if os.path.abspath(os.path.realpath(target_path)) == os.path.abspath(source_path):
                            continue
                        # Otherwise, we might need to remove and re-link
                        if os.path.islink(target_path):
                            os.unlink(target_path)
                        else:
                            shutil.rmtree(target_path)
                    else:
                        os.remove(target_path)

                # Try to create a symlink (or junction on Windows)
                # On Windows, os.symlink(src, dst, target_is_directory=True) 
                # might require admin.
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

    def resolve_source(self, source: str) -> str:
        """
        Resolves the source path of a volume.

        :param source: The source path or volume name.
        :return: The absolute path to the source.
        """
        if not os.path.isabs(source) and not source.startswith('.'):
            return os.path.join(self.volumes_root, source)
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
            if target.startswith('/') or target.startswith('\\'):
                return os.path.abspath(os.path.join(self.base_dir, target.lstrip('/\\')))
            return target
        
        # Relative to working_dir if provided, else base_dir
        root = working_dir if working_dir else self.base_dir
        return os.path.abspath(os.path.join(root, target))
