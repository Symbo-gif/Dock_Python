"""
Utilities for string interpolation using environment variables.
"""
import re
from typing import Dict, Optional

class EnvironmentInterpolator:
    """
    Utility for interpolating environment variables in strings.
    Supports ${VAR}, ${VAR:-default}, and ${VAR:+value}.
    """
    @staticmethod
    def interpolate(template: str, context: Dict[str, str]) -> str:
        """
        Interpolates environment variables in the template string using the provided context.

        :param template: The string containing ${VAR} placeholders.
        :param context: The environment variables context.
        :return: The interpolated string.
        :raises KeyError: If a variable is not found and no default is provided.
        """
        # Pattern: ${VAR:-default} or ${VAR:+value} or ${VAR}
        # Group 1: VAR name
        # Group 2: :-default or :+value part
        # Group 3: - or +
        # Group 4: default or value
        pattern = r'\$\{([^}:]+)(?::(-|\+)([^}]*))?\}'
        
        def replace(match):
            """
            Internal replacement function for re.sub.
            """
            var_name = match.group(1)
            modifier = match.group(2)  # None, '-', or '+'
            alt_value = match.group(3) # default_val or value_if_set
            
            value = context.get(var_name)
            
            if modifier == '-':
                # ${VAR:-default} -> use default if VAR is unset or empty
                return value if value else alt_value
            elif modifier == '+':
                # ${VAR:+value} -> use alt_value if VAR is set and not empty, else empty
                return alt_value if value else ''
            else:
                # ${VAR}
                if value is not None:
                    return value
                else:
                    # In Docker, ${VAR} if unset usually resolves to empty string 
                    # but sometimes it raises an error depending on the context.
                    # The strategy document said: raise KeyError(f"Variable {var_name} not found")
                    # Let's stick to that for now if no modifier is present.
                    raise KeyError(f"Variable {var_name} not found in context")
        
        return re.sub(pattern, replace, template)
