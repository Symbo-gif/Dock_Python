"""
Utilities for finding and checking availability of network ports.
"""
import socket

def get_free_port() -> int:
    """
    Finds a free port on localhost.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def is_port_free(port: int) -> bool:
    """
    Checks if a port is free on localhost.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('', port))
            return True
        except socket.error:
            return False
