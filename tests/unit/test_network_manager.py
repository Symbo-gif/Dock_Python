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
Unit tests for the enhanced network manager.
"""
import pytest
from d2p.MANAGERS.network_manager import NetworkManager, NetworkConfig, NetworkMode
from d2p.MODELS.service_definition import ServiceDefinition


class TestNetworkManager:
    """Tests for NetworkManager."""

    def test_init_creates_default_network(self):
        """Test that default network is created."""
        mgr = NetworkManager()
        assert "d2p_default" in mgr.networks

    def test_create_network(self):
        """Test network creation."""
        mgr = NetworkManager()
        config = NetworkConfig(name="test-net", subnet="172.20.0.0/16")
        result = mgr.create_network(config)
        assert result is True
        assert "test-net" in mgr.networks

    def test_remove_network(self):
        """Test network removal."""
        mgr = NetworkManager()
        config = NetworkConfig(name="test-net")
        mgr.create_network(config)
        result = mgr.remove_network("test-net")
        assert result is True
        assert "test-net" not in mgr.networks

    def test_connect_service(self):
        """Test connecting a service to a network."""
        mgr = NetworkManager()
        ip = mgr.connect_service("web", "d2p_default", aliases=["webserver"])
        assert ip is not None
        assert "web" in mgr.service_networks
        assert "web" in mgr.dns_entries
        assert "webserver" in mgr.dns_entries

    def test_get_service_discovery_env(self):
        """Test service discovery environment generation."""
        mgr = NetworkManager()
        mgr.connect_service("db", "d2p_default")
        env = mgr.get_service_discovery_env(["db"])
        assert "DB_HOST" in env
        assert env["DB_HOST"] != ""

    def test_resolve_hostname(self):
        """Test hostname resolution."""
        mgr = NetworkManager()
        mgr.connect_service("api", "d2p_default")
        ip = mgr.resolve_hostname("api")
        assert ip is not None

    def test_generate_hosts_content(self):
        """Test hosts file content generation."""
        mgr = NetworkManager()
        mgr.connect_service("web", "d2p_default")
        content = mgr.generate_hosts_file_content()
        assert "localhost" in content
        assert "web" in content

    def test_cleanup(self):
        """Test cleanup."""
        mgr = NetworkManager()
        mgr.connect_service("test", "d2p_default")
        mgr.cleanup()
        assert len(mgr.service_networks) == 0
        assert len(mgr.dns_entries) == 0


class TestNetworkMode:
    """Tests for NetworkMode enum."""

    def test_network_modes(self):
        """Test network mode values."""
        assert NetworkMode.BRIDGE == "bridge"
        assert NetworkMode.HOST == "host"
        assert NetworkMode.NONE == "none"
