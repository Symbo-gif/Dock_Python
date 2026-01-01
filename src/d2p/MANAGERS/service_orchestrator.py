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
Orchestration for multiple services, managing dependencies and health.
"""
from typing import Dict, List, Optional
from ..MODELS.orchestration_config import OrchestrationConfig
from .process_manager import ProcessManager
from ..RUNNERS.dependency_resolver import DependencyResolver
from .network_manager import NetworkManager
from .health_monitor import HealthMonitor
import time

class ServiceOrchestrator:
    """
    Orchestrates multiple services based on their dependencies.
    """
    def __init__(self, config: OrchestrationConfig, base_dir: str = "."):
        """
        Initializes the orchestrator.

        :param config: Configuration for all services.
        :param base_dir: Working directory for the services.
        """
        self.config = config
        self.base_dir = base_dir
        self.resolver = DependencyResolver()
        self.network_manager = NetworkManager()
        self.managers: Dict[str, ProcessManager] = {}
        
        for name, svc_def in config.services.items():
            # Allocate ports before creating manager
            self.network_manager.allocate_ports(svc_def)
            self.managers[name] = ProcessManager(svc_def, base_dir)
            
        self.health_monitor = HealthMonitor(self.managers, on_failure=self._handle_service_failure)

    def up(self):
        """
        Starts all services in the correct dependency order.
        """
        order = self.resolver.resolve_order(self.config)
        print(f"Starting services in order: {', '.join(order)}")
        
        # Get discovery env for all services
        discovery_env = self.network_manager.get_service_discovery_env(list(self.config.services.keys()))
        
        for name in order:
            print(f"Starting service: {name}...")
            manager = self.managers[name]
            manager.start(extra_env=discovery_env)
            
            # Wait for service to be healthy if health check is defined
            if manager.service_def.health_check:
                self._wait_for_healthy(name)
            else:
                # Basic wait to let process start
                time.sleep(1)

        self.health_monitor.start()

    def _wait_for_healthy(self, name: str):
        """
        Waits for a service to become healthy according to its health check definition.

        :param name: The name of the service to wait for.
        """
        manager = self.managers[name]
        hc = manager.service_def.health_check
        print(f"Waiting for {name} to become healthy...")
        
        # This is a bit simplified, ideally we'd use the HealthMonitor's check logic
        # For now, let's just check if it's running
        start_time = time.time()
        timeout = hc.start_period + (hc.timeout * hc.retries)
        
        while time.time() - start_time < timeout:
            if manager.status() == "running":
                # In a real system, we'd run the actual health check command here
                print(f"Service {name} is running.")
                return
            time.sleep(1)
        
        print(f"Warning: Service {name} failed to become healthy within timeout.")

    def down(self):
        """
        Stops all services in reverse dependency order.
        """
        self.health_monitor.stop()
        order = self.resolver.resolve_order(self.config)
        # Stop in reverse order
        for name in reversed(order):
            print(f"Stopping service: {name}...")
            self.managers[name].stop()

    def ps(self) -> Dict[str, str]:
        """
        Returns the status of all services.

        :return: Service names and their statuses.
        """
        return {name: manager.status() for name, manager in self.managers.items()}

    def _handle_service_failure(self, name: str):
        """
        Callback handled when a service failure is detected by the health monitor.

        :param name: The name of the failed service.
        """
        print(f"Service {name} failed! Checking restart policy...")
        manager = self.managers[name]
        policy = manager.service_def.restart_policy
        if policy.condition == "always" or policy.condition == "on-failure":
            print(f"Restarting service {name}...")
            # We should probably have a retry count here
            discovery_env = self.network_manager.get_service_discovery_env(list(self.config.services.keys()))
            manager.start(extra_env=discovery_env)
