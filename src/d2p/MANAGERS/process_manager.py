"""
Lifecycle management for individual service processes.
"""
import os
from typing import Optional, Dict
from ..MODELS.service_definition import ServiceDefinition
from ..RUNNERS.process_runner import ProcessRunner
from ..RUNNERS.entrypoint_executor import EntrypointExecutor
from .environment_manager import EnvironmentManager
from .volume_manager import VolumeManager

class ProcessManager:
    """
    Manages the lifecycle of a single service.
    """
    def __init__(self, 
                 service_def: ServiceDefinition, 
                 base_dir: str = "."):
        """
        Initializes the process manager for a service.

        :param service_def: Definition of the service.
        :param base_dir: Base directory for logs and relative paths.
        """
        self.service_def = service_def
        self.base_dir = base_dir
        
        self.env_manager = EnvironmentManager(base_dir)
        self.volume_manager = VolumeManager(base_dir)
        self.executor = EntrypointExecutor()
        log_path = os.path.join(base_dir, ".d2p", "logs", f"{service_def.name}.log")
        self.runner = ProcessRunner(service_def.name, 
                                    log_file=log_path)

    def start(self, extra_env: Optional[Dict[str, str]] = None):
        """
        Prepares the environment, volumes, and starts the service process.
        
        :param extra_env: Additional environment variables (e.g., service discovery).
        """
        # 1. Prepare Environment
        env = self.env_manager.get_merged_environment(
            self.service_def.environment,
            self.service_def.environment_files
        )
        if extra_env:
            env.update(extra_env)
        
        # 2. Prepare Volumes
        self.volume_manager.prepare_volumes(self.service_def.volumes, service_working_dir=self.service_def.working_dir)
        
        # 3. Resolve Command
        command = self.executor.get_full_command(
            self.service_def.entrypoint,
            self.service_def.cmd
        )
        
        if not command:
            print(f"[{self.service_def.name}] No command specified, nothing to run.")
            return

        # 3.5 Use venv if available
        # We can check labels or just check if a venv exists for this service
        venv_path = os.path.join(self.base_dir, ".d2p", "venvs", self.service_def.name)
        if os.path.exists(venv_path):
            python_exe = os.path.join(venv_path, "Scripts", "python.exe") if os.name == "nt" else os.path.join(venv_path, "bin", "python")
            if command[0] == "python":
                command[0] = python_exe
            elif command[0].endswith("pip"):
                pip_exe = os.path.join(venv_path, "Scripts", "pip.exe") if os.name == "nt" else os.path.join(venv_path, "bin", "pip")
                command[0] = pip_exe
            # Also add venv bin to PATH
            venv_bin = os.path.dirname(python_exe)
            path_sep = ";" if os.name == "nt" else ":"
            env["PATH"] = venv_bin + path_sep + env.get("PATH", "")

        # 4. Start Process
        self.runner.start(
            command,
            env=env,
            working_dir=self.service_def.working_dir
        )

    def stop(self):
        """
        Stops the service process.
        """
        self.runner.stop()

    def status(self) -> str:
        """
        Gets the current status of the service.

        :return: Status string (e.g., 'running', 'stopped', 'exited(0)').
        """
        if self.runner.is_running():
            return "running"
        exit_code = self.runner.get_exit_code()
        if exit_code is None:
            return "stopped"
        return f"exited({exit_code})"
