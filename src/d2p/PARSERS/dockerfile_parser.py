"""
Parsers for Dockerfiles, extracting instructions and arguments.
"""
import re
from typing import List
from ..MODELS.dockerfile_ast import Instruction

class DockerfileParser:
    """
    Parser for Dockerfile instructions.
    """
    def parse(self, dockerfile_path: str) -> List[Instruction]:
        """
        Parses a Dockerfile from a file path.

        Args:
            dockerfile_path (str): Path to the Dockerfile.

        Returns:
            List[Instruction]: List of parsed instructions.
        """
        with open(dockerfile_path, 'r') as f:
            content = f.read()
        return self.parse_from_string(content)

    def parse_from_string(self, content: str) -> List[Instruction]:
        """
        Parses a Dockerfile from a string content.

        Args:
            content (str): Content of the Dockerfile.

        Returns:
            List[Instruction]: List of parsed instructions.
        """
        instructions = []
        
        # 1. Remove comments
        content = re.sub(r'^\s*#.*$', '', content, flags=re.MULTILINE)
        
        # 2. Handle line continuations with \
        # Only replace \ followed by optional whitespace and a newline
        content = re.sub(r'\\\s*\n', ' ', content)
        
        # 3. Match instructions
        # Dockerfile instructions must start a line, but can be preceded by whitespace
        pattern = re.compile(r'^\s*([A-Z]+)\s+(.*)$', re.MULTILINE)
        
        for match in pattern.finditer(content):
            inst = match.group(1)
            args_str = match.group(2).strip()
            
            # 4. Handle JSON/Exec form vs Shell form
            if args_str.startswith('[') and args_str.endswith(']'):
                import json
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    # Not valid JSON, treat as shell form
                    args = [args_str]
            else:
                # Shell form
                # For ENV, it can be KEY=VALUE or KEY VALUE
                if inst == "ENV":
                    # If it contains =, it's KEY=VALUE
                    if '=' in args_str:
                        # Could be multiple KEY=VALUE on same line
                        args = re.findall(r'(\S+=\S+)', args_str)
                    else:
                        args = args_str.split(None, 1)
                else:
                    args = [args_str]
            
            instructions.append(Instruction(
                instruction=inst,
                arguments=args,
                raw=match.group(0).strip()
            ))
            
        return instructions
