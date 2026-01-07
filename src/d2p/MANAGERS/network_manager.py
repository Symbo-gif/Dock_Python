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
Network management for services, handling port allocation, service discovery,
virtual networks, and DNS-based resolution.
"""
import os
import sys
import socket
import subprocess
from typing import Dict, List, Optional, Set
from enum import Enum
from dataclasses import dataclass, field

from ..UTILS.port_finder import get_free_port, is_port_free
from ..MODELS.service_definition import ServiceDefinition


class NetworkMode(str, Enum):
    """Network modes for containers."""
    BRIDGE = "bridge"  # Default isolated network
    HOST = "host"      # Use host network directly
    NONE = "none"      # No networking
    CONTAINER = "container"  # Share with another container


@dataclass
class NetworkConfig:
    """Configuration for a virtual network."""
    name: str
    subnet: Optional[str] = None  # e.g., "172.18.0.0/16"
    gateway: Optional[str] = None  # e.g., "172.18.0.1"
    driver: str = "bridge"
    internal: bool = False  # If True, no external access
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class ServiceNetwork:
    """Network information for a service."""
    service_name: str
    networks: List[str]
    ip_address: Optional[str] = None
    aliases: List[str] = field(default_factory=list)


class NetworkManager:
    """
    Manages network-related aspects like port mapping, service discovery,
    and virtual network configuration.
    """
    
    def __init__(self):
        """
        Initializes the network manager.
        """
        self.service_ports: Dict[str, Dict[int, int]] = {}  # service_name -> {container_port: host_port}
        self.host_port_to_service: Dict[int, str] = {}  # host_port -> service_name
        self.networks: Dict[str, NetworkConfig] = {}  # network_name -> config
        self.service_networks: Dict[str, ServiceNetwork] = {}  # service_name -> network info
        self.dns_entries: Dict[str, str] = {}  # hostname -> ip
        self._is_linux = sys.platform.startswith('linux')
        self._allocated_ips: Dict[str, Set[str]] = {}  # network -> set of allocated IPs
        
        # Create default network
        self.create_network(NetworkConfig(name="d2p_default", subnet="172.28.0.0/16", gateway="172.28.0.1"))

    def create_network(self, config: NetworkConfig) -> bool:
        """
        Create a virtual network.
        
        Args:
            config: Network configuration.
            
        Returns:
            True if created successfully.
        """
        if config.name in self.networks:
            return True  # Already exists
        
        self.networks[config.name] = config
        self._allocated_ips[config.name] = set()
        
        # Reserve gateway IP if specified
        if config.gateway:
            self._allocated_ips[config.name].add(config.gateway)
        
        print(f"Created network: {config.name}")
        return True
    
    def remove_network(self, name: str) -> bool:
        """
        Remove a virtual network.
        
        Args:
            name: Network name.
            
        Returns:
            True if removed.
        """
        if name in self.networks:
            del self.networks[name]
            if name in self._allocated_ips:
                del self._allocated_ips[name]
            return True
        return False
    
    def connect_service(self, service_name: str, network_name: str, 
                       aliases: Optional[List[str]] = None) -> Optional[str]:
        """
        Connect a service to a network.
        
        Args:
            service_name: Name of the service.
            network_name: Name of the network.
            aliases: DNS aliases for the service.
            
        Returns:
            Allocated IP address, or None if failed.
        """
        if network_name not in self.networks:
            # Create the network if it doesn't exist
            self.create_network(NetworkConfig(name=network_name))
        
        # Allocate IP
        ip = self._allocate_ip(network_name)
        if not ip:
            return None
        
        # Store service network info
        if service_name not in self.service_networks:
            self.service_networks[service_name] = ServiceNetwork(
                service_name=service_name,
                networks=[network_name],
                ip_address=ip,
                aliases=aliases or []
            )
        else:
            self.service_networks[service_name].networks.append(network_name)
            if not self.service_networks[service_name].ip_address:
                self.service_networks[service_name].ip_address = ip
        
        # Add DNS entries
        self.dns_entries[service_name] = ip
        for alias in (aliases or []):
            self.dns_entries[alias] = ip
        
        return ip
    
    def _allocate_ip(self, network_name: str) -> Optional[str]:
        """Allocate an IP address from a network's subnet."""
        if network_name not in self.networks:
            return None
        
        config = self.networks[network_name]
        if not config.subnet:
            # No subnet, return localhost
            return "127.0.0.1"
        
        # Parse subnet (simple implementation)
        try:
            base_ip, prefix = config.subnet.split("/")
            prefix_len = int(prefix)
            
            # Convert base IP to integer
            parts = [int(p) for p in base_ip.split(".")]
            base_int = (parts[0] << 24) + (parts[1] << 16) + (parts[2] << 8) + parts[3]
            
            # Calculate number of available IPs
            host_bits = 32 - prefix_len
            num_ips = (1 << host_bits) - 2  # Exclude network and broadcast
            
            # Find first available IP (starting from .2)
            for offset in range(2, num_ips + 2):
                ip_int = base_int + offset
                ip = f"{(ip_int >> 24) & 0xFF}.{(ip_int >> 16) & 0xFF}.{(ip_int >> 8) & 0xFF}.{ip_int & 0xFF}"
                
                if ip not in self._allocated_ips.get(network_name, set()):
                    self._allocated_ips[network_name].add(ip)
                    return ip
            
        except (ValueError, IndexError):
            pass
        
        return "127.0.0.1"
    
    def allocate_ports(self, service_def: ServiceDefinition) -> Dict[int, int]:
        """
        Allocates host ports for a service based on its definition.
        
        :param service_def: The service definition.
        :return: Mapping from container port to allocated host port.
        """
        mappings = {}
        for container_port, host_port in service_def.ports.items():
            if host_port is None:
                # Dynamically allocate
                allocated_port = get_free_port()
            else:
                if is_port_free(host_port):
                    allocated_port = host_port
                else:
                    # In a real system, we might fail here or try another port
                    # Docker usually fails if the requested host port is taken.
                    raise RuntimeError(f"Port {host_port} is already in use, cannot start service {service_def.name}")
            
            mappings[container_port] = allocated_port
            self.host_port_to_service[allocated_port] = service_def.name
            
        self.service_ports[service_def.name] = mappings
        
        # Connect to networks
        networks = service_def.networks or ["d2p_default"]
        for network in networks:
            self.connect_service(service_def.name, network, aliases=[service_def.name])
        
        return mappings

    def get_service_discovery_env(self, all_services: List[str]) -> Dict[str, str]:
        """
        Generates environment variables for service discovery.
        Includes DNS-style entries for container networking.
        """
        env = {}
        for name in all_services:
            prefix = name.upper().replace('-', '_').replace('.', '_')
            
            # Use allocated IP if available, otherwise localhost
            if name in self.service_networks and self.service_networks[name].ip_address:
                host = self.service_networks[name].ip_address
            else:
                host = "127.0.0.1"
            
            env[f"{prefix}_HOST"] = host
            
            # If the service has ports, we use the first one as the "default" port
            if name in self.service_ports and self.service_ports[name]:
                container_ports = list(self.service_ports[name].keys())
                env[f"{prefix}_PORT"] = str(self.service_ports[name][container_ports[0]])
        
        return env
    
    def get_dns_env(self) -> Dict[str, str]:
        """
        Get environment variables for DNS resolution.
        These can be used in /etc/hosts or similar.
        """
        env = {}
        for hostname, ip in self.dns_entries.items():
            key = f"D2P_DNS_{hostname.upper().replace('-', '_').replace('.', '_')}"
            env[key] = f"{ip} {hostname}"
        return env
    
    def generate_hosts_file_content(self) -> str:
        """
        Generate content for an /etc/hosts-style file.
        
        Returns:
            Hosts file content as a string.
        """
        lines = ["127.0.0.1 localhost", "::1 localhost"]
        
        for hostname, ip in self.dns_entries.items():
            lines.append(f"{ip} {hostname}")
        
        return "\n".join(lines) + "\n"
    
    def get_host_port(self, service_name: str, container_port: int) -> Optional[int]:
        """
        Returns the host port for a given service and container port.
        """
        return self.service_ports.get(service_name, {}).get(container_port)
    
    def get_service_ip(self, service_name: str) -> Optional[str]:
        """
        Get the IP address of a service.
        
        Args:
            service_name: Service name.
            
        Returns:
            IP address or None.
        """
        if service_name in self.service_networks:
            return self.service_networks[service_name].ip_address
        return self.dns_entries.get(service_name)
    
    def resolve_hostname(self, hostname: str) -> Optional[str]:
        """
        Resolve a hostname to an IP address.
        
        Args:
            hostname: Hostname to resolve.
            
        Returns:
            IP address or None.
        """
        # Check local DNS entries first
        if hostname in self.dns_entries:
            return self.dns_entries[hostname]
        
        # Fall back to system DNS
        try:
            return socket.gethostbyname(hostname)
        except socket.gaierror:
            return None
    
    def cleanup(self) -> None:
        """Clean up network resources."""
        self.service_ports.clear()
        self.host_port_to_service.clear()
        self.service_networks.clear()
        self.dns_entries.clear()
        self._allocated_ips.clear()
