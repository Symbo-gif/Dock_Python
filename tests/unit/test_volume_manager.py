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
Unit tests for the enhanced volume manager.
"""
import os
import pytest
from d2p.MANAGERS.volume_manager import VolumeManager, NamedVolume


class TestVolumeManager:
    """Tests for VolumeManager."""
    
    def test_init(self, tmp_path):
        """Test initialization."""
        vm = VolumeManager(base_dir=str(tmp_path))
        assert os.path.exists(vm.volumes_root)
    
    def test_create_volume(self, tmp_path):
        """Test volume creation."""
        vm = VolumeManager(base_dir=str(tmp_path))
        vol = vm.create_volume("test-vol")
        assert vol.name == "test-vol"
        assert os.path.exists(vol.path)
    
    def test_create_volume_idempotent(self, tmp_path):
        """Test that creating the same volume twice returns existing volume."""
        vm = VolumeManager(base_dir=str(tmp_path))
        vol1 = vm.create_volume("test-vol")
        vol2 = vm.create_volume("test-vol")
        assert vol1.path == vol2.path
    
    def test_get_volume(self, tmp_path):
        """Test getting a volume."""
        vm = VolumeManager(base_dir=str(tmp_path))
        vm.create_volume("test-vol")
        vol = vm.get_volume("test-vol")
        assert vol is not None
        assert vol.name == "test-vol"
    
    def test_list_volumes(self, tmp_path):
        """Test listing volumes."""
        vm = VolumeManager(base_dir=str(tmp_path))
        vm.create_volume("vol1")
        vm.create_volume("vol2")
        volumes = vm.list_volumes()
        assert len(volumes) == 2
        names = [v.name for v in volumes]
        assert "vol1" in names
        assert "vol2" in names
    
    def test_remove_volume(self, tmp_path):
        """Test volume removal."""
        vm = VolumeManager(base_dir=str(tmp_path))
        vol = vm.create_volume("test-vol")
        result = vm.remove_volume("test-vol", force=True)
        assert result is True
        assert vm.get_volume("test-vol") is None
    
    def test_resolve_source_named_volume(self, tmp_path):
        """Test resolving named volume source."""
        vm = VolumeManager(base_dir=str(tmp_path))
        # Named volume (no path separators)
        path = vm.resolve_source("my-data")
        assert "my-data" in path
    
    def test_resolve_source_relative_path(self, tmp_path):
        """Test resolving relative path source."""
        vm = VolumeManager(base_dir=str(tmp_path))
        path = vm.resolve_source("./data")
        assert path.endswith("data")
    
    def test_resolve_target(self, tmp_path):
        """Test resolving target path."""
        vm = VolumeManager(base_dir=str(tmp_path))
        path = vm.resolve_target("/app/data")
        assert "app" in path
        assert "data" in path
    
    def test_get_volume_size(self, tmp_path):
        """Test getting volume size."""
        vm = VolumeManager(base_dir=str(tmp_path))
        vol = vm.create_volume("test-vol")
        
        # Create a file in the volume
        test_file = os.path.join(vol.path, "test.txt")
        with open(test_file, 'w') as f:
            f.write("Hello, World!")
        
        size = vm.get_volume_size("test-vol")
        assert size > 0
    
    def test_prune(self, tmp_path):
        """Test pruning empty volumes."""
        vm = VolumeManager(base_dir=str(tmp_path))
        vm.create_volume("empty-vol")
        result = vm.prune()
        assert "volumes_removed" in result
