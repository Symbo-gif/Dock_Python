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
Converters for generating systemd service files from Docker Compose configurations.
"""
import os
from jinja2 import Template
from ..MODELS.orchestration_config import OrchestrationConfig

SYSTEMD_TEMPLATE = """
[Unit]
Description=D2P Service: {{ name }}
After=network.target {% for dep in depends_on %} d2p-{{ dep }}.service{% endfor %}

[Service]
Type=simple
User={{ user or 'root' }}
WorkingDirectory={{ working_dir or base_dir }}
ExecStart={{ command | join(' ') }}
{% for k, v in environment.items() %}
Environment={{ k }}={{ v }}
{% endfor %}
Restart={{ restart_policy }}

[Install]
WantedBy=multi-user.target
"""


class SystemdConverter:
    """
    Converts a Docker Compose configuration into systemd unit files.
    """

    def __init__(self, config: OrchestrationConfig, base_dir: str = "."):
        """
        Initializes the systemd converter.

        :param config: The parsed orchestration configuration.
        :param base_dir: The base directory for resolving paths.
        """
        self.config = config
        self.base_dir = os.path.abspath(base_dir)
        self.template = Template(SYSTEMD_TEMPLATE)

    def convert(self, output_dir: str = "systemd"):
        """
        Generates systemd service files.

        :param output_dir: The directory where service files will be created.
        :return: The path to the output directory.
        """
        os.makedirs(output_dir, exist_ok=True)

        for name, svc in self.config.services.items():
            content = self.template.render(
                name=name,
                depends_on=svc.depends_on,
                user=svc.user,
                working_dir=svc.working_dir,
                base_dir=self.base_dir,
                command=svc.entrypoint + svc.cmd,
                environment=svc.environment,
                restart_policy=svc.restart_policy.condition,
            )

            with open(os.path.join(output_dir, f"d2p-{name}.service"), "w") as f:
                f.write(content)

        print(f"Systemd service files generated in {output_dir}")
        return output_dir
