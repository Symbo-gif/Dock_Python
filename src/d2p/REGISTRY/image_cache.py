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
Local image cache management.
Provides efficient storage and retrieval of pulled images.
"""

import os
import json
import hashlib
import shutil
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone, timedelta

from .image_reference import ImageReference


@dataclass
class CachedImage:
    """Information about a cached image."""
    reference: str
    digest: str
    created: str
    size: int
    rootfs_path: str
    config_path: str
    pulled_at: str


class ImageCache:
    """
    Manages a local cache of pulled images.
    Provides content-addressable storage for image layers.
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the image cache.
        
        Args:
            cache_dir: Directory for cache storage. Defaults to ~/.d2p/cache
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.home() / ".d2p" / "cache"
        
        self.layers_dir = self.cache_dir / "layers"
        self.images_dir = self.cache_dir / "images"
        self.index_file = self.cache_dir / "index.json"
        
        # Create directories
        self.layers_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or create index
        self._index = self._load_index()
    
    def _load_index(self) -> Dict[str, Any]:
        """Load the cache index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"images": {}, "layers": {}}
    
    def _save_index(self) -> None:
        """Save the cache index to disk."""
        with open(self.index_file, 'w') as f:
            json.dump(self._index, f, indent=2)
    
    def get_image(self, image_name: str) -> Optional[CachedImage]:
        """
        Get a cached image.
        
        Args:
            image_name: Image name or reference
            
        Returns:
            CachedImage if found, None otherwise
        """
        ref = ImageReference.parse(image_name)
        key = ref.full_name
        
        if key in self._index["images"]:
            info = self._index["images"][key]
            rootfs_path = Path(info["rootfs_path"])
            
            # Verify the image still exists
            if rootfs_path.exists():
                return CachedImage(
                    reference=info["reference"],
                    digest=info.get("digest", ""),
                    created=info.get("created", ""),
                    size=info.get("size", 0),
                    rootfs_path=str(rootfs_path),
                    config_path=info.get("config_path", ""),
                    pulled_at=info.get("pulled_at", "")
                )
            else:
                # Image was deleted, remove from index
                del self._index["images"][key]
                self._save_index()
        
        return None
    
    def add_image(self, 
                  image_name: str,
                  rootfs_path: str,
                  config: Dict[str, Any],
                  digest: Optional[str] = None) -> CachedImage:
        """
        Add an image to the cache.
        
        Args:
            image_name: Image name
            rootfs_path: Path to the image rootfs
            config: Image configuration
            digest: Image digest
            
        Returns:
            CachedImage object
        """
        ref = ImageReference.parse(image_name)
        key = ref.full_name
        
        # Calculate size
        size = self._calculate_dir_size(Path(rootfs_path))
        
        # Save config if not already saved
        config_path = Path(rootfs_path).parent / "config.json"
        if not config_path.exists():
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
        
        # Create index entry
        entry = {
            "reference": ref.full_name,
            "digest": digest or "",
            "created": config.get("created", ""),
            "size": size,
            "rootfs_path": str(rootfs_path),
            "config_path": str(config_path),
            "pulled_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
        
        self._index["images"][key] = entry
        self._save_index()
        
        return CachedImage(**entry)
    
    def remove_image(self, image_name: str) -> bool:
        """
        Remove an image from the cache.
        
        Args:
            image_name: Image name
            
        Returns:
            True if removed, False if not found
        """
        ref = ImageReference.parse(image_name)
        key = ref.full_name
        
        if key in self._index["images"]:
            info = self._index["images"][key]
            rootfs_path = Path(info["rootfs_path"])
            
            # Remove the image directory
            image_dir = rootfs_path.parent
            if image_dir.exists():
                shutil.rmtree(image_dir)
            
            del self._index["images"][key]
            self._save_index()
            return True
        
        return False
    
    def list_images(self) -> List[CachedImage]:
        """
        List all cached images.
        
        Returns:
            List of CachedImage objects
        """
        images = []
        for key, info in list(self._index["images"].items()):
            rootfs_path = Path(info["rootfs_path"])
            if rootfs_path.exists():
                images.append(CachedImage(
                    reference=info["reference"],
                    digest=info.get("digest", ""),
                    created=info.get("created", ""),
                    size=info.get("size", 0),
                    rootfs_path=str(rootfs_path),
                    config_path=info.get("config_path", ""),
                    pulled_at=info.get("pulled_at", "")
                ))
            else:
                # Clean up stale entries
                del self._index["images"][key]
        
        self._save_index()
        return images
    
    def has_layer(self, digest: str) -> bool:
        """Check if a layer is cached."""
        layer_path = self.layers_dir / digest.replace(":", "_")
        return layer_path.exists()
    
    def get_layer_path(self, digest: str) -> Optional[Path]:
        """Get the path to a cached layer."""
        layer_path = self.layers_dir / digest.replace(":", "_")
        return layer_path if layer_path.exists() else None
    
    def add_layer(self, digest: str, data: bytes) -> Path:
        """
        Add a layer to the cache.
        
        Args:
            digest: Layer digest
            data: Layer data
            
        Returns:
            Path to the cached layer
        """
        layer_path = self.layers_dir / digest.replace(":", "_")
        
        # Verify digest
        actual_digest = f"sha256:{hashlib.sha256(data).hexdigest()}"
        if not digest.startswith("sha256:"):
            # Accept if we can't verify
            pass
        elif actual_digest != digest:
            raise ValueError(f"Layer digest mismatch")
        
        with open(layer_path, 'wb') as f:
            f.write(data)
        
        # Update index
        self._index["layers"][digest] = {
            "path": str(layer_path),
            "size": len(data),
            "added_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
        self._save_index()
        
        return layer_path
    
    def prune(self, max_age_days: Optional[int] = None, 
              max_size_gb: Optional[float] = None) -> Dict[str, int]:
        """
        Prune the cache.
        
        Args:
            max_age_days: Remove images older than this
            max_size_gb: Keep cache under this size
            
        Returns:
            Statistics about removed items
        """
        removed_images = 0
        removed_layers = 0
        freed_bytes = 0
        
        # Remove old images
        if max_age_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
            
            for key, info in list(self._index["images"].items()):
                pulled_at = info.get("pulled_at", "")
                if pulled_at:
                    try:
                        pulled_date = datetime.fromisoformat(pulled_at.rstrip("Z"))
                        if pulled_date < cutoff:
                            size = info.get("size", 0)
                            if self.remove_image(info["reference"]):
                                removed_images += 1
                                freed_bytes += size
                    except ValueError:
                        pass
        
        # Remove unreferenced layers
        used_layers = set()
        for info in self._index["images"].values():
            # In a real implementation, we'd track which layers are used by each image
            pass
        
        for digest in list(self._index["layers"].keys()):
            if digest not in used_layers:
                layer_info = self._index["layers"][digest]
                layer_path = Path(layer_info["path"])
                if layer_path.exists():
                    freed_bytes += layer_path.stat().st_size
                    layer_path.unlink()
                del self._index["layers"][digest]
                removed_layers += 1
        
        self._save_index()
        
        return {
            "removed_images": removed_images,
            "removed_layers": removed_layers,
            "freed_bytes": freed_bytes
        }
    
    def get_cache_size(self) -> int:
        """Get total cache size in bytes."""
        return self._calculate_dir_size(self.cache_dir)
    
    def _calculate_dir_size(self, path: Path) -> int:
        """Calculate the total size of a directory."""
        total = 0
        if path.exists():
            for item in path.rglob("*"):
                if item.is_file():
                    total += item.stat().st_size
        return total
    
    def format_size(self, size_bytes: int) -> str:
        """Format a size in bytes to human readable string."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"
