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
from click.testing import CliRunner
from d2p.CLI.main import cli
import os
import yaml

def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'Start services' in result.output

def test_cli_up_no_file():
    runner = CliRunner()
    result = runner.invoke(cli, ['-f', 'non_existent.yml', 'up'])
    assert result.exit_code == 0
    assert 'Error: non_existent.yml not found.' in result.output

def test_cli_convert_help():
    runner = CliRunner()
    result = runner.invoke(cli, ['convert', '--help'])
    assert result.exit_code == 0
    assert '--type' in result.output
