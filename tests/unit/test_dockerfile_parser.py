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

from d2p.PARSERS.dockerfile_parser import DockerfileParser

def test_parse_from_string():
    content = """
    FROM python:3.9-slim
    WORKDIR /app
    COPY . .
    RUN pip install -r requirements.txt \
        && echo "done"
    ENV PORT=8080
    CMD ["python", "app.py"]
    """
    parser = DockerfileParser()
    instructions = parser.parse_from_string(content)
    
    inst_names = [i.instruction for i in instructions]
    assert "FROM" in inst_names
    assert "WORKDIR" in inst_names
    assert "RUN" in inst_names
    assert "CMD" in inst_names
    
    # Check CMD parsing (exec form)
    cmd_inst = next(i for i in instructions if i.instruction == "CMD")
    assert cmd_inst.arguments == ["python", "app.py"]
    
    # Check RUN with line continuation
    run_inst = next(i for i in instructions if i.instruction == "RUN")
    assert "&& echo \"done\"" in run_inst.arguments[0]
