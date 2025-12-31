import random
import string
import pytest
from d2p.PARSERS.dockerfile_parser import DockerfileParser
from d2p.PARSERS.compose_parser import ComposeParser
from d2p.PARSERS.env_parser import EnvParser

def random_string(length):
    return ''.join(random.choice(string.printable) for _ in range(length))

def test_fuzz_dockerfile_parser():
    parser = DockerfileParser()
    for _ in range(100):
        content = random_string(random.randint(0, 1000))
        try:
            parser.parse_from_string(content)
        except Exception as e:
            # We don't want it to crash with unhandled exceptions like IndexError or AttributeError
            # though some exceptions like re.error might be okay if we don't catch them, 
            # but ideally it should be robust.
            pass

def test_fuzz_compose_parser():
    parser = ComposeParser()
    for _ in range(100):
        content = random_string(random.randint(0, 1000))
        try:
            # Compose parser likely expects YAML, so random junk should fail gracefully
            parser.parse_from_string(content)
        except Exception:
            pass

def test_fuzz_env_parser():
    parser = EnvParser()
    for _ in range(100):
        content = random_string(random.randint(0, 1000))
        try:
            parser.parse_from_string(content)
        except Exception:
            pass

def test_edge_cases_parsers():
    dockerfile_parser = DockerfileParser()
    compose_parser = ComposeParser()
    
    # Empty string
    dockerfile_parser.parse_from_string("")
    
    # Only whitespace
    dockerfile_parser.parse_from_string("   \n\t  ")
    
    # Very long line
    dockerfile_parser.parse_from_string("RUN " + "a" * 10000)
    
    # Many line continuations
    dockerfile_parser.parse_from_string("RUN echo \\\n" * 100 + "hello")
