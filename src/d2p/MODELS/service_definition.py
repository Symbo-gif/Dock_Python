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
Models for defining services, including restart policies, health checks, and mounts.
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class RestartPolicyCondition(str, Enum):
    """
    Conditions under which a service should be restarted.
    """

    NO = "no"
    ALWAYS = "always"
    ON_FAILURE = "on-failure"
    UNLESS_STOPPED = "unless-stopped"


class RestartPolicy(BaseModel):
    """
    Defines how a service should be restarted on failure or exit.
    """

    condition: RestartPolicyCondition = RestartPolicyCondition.NO
    max_retries: int = 0
    delay: float = 0.0


class HealthCheck(BaseModel):
    """
    Defines a command to run to check the health of a service.
    """

    test: List[str]
    interval: float = 30.0
    timeout: float = 30.0
    retries: int = 3
    start_period: float = 0.0


class VolumeMount(BaseModel):
    """
    Defines a mapping between a host path and a service path.
    """

    source: str
    target: str
    read_only: bool = False


class ServiceDefinition(BaseModel):
    """
    The full definition of a single service, translated from Docker Compose.
    """

    name: str
    image_name: str
    build_context: Optional[str] = None
    dockerfile_path: Optional[str] = None

    # Execution
    cmd: List[str] = []
    entrypoint: List[str] = []
    working_dir: Optional[str] = None

    # Environment
    environment: Dict[str, str] = {}
    environment_files: List[str] = []

    # Networking
    ports: Dict[int, Optional[int]] = {}  # {container: host}
    expose_ports: List[int] = []
    networks: List[str] = []
    hostname: Optional[str] = None

    # Storage
    volumes: List[VolumeMount] = []
    tmpfs: List[str] = []

    # Lifecycle
    restart_policy: RestartPolicy = Field(default_factory=RestartPolicy)
    health_check: Optional[HealthCheck] = None
    depends_on: List[str] = []

    # Resources
    cpu_limit: Optional[float] = None
    memory_limit: Optional[str] = None

    # Metadata
    labels: Dict[str, str] = {}
    user: Optional[str] = None
