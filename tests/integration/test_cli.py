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
