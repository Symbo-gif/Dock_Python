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

from d2p.PARSERS.env_parser import EnvParser

def test_parse_from_string():
    content = """
    KEY1=VALUE1
    KEY2 = VALUE2
    # This is a comment
    KEY3="VALUE3" # Trailing comment
    KEY4='VALUE4'
    """
    env = EnvParser.parse_from_string(content)
    assert env['KEY1'] == 'VALUE1'
    assert env['KEY2'] == 'VALUE2'
    assert env['KEY3'] == 'VALUE3'
    assert env['KEY4'] == 'VALUE4'
    assert 'KEY5' not in env
