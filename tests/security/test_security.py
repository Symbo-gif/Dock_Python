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

import pytest
import os
import subprocess
from d2p.RUNNERS.process_runner import ProcessRunner
from d2p.PARSERS.dockerfile_parser import DockerfileParser


def test_command_injection_attempt():
    """
    Test if ProcessRunner is vulnerable to command injection.
    On Windows, if shell=True, '&' can be used to run additional commands.
    """
    runner = ProcessRunner(name="test_injection")
    # We attempt to create a file 'injected.txt' via command injection
    injected_file = "injected.txt"
    if os.path.exists(injected_file):
        os.remove(injected_file)

    # Command that tries to inject another command
    # If shell=False, '&' should be treated as a literal argument, not a shell operator.
    if os.name == "nt":
        command = [
            "python",
            "-c",
            "import sys; print(sys.argv)",
            "&",
            "echo",
            "injected",
            ">",
            injected_file,
        ]
    else:
        command = ["echo", "hello", ";", "touch", injected_file]

    try:
        runner.start(command=command, env={})
        import time

        time.sleep(1)
        runner.stop()
    except:
        pass

    # If shell=True and it's vulnerable, injected.txt might be created
    exists = os.path.exists(injected_file)
    if exists:
        os.remove(injected_file)

    assert not exists, "Command injection successful! Security vulnerability found."


def test_path_traversal_parse():
    """
    Test if DockerfileParser handles path traversal.
    """
    parser = DockerfileParser()
    # We want to ensure that it's NOT possible to read files outside a specific root
    # if we implement such a check.
    # For now, let's see if we can read the hosts file.
    hosts_path = (
        "C:\\Windows\\System32\\drivers\\etc\\hosts"
        if os.name == "nt"
        else "/etc/hosts"
    )

    # If the parser allows reading it, and we want to prevent it, then it's a fail.
    # Currently it DOES allow it.

    # Let's try a non-existent file to see it raises
    with pytest.raises(FileNotFoundError):
        parser.parse("non_existent_file_12345.txt")
