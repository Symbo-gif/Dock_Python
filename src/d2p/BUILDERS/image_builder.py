"""
Builders for converting Dockerfiles into internal image models and preparing environments.
"""
import os
import subprocess
from typing import Optional
from ..PARSERS.dockerfile_parser import DockerfileParser
from ..MODELS.container_image import ContainerImage

class ImageBuilder:
    """
    Analyzes Dockerfiles and builds an internal representation of the image,
    capable of preparing a corresponding native environment.
    """
    def __init__(self, base_dir: str = "."):
        """
        Initializes the ImageBuilder.

        :param base_dir: The base directory for resolving relative paths.
        """
        self.base_dir = base_dir
        self.parser = DockerfileParser()

    def build(self, dockerfile_path: str, image_name: str) -> ContainerImage:
        """
        Parses a Dockerfile and creates a ContainerImage model.

        :param dockerfile_path: Path to the Dockerfile.
        :param image_name: Name to assign to the resulting image.
        :return: A ContainerImage instance.
        """
        full_path = os.path.join(self.base_dir, dockerfile_path)
        instructions = self.parser.parse(full_path)
        
        image = ContainerImage(name=image_name, base_image="")
        
        for inst in instructions:
            cmd = inst.instruction
            args = inst.arguments
            
            if cmd == "FROM":
                image.base_image = args[0]
            elif cmd == "WORKDIR":
                image.working_directory = args[0]
            elif cmd == "ENV":
                # Handle ENV KEY=VALUE or ENV KEY VALUE
                for arg in args:
                    if '=' in arg:
                        k, v = arg.split('=', 1)
                        image.env_vars[k] = v
            elif cmd == "RUN":
                image.run_instructions.append(" ".join(args))
                # Detect pip install
                if "pip install" in " ".join(args):
                    if "-r" in " ".join(args):
                        # Should probably parse requirements file
                        image.pip_requirements.append("from requirements.txt")
            elif cmd == "CMD":
                image.cmd = args
            elif cmd == "ENTRYPOINT":
                image.entrypoint = args
                
        return image

    def prepare_environment(self, image: ContainerImage):
        """
        Creates a virtual environment for the service and installs dependencies.
        """
        venv_path = os.path.join(self.base_dir, ".d2p", "venvs", image.name)
        print(f"Preparing environment for {image.name} in {venv_path}")
        
        if not os.path.exists(venv_path):
            os.makedirs(os.path.dirname(venv_path), exist_ok=True)
            subprocess.run(["python", "-m", "venv", venv_path], check=True)
        
        pip_path = os.path.join(venv_path, "Scripts", "pip.exe") if os.name == "nt" else os.path.join(venv_path, "bin", "pip")
        
        for inst in image.run_instructions:
            if "pip install" in inst:
                print(f"Executing dependency installation: {inst}")
                # Replace 'pip' with the actual venv pip path
                cmd = inst.replace("pip", pip_path)
                subprocess.run(cmd, shell=True, check=True)
        
        # Store venv path in image for later use by process runner
        image.labels["d2p.venv_path"] = venv_path
