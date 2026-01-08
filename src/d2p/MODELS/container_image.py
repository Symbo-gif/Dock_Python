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
