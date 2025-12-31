"""
Parsers for .env files, supporting quotes and comments.
"""
import re
from typing import Dict

class EnvParser:
    """
    Parser for .env files.
    """
    @staticmethod
    def parse(env_path: str) -> Dict[str, str]:
        """
        Parses an .env file from a path.

        Args:
            env_path (str): Path to the .env file.

        Returns:
            Dict[str, str]: Dictionary of environment variables.
        """
        with open(env_path, 'r') as f:
            content = f.read()
        return EnvParser.parse_from_string(content)

    @staticmethod
    def parse_from_string(content: str) -> Dict[str, str]:
        """
        Parses environment variables from a string.
        Handles quotes, comments and escaped characters.
        """
        env = {}
        # Pattern to find KEY=VALUE
        # Key: alphanumeric and underscore
        # Value: everything until newline, handling quotes
        lines = content.splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if '=' not in line:
                continue
                
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            
            if not key:
                continue
                
            # Strip trailing comments if not quoted
            if '#' in value:
                # We need to be careful not to strip # inside quotes
                # Simple check: if there is a # and it's after the first quote, 
                # but we'll just do a simpler one for now: 
                # if it starts with a quote, we find the matching end quote
                if value.startswith('"') or value.startswith("'"):
                    quote = value[0]
                    end_quote_idx = value.find(quote, 1)
                    if end_quote_idx != -1:
                        value = value[:end_quote_idx+1]
                else:
                    value = value.split('#')[0].strip()

            # Handle quotes
            if len(value) >= 2:
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    quote = value[0]
                    value = value[1:-1]
                    # Unescape same quote
                    value = value.replace(f'\\{quote}', quote)
                
            env[key] = value
            
        return env
