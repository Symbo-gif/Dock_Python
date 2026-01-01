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
Health monitoring for services, including process status and health check commands.
"""
import threading
import time
from typing import Dict, Callable, Optional
from .process_manager import ProcessManager

class HealthMonitor:
    """
    Monitors the health of services and triggers callbacks on failure.
    Supports both process status checks and Docker-style health check commands.
    """
    def __init__(self, 
                 managers: Dict[str, ProcessManager], 
                 interval: int = 5,
                 on_failure: Optional[Callable[[str], None]] = None):
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

    def _monitor_loop(self):
        """
        Internal monitoring loop that periodically checks the health of all services.
        """
        while self.running:
            for name, manager in self.managers.items():
                if not manager.runner.is_running():
                    # If it's not even running, it's failed
                    if self.on_failure:
                        self.on_failure(name)
                    continue

                hc = manager.service_def.health_check
                if hc:
                    # Run health check command
                    import subprocess
                    try:
                        # Docker health check 'test' is often ["CMD", "curl", "-f", "http://localhost"]
                        # or ["CMD-SHELL", "curl -f http://localhost || exit 1"]
                        cmd = hc.test
                        if cmd[0] == "CMD":
                            real_cmd = cmd[1:]
                        elif cmd[0] == "CMD-SHELL":
                            real_cmd = cmd[1]
                        else:
                            real_cmd = cmd
                        
                        # Use same environment as service
                        env = manager.env_manager.get_merged_environment(
                            manager.service_def.environment,
                            manager.service_def.environment_files
                        )
                        
                        result = subprocess.run(
                            real_cmd, 
                            shell=(cmd[0] == "CMD-SHELL"),
                            env=env,
                            capture_output=True,
                            timeout=hc.timeout
                        )
                        
                        if result.returncode != 0:
                            # In a real system we'd track retries
                            # For now, immediate failure if it fails
                            if self.on_failure:
                                self.on_failure(name)
                    except Exception as e:
                        print(f"Health check failed for {name}: {e}")
                        if self.on_failure:
                            self.on_failure(name)
            time.sleep(self.interval)
