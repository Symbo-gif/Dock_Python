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

import os
import time
from d2p.MODELS.service_definition import ServiceDefinition
from d2p.MANAGERS.process_manager import ProcessManager

def test_single_service_lifecycle(tmp_path):
    # Setup
    dummy_script = os.path.abspath("tests/integration/dummy_service.py")
    
    service_def = ServiceDefinition(
        name="test-service",
        image_name="python:3.12",
        cmd=["python", dummy_script],
        environment={"DEBUG": "true", "PYTHONUNBUFFERED": "1"},
    )
    
    manager = ProcessManager(service_def, base_dir=str(tmp_path))
    
    # Start
    manager.start()
    assert manager.status() == "running"
    
    # Wait a bit
    time.sleep(2)
    assert manager.status() == "running"
    
    # Stop
    manager.stop()
    assert manager.status() in ["exited(1)", "exited(0)", "stopped", "exited(-15)"] # Depending on how it was killed
    
    # Check logs
    log_file = tmp_path / ".d2p" / "logs" / "test-service.log"
    assert log_file.exists()
    content = log_file.read_text()
    assert "Dummy service starting..." in content
    assert "DEBUG: true" in content
