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
Execution of system processes with log redirection and lifecycle management.
"""
import subprocess
import os
from typing import List, Dict, Optional
import sys

class ProcessRunner:
    """
    Manages the execution of a single system process.
    """
    def __init__(self, name: str, log_file: Optional[str] = None):
        """
        Initializes the process runner.

        Args:
            name (str): Identifier for the process.
            log_file (Optional[str]): Path to a file where stdout/stderr will be redirected.
        """
        self.name = name
        self.log_file = log_file
        self.process = None

    def start(self, 
              command: List[str], 
              env: Dict[str, str], 
              working_dir: Optional[str] = None):
        """
        Starts the process.

        Args:
            command (List[str]): Command and arguments to execute.
            env (Dict[str, str]): Environment variables for the process.
            working_dir (Optional[str]): Directory to start the process in.
        """
        
        # Ensure working_dir exists
        if working_dir and not os.path.exists(working_dir):
            os.makedirs(working_dir, exist_ok=True)

        stdout = sys.stdout
        stderr = sys.stderr
        
        if self.log_file:
            log_dir = os.path.dirname(self.log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            self.log_handle = open(self.log_file, 'a')
            stdout = self.log_handle
            stderr = self.log_handle

        print(f"[{self.name}] Starting command: {' '.join(command)}")
        
        try:
            self.process = subprocess.Popen(
                command,
                env=env,
                cwd=working_dir,
                stdout=stdout,
                stderr=stderr,
                text=True,
                # Avoid shell=True for security reasons (CWE-78)
                shell=False
            )
        except Exception as e:
            print(f"[{self.name}] Failed to start: {e}")
            raise

    def stop(self, timeout: int = 10):
        """
        Stops the process by sending SIGTERM, followed by SIGKILL if it doesn't stop.

        Args:
            timeout (int): Seconds to wait for termination before killing.
        """
        if self.process:
            print(f"[{self.name}] Stopping process...")
            self.process.terminate()
            try:
                self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                print(f"[{self.name}] Process did not terminate, killing...")
                self.process.kill()
            
            if hasattr(self, 'log_handle'):
                self.log_handle.close()

    def is_running(self) -> bool:
        """
        Checks if the process is currently running.

        Returns:
            bool: True if running, False otherwise.
        """
        return self.process is not None and self.process.poll() is None

    def get_exit_code(self) -> Optional[int]:
        """
        Gets the exit code of the process.

        Returns:
            Optional[int]: Exit code if process finished, None otherwise.
        """
        if self.process:
            return self.process.poll()
        return None
