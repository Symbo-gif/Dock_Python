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
                    if dep in services: # Only depend on services defined in the config
                        visit(dep)
                processing.remove(name)
                visited.add(name)
                ordered.append(name)

        for name in services:
            visit(name)
            
        return ordered
