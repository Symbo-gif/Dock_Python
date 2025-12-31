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
