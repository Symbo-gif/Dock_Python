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
Managers for handling environment variables and .env file resolution.
"""
import os
from typing import Dict, List, Optional
from ..PARSERS.env_parser import EnvParser

class EnvironmentManager:
    """
    Manages the merging and resolution of environment variables from multiple sources.
    """
    def __init__(self, base_dir: str = "."):
        """
        Initializes the environment manager.

        :param base_dir: The base directory for resolving relative paths to .env files.
        """
        self.base_dir = base_dir
        self.parser = EnvParser()

    def get_merged_environment(self, 
                               explicit_env: Dict[str, str], 
                               env_files: List[str]) -> Dict[str, str]:
        """
        Merges environment variables from the current process, specified .env files,
        and explicit environment variable definitions.

        :param explicit_env: A dictionary of explicitly defined environment variables.
        :param env_files: A list of paths to .env files.
        :return: A dictionary containing the merged environment variables.
        """
        merged_env = os.environ.copy()
        
        # 1. Load from env files (later files override earlier ones)
        for env_file in env_files:
            file_path = os.path.join(self.base_dir, env_file)
            if os.path.exists(file_path):
                file_env = self.parser.parse(file_path)
                merged_env.update(file_env)
                
        # 2. Explicit environment variables override everything
        merged_env.update(explicit_env)
        
        return merged_env
