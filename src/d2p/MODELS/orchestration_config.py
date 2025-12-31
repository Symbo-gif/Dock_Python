"""
Models for overall orchestration configuration.
"""
from typing import List, Dict
from pydantic import BaseModel
from .service_definition import ServiceDefinition

class OrchestrationConfig(BaseModel):
    """
    Complete configuration for a multi-service stack.
    Equivalent to a parsed docker-compose.yml file.
    """
    services: Dict[str, ServiceDefinition]
    networks: List[str] = []
    volumes: List[str] = []
