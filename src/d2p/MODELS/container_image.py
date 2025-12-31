"""
Models representing container images and their configurations.
"""
from typing import List, Dict, Optional
from pydantic import BaseModel

class ContainerImage(BaseModel):
    """
    Represents a parsed and processed container image definition, 
    translated into Python-centric concepts.
    """
    name: str
    base_image: str
    base_image_version: str = "latest"
    
    python_version: Optional[str] = None
    pip_requirements: List[str] = []
    system_dependencies: List[str] = []
    
    env_vars: Dict[str, str] = {}
    build_args: Dict[str, str] = {}
    
    working_directory: Optional[str] = None
    exposed_ports: List[int] = []
    volumes: List[str] = []
    
    cmd: List[str] = []
    entrypoint: List[str] = []
    
    run_instructions: List[str] = []
    
    labels: Dict[str, str] = {}
