"""
Utilities for resolving the full execution command for a service.
"""
from typing import List, Optional

class EntrypointExecutor:
    """
    Handles the merging of ENTRYPOINT and CMD instructions according to Docker rules.
    """
    def get_full_command(self, entrypoint: List[str], cmd: List[str]) -> List[str]:
        """
        Combines entrypoint and cmd into a single command list.

        :param entrypoint: The ENTRYPOINT list.
        :param cmd: The CMD list.
        :return: The full command list.
        """
        # Docker rules:
        # If ENTRYPOINT is defined, it's the executable. CMD becomes arguments.
        # If ENTRYPOINT is not defined, CMD is the executable + arguments.
        
        if entrypoint:
            return entrypoint + cmd
        return cmd
