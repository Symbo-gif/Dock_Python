"""
Converters for transforming Docker Compose configurations into standalone Python packages.
"""
import os
import shutil
from ..MODELS.orchestration_config import OrchestrationConfig

PACKAGE_MAIN_TEMPLATE = """
import os
import sys
from d2p.PARSERS.compose_parser import ComposeParser
from d2p.MANAGERS.service_orchestrator import ServiceOrchestrator

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    compose_file = os.path.join(base_dir, "docker-compose.yml")
    
    if not os.path.exists(compose_file):
        print(f"Error: {compose_file} not found.")
        sys.exit(1)
        
    parser = ComposeParser()
    config = parser.parse(compose_file)
    orchestrator = ServiceOrchestrator(config, base_dir=base_dir)
    
    try:
        orchestrator.up()
        print("Services are running. Press Ctrl+C to stop.")
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        orchestrator.down()
        print("Services stopped.")

if __name__ == "__main__":
    main()
"""

class PythonPackageConverter:
    """
    Converts a Docker Compose setup into a native Python package structure
    that uses d2p to run services.
    """
    def __init__(self, config: OrchestrationConfig, source_dir: str):
        """
        Initializes the converter.

        :param config: The parsed orchestration configuration.
        :param source_dir: The source directory containing the project files.
        """
        self.config = config
        self.source_dir = os.path.abspath(source_dir)

    def convert(self, output_dir: str):
        """
        Performs the conversion to a Python package.

        :param output_dir: The directory where the package will be generated.
        :return: The path to the generated package.
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. Copy original source (excluding what we don't want)
        for item in os.listdir(self.source_dir):
            if item in ['.git', '__pycache__', '.pytest_cache', output_dir]:
                continue
            s = os.path.join(self.source_dir, item)
            d = os.path.join(output_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
                
        # 2. Generate main entry point
        with open(os.path.join(output_dir, "run_native.py"), 'w') as f:
            f.write(PACKAGE_MAIN_TEMPLATE)
            
        # 3. Create a requirements.txt if not exists
        req_file = os.path.join(output_dir, "requirements_native.txt")
        with open(req_file, 'w') as f:
            f.write("d2p\n")
            
        print(f"Python package generated in {output_dir}")
        print("You can run it with: python run_native.py")
        return output_dir
