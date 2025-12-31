import pytest
import time
from d2p.MANAGERS.service_orchestrator import ServiceOrchestrator
from d2p.MODELS.service_definition import ServiceDefinition
from d2p.MODELS.orchestration_config import OrchestrationConfig

def test_stress_orchestration():
    """
    Stress test by orchestrating 50 services simultaneously.
    (Reducing from 100 to 50 to avoid overloading the CI environment)
    """
    services = {}
    for i in range(50):
        name = f"service_{i}"
        services[name] = ServiceDefinition(
            name=name,
            image_name="dummy",
            cmd=["python", "-c", "import time; time.sleep(1)"],
            environment={},
            ports={},
            volumes=[],
            depends_on=[]
        )
    
    config = OrchestrationConfig(services=services)
    orchestrator = ServiceOrchestrator(config=config)
    
    start_time = time.time()
    orchestrator.up()
    end_time = time.time()
    
    # Starting 50 simple processes should be relatively fast
    # but we mostly care that it doesn't crash
    print(f"Started 50 services in {end_time - start_time:.2f}s")
    
    status = orchestrator.ps()
    assert len(status) == 50
    for name, s in status.items():
        assert s == "running" or "exited" in s
        
    orchestrator.down()

def test_large_config_parsing():
    from d2p.PARSERS.compose_parser import ComposeParser
    parser = ComposeParser()
    
    # Generate a large compose file
    content = "services:\n"
    for i in range(1000):
        content += f"  service_{i}:\n"
        content += f"    image: image_{i}\n"
        content += f"    environment:\n"
        content += f"      - VAR_{i}=VALUE_{i}\n"
        
    start_time = time.time()
    parser.parse_from_string(content)
    end_time = time.time()
    
    assert end_time - start_time < 2.0  # Should parse 1000 services in less than 2 seconds
