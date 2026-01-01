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
