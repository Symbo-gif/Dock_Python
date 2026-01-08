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
Models for the Dockerfile Abstract Syntax Tree.
"""
from typing import List, Optional, Any
from pydantic import BaseModel


class Instruction(BaseModel):
    """
    Represents a single instruction in a Dockerfile.
    """

    instruction: str
    arguments: List[str]
    raw: str


class DockerfileAST(BaseModel):
    """
    Represents the complete Abstract Syntax Tree of a Dockerfile.
    """

    instructions: List[Instruction] = []
