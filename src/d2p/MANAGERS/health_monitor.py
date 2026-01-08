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
Health monitoring for services, including process status, health check commands,
and restart policy management with exponential backoff.
"""
import subprocess
import threading
import time
from typing import Dict, Callable, Optional, Any, List, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone

from .process_manager import ProcessManager


class HealthStatus(str, Enum):
    """Health status of a service."""

    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    NONE = "none"  # No health check configured


@dataclass
class ServiceHealth:
    """Health information for a service."""

    status: HealthStatus = HealthStatus.NONE
    failing_streak: int = 0
    last_check: Optional[str] = None
    last_output: str = ""
    restart_count: int = 0
    last_restart: Optional[str] = None


class HealthMonitor:
    """
    Monitors the health of services and triggers callbacks on failure.
    Supports Docker-style health check commands with retries and restart policies.
    """

    def __init__(
        self,
        managers: Dict[str, ProcessManager],
        interval: int = 5,
        on_failure: Optional[Callable[[str], None]] = None,
    ):
        """
        Initializes the health monitor.

        :param managers: Managers for the services to monitor.
        :param interval: Seconds between health checks.
        :param on_failure: Callback when a service fails.
        """
        self.managers = managers
        self.interval = interval
        self.on_failure = on_failure
        self.running = False
        self.thread = None

        # Health tracking per service
        self._health: Dict[str, ServiceHealth] = {}
        for name in managers:
            self._health[name] = ServiceHealth()

        # Restart backoff tracking
        self._restart_delays: Dict[str, float] = {}
        self._max_restart_delay = 300  # 5 minutes max

    def start(self):
        """
        Starts the health monitoring thread.
        """
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """
        Stops the health monitoring thread.
        """
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)

    def get_health(self, service_name: str) -> ServiceHealth:
        """
        Get the health status of a service.

        Args:
            service_name: Name of the service.

        Returns:
            ServiceHealth object.
        """
        return self._health.get(service_name, ServiceHealth())

    def get_all_health(self) -> Dict[str, ServiceHealth]:
        """Get health status of all services."""
        return self._health.copy()

    def _monitor_loop(self):
        """
        Internal monitoring loop that periodically checks the health of all services.
        """
        # Track start period for each service
        start_times: Dict[str, float] = {}

        while self.running:
            current_time = time.time()

            for name, manager in self.managers.items():
                if name not in start_times:
                    start_times[name] = current_time

                health = self._health[name]
                hc = manager.service_def.health_check

                # Check if process is running
                if not manager.runner.is_running():
                    exit_code = manager.runner.get_exit_code()

                    # Handle restart policy
                    should_restart = self._should_restart(name, manager, exit_code)

                    if should_restart:
                        self._handle_restart(name, manager)
                    elif self.on_failure:
                        self.on_failure(name)

                    health.status = HealthStatus.UNHEALTHY
                    continue

                # If no health check, just check if running
                if not hc:
                    health.status = HealthStatus.NONE
                    continue

                # Check if still in start period
                elapsed = current_time - start_times.get(name, current_time)
                if elapsed < hc.start_period:
                    health.status = HealthStatus.STARTING
                    continue

                # Run health check
                check_result = self._run_health_check(name, manager)

                health.last_check = (
                    datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                )

                if check_result["success"]:
                    health.status = HealthStatus.HEALTHY
                    health.failing_streak = 0
                    health.last_output = check_result.get("output", "")
                    # Reset restart delay on success
                    self._restart_delays[name] = 0
                else:
                    health.failing_streak += 1
                    health.last_output = check_result.get("error", "")

                    # Check if exceeded retries
                    if health.failing_streak >= hc.retries:
                        health.status = HealthStatus.UNHEALTHY

                        # Trigger failure callback
                        if self.on_failure:
                            self.on_failure(name)
                    else:
                        health.status = HealthStatus.UNHEALTHY

            time.sleep(self.interval)

    def _run_health_check(self, name: str, manager: ProcessManager) -> Dict[str, Any]:
        """
        Run the health check command for a service.

        Args:
            name: Service name.
            manager: Process manager for the service.

        Returns:
            Dictionary with 'success', 'output', and 'error' keys.
        """
        hc = manager.service_def.health_check
        if not hc or not hc.test:
            return {"success": True}

        try:
            cmd = hc.test
            use_shell = False

            # Parse command format
            if cmd[0] == "CMD":
                real_cmd: Union[List[str], str] = cmd[1:]
            elif cmd[0] == "CMD-SHELL":
                real_cmd = cmd[1] if len(cmd) > 1 else ""
                use_shell = True
            elif cmd[0] == "NONE":
                return {"success": True}
            else:
                real_cmd = cmd

            # Get environment
            env = manager.env_manager.get_merged_environment(
                manager.service_def.environment, manager.service_def.environment_files
            )

            # Run the check
            result = subprocess.run(
                real_cmd,
                shell=use_shell,
                env=env,
                capture_output=True,
                timeout=hc.timeout,
                text=True,
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "output": result.stdout[:500] if result.stdout else "",
                }
            else:
                return {
                    "success": False,
                    "error": (
                        result.stderr[:500]
                        if result.stderr
                        else f"Exit code: {result.returncode}"
                    ),
                }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Health check timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _should_restart(
        self, name: str, manager: ProcessManager, exit_code: Optional[int]
    ) -> bool:
        """
        Determine if a service should be restarted based on its policy.

        Args:
            name: Service name.
            manager: Process manager.
            exit_code: Process exit code.

        Returns:
            True if should restart.
        """
        policy = manager.service_def.restart_policy
        condition = policy.condition

        if condition == "no":
            return False

        if condition == "always":
            return True

        if condition == "on-failure":
            # Restart only if exited with non-zero code
            return exit_code is not None and exit_code != 0

        if condition == "unless-stopped":
            # In our case, similar to always since we don't track explicit stops
            return True

        return False

    def _handle_restart(self, name: str, manager: ProcessManager) -> None:
        """
        Handle restarting a service with backoff.

        Args:
            name: Service name.
            manager: Process manager.
        """
        policy = manager.service_def.restart_policy
        health = self._health[name]

        # Check max retries
        if policy.max_retries > 0 and health.restart_count >= policy.max_retries:
            print(
                f"Service {name} exceeded max restart attempts ({policy.max_retries})"
            )
            return

        # Calculate delay with exponential backoff
        base_delay = policy.delay if policy.delay > 0 else 1.0
        current_delay = self._restart_delays.get(name, base_delay)

        # Wait before restart
        if current_delay > 0:
            print(f"Waiting {current_delay:.1f}s before restarting {name}...")
            time.sleep(current_delay)

        # Restart the service
        print(f"Restarting service {name} (attempt {health.restart_count + 1})...")
        try:
            manager.stop()
            manager.start()

            health.restart_count += 1
            health.last_restart = (
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )

            # Increase delay for next time (exponential backoff)
            self._restart_delays[name] = min(current_delay * 2, self._max_restart_delay)

        except Exception as e:
            print(f"Failed to restart {name}: {e}")

    def reset_health(self, name: str) -> None:
        """
        Reset health tracking for a service.

        Args:
            name: Service name.
        """
        self._health[name] = ServiceHealth()
        self._restart_delays[name] = 0
