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
Dependency resolution for services to determine startup and shutdown order.
"""
from typing import List, Dict, Set
from ..MODELS.orchestration_config import OrchestrationConfig


class DependencyResolver:
    """
    Resolves the startup and shutdown order of services based on their dependencies.
    """

    def resolve_order(self, config: OrchestrationConfig) -> List[str]:
        """
        Determines the correct order to start services using topological sort.

        :param config: The orchestration configuration.
        :return: Service names in the order they should be started.
        :raises Exception: If a circular dependency is detected.
        """
        services = config.services
        dependencies = {name: set(svc.depends_on) for name, svc in services.items()}

        ordered = []
        visited = set()
        processing = set()

        def visit(name):
            """
            Recursive function for topological sort.
            """
            if name in processing:
                raise Exception(f"Circular dependency detected involving {name}")
            if name not in visited:
                processing.add(name)
                for dep in dependencies.get(name, []):
                    if dep in services:  # Only depend on services defined in the config
                        visit(dep)
                processing.remove(name)
                visited.add(name)
                ordered.append(name)

        for name in services:
            visit(name)

        return ordered
