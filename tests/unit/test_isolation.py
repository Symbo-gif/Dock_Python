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
Unit tests for the isolation module.
"""
import sys
import pytest
from d2p.ISOLATION.namespace_manager import NamespaceManager, NamespaceConfig, NamespaceType
from d2p.ISOLATION.cgroup_manager import CgroupManager, ResourceLimits
from d2p.ISOLATION.isolated_runner import IsolatedRunner, IsolationConfig


class TestNamespaceManager:
    """Tests for NamespaceManager."""
    
    def test_init_default(self):
        """Test default initialization."""
        mgr = NamespaceManager()
        assert mgr.config.namespaces == NamespaceType.NONE
        
    def test_init_with_config(self):
        """Test initialization with config."""
        config = NamespaceConfig(namespaces=NamespaceType.BASIC, hostname="test")
        mgr = NamespaceManager(config)
        assert mgr.config.namespaces == NamespaceType.BASIC
        assert mgr.config.hostname == "test"
    
    def test_is_available_depends_on_platform(self):
        """Test availability check."""
        mgr = NamespaceManager()
        # On non-Linux, should not be available
        if not sys.platform.startswith('linux'):
            assert not mgr.is_available
    
    def test_get_isolation_level(self):
        """Test isolation level description."""
        mgr = NamespaceManager()
        level = mgr.get_isolation_level()
        assert isinstance(level, str)
        assert len(level) > 0


class TestCgroupManager:
    """Tests for CgroupManager."""
    
    def test_init(self):
        """Test initialization."""
        mgr = CgroupManager("test-service")
        assert mgr.name == "test-service"
    
    def test_sanitize_name(self):
        """Test name sanitization."""
        assert CgroupManager._sanitize_name("foo/bar") == "foo_bar"
        assert CgroupManager._sanitize_name("..test") == "_test"
        assert CgroupManager._sanitize_name(".hidden") == "hidden"
    
    def test_parse_memory_string(self):
        """Test memory string parsing."""
        assert CgroupManager.parse_memory_string("512m") == 512 * 1024 * 1024
        assert CgroupManager.parse_memory_string("1g") == 1024 * 1024 * 1024
        assert CgroupManager.parse_memory_string("100") == 100
        assert CgroupManager.parse_memory_string("2gb") == 2 * 1024 * 1024 * 1024
        assert CgroupManager.parse_memory_string("") is None
        assert CgroupManager.parse_memory_string("invalid") is None
    
    def test_resource_limits_cpu_calculation(self):
        """Test CPU quota calculation from CPUs."""
        limits = ResourceLimits(cpus=0.5)
        assert limits.cpu_quota == 50000  # 0.5 * 100000


class TestIsolatedRunner:
    """Tests for IsolatedRunner."""
    
    def test_init(self):
        """Test initialization."""
        runner = IsolatedRunner("test")
        assert runner.name == "test"
    
    def test_init_with_config(self):
        """Test initialization with config."""
        config = IsolationConfig(
            hostname="test-host",
            cpu_limit=0.5,
            memory_limit="256m"
        )
        runner = IsolatedRunner("test", config)
        assert runner.config.hostname == "test-host"
        assert runner.config.cpu_limit == 0.5
    
    def test_get_isolation_summary(self):
        """Test isolation summary."""
        runner = IsolatedRunner("test")
        summary = runner.get_isolation_summary()
        assert "namespaces" in summary
        assert "cgroups" in summary
        assert "filesystem" in summary
    
    def test_is_linux(self):
        """Test Linux detection."""
        runner = IsolatedRunner("test")
        expected = sys.platform.startswith('linux')
        assert runner.is_linux == expected
