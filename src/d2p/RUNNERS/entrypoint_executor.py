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
