"""
Network management for services, handling port allocation and service discovery.
"""
from typing import Dict, List, Optional
from ..UTILS.port_finder import get_free_port, is_port_free
from ..MODELS.service_definition import ServiceDefinition

class NetworkManager:
    """
    Manages network-related aspects like port mapping and service discovery.
    """
    def __init__(self):
        """
        Initializes the network manager.
        """
        self.service_ports: Dict[str, Dict[int, int]] = {} # service_name -> {container_port: host_port}
        self.host_port_to_service: Dict[int, str] = {} # host_port -> service_name

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
        return mappings

    def get_service_discovery_env(self, all_services: List[str]) -> Dict[str, str]:
        """
        Generates environment variables for service discovery.
        Example: DB_HOST=127.0.0.1, DB_PORT=5432
        """
        env = {}
        for name in all_services:
            prefix = name.upper().replace('-', '_')
            env[f"{prefix}_HOST"] = "127.0.0.1"
            
            # If the service has ports, we use the first one as the "default" port
            if name in self.service_ports and self.service_ports[name]:
                # We usually want the first mapped port
                container_ports = list(self.service_ports[name].keys())
                # Prefer common ports if multiple exist (e.g. 80, 443, 3306, 5432)
                # For now just pick the first one
                env[f"{prefix}_PORT"] = str(self.service_ports[name][container_ports[0]])
                
        return env

    def get_host_port(self, service_name: str, container_port: int) -> Optional[int]:
        """
        Returns the host port for a given service and container port.
        """
        return self.service_ports.get(service_name, {}).get(container_port)
