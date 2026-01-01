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
Parsers for Docker Compose YAML files.
"""
import yaml
from typing import Dict, Any, List, Optional
from ..MODELS.orchestration_config import OrchestrationConfig
from ..MODELS.service_definition import ServiceDefinition, RestartPolicy, VolumeMount
from ..UTILS.string_interpolation import EnvironmentInterpolator
import os

class ComposeParser:
    """
    Parser for docker-compose.yml files.
    """
    def __init__(self, context: Optional[Dict[str, str]] = None):
        """
        Initializes the parser with an optional environment context for interpolation.

        :param context: A dictionary of environment variables for interpolation.
        """
        self.context = context or dict(os.environ)

    def parse(self, compose_path: str) -> OrchestrationConfig:
        """
        Parses a compose file from a path.

        :param compose_path: Path to the compose file.
        :return: Parsed configuration.
        """
        with open(compose_path, 'r') as f:
            content = f.read()
        return self.parse_from_string(content)

    def parse_from_string(self, content: str) -> OrchestrationConfig:
        """
        Parses a compose file from a string.

        :param content: YAML content of the compose file.
        :return: Parsed configuration.
        """
        # Interpolate variables before parsing YAML
        try:
            content = EnvironmentInterpolator.interpolate(content, self.context)
        except KeyError as e:
            # For compose files, we might want to warn or use empty string instead of failing hard
            # but for now let's see. 
            # In Docker, ${VAR} if unset is empty string.
            print(f"Warning during interpolation: {e}")
            
        data = yaml.safe_load(content)
        if not data:
            data = {}
        
        services = {}
        for name, spec in data.get('services', {}).items():
            services[name] = self._parse_service(name, spec)
            
        return OrchestrationConfig(
            services=services,
            networks=list(data.get('networks', {}).keys()) if data.get('networks') else [],
            volumes=list(data.get('volumes', {}).keys()) if data.get('volumes') else []
        )

    def _parse_service(self, name: str, spec: Dict[str, Any]) -> ServiceDefinition:
        """
        Parses a single service definition from a compose file.

        :param name: The name of the service.
        :param spec: The service specification dictionary.
        :return: A ServiceDefinition instance.
        """
        # Restart policy
        restart = spec.get('restart', 'no')
        restart_policy = RestartPolicy(condition=restart)
        
        # Volumes
        volumes = []
        for v in spec.get('volumes', []):
            if isinstance(v, str):
                parts = v.split(':')
                if len(parts) == 2:
                    volumes.append(VolumeMount(source=parts[0], target=parts[1]))
                elif len(parts) == 3:
                    volumes.append(VolumeMount(source=parts[0], target=parts[1], read_only=(parts[2] == 'ro')))
            elif isinstance(v, dict):
                volumes.append(VolumeMount(**v))

        # Ports
        ports = {}
        for p in spec.get('ports', []):
            if isinstance(p, str):
                parts = p.split(':')
                if len(parts) == 2:
                    ports[int(parts[1])] = int(parts[0])
                else:
                    ports[int(parts[0])] = None
            elif isinstance(p, dict):
                ports[p['target']] = p.get('published')

        # Environment
        environment = {}
        env_spec = spec.get('environment', [])
        if isinstance(env_spec, list):
            for e in env_spec:
                if '=' in e:
                    k, v = e.split('=', 1)
                    environment[k] = v
        elif isinstance(env_spec, dict):
            environment = env_spec

        return ServiceDefinition(
            name=name,
            image_name=spec.get('image', ''),
            build_context=spec.get('build', {}).get('context') if isinstance(spec.get('build'), dict) else spec.get('build'),
            dockerfile_path=spec.get('build', {}).get('dockerfile') if isinstance(spec.get('build'), dict) else None,
            cmd=self._to_list(spec.get('command', [])),
            entrypoint=self._to_list(spec.get('entrypoint', [])),
            working_dir=spec.get('working_dir'),
            environment=environment,
            environment_files=self._to_list(spec.get('env_file', [])),
            ports=ports,
            volumes=volumes,
            restart_policy=restart_policy,
            depends_on=list(spec.get('depends_on', {}).keys()) if isinstance(spec.get('depends_on'), dict) else spec.get('depends_on', [])
        )

    def _to_list(self, val: Any) -> List[str]:
        """
        Helper to ensure a value is a list of strings.

        :param val: The value to convert.
        :return: A list of strings.
        """
        if val is None:
            return []
        if isinstance(val, str):
            return [val]
        return list(val)
