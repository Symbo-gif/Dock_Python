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
