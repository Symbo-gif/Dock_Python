import os
import time
import yaml
from d2p.PARSERS.compose_parser import ComposeParser
from d2p.MANAGERS.service_orchestrator import ServiceOrchestrator

def test_multi_service_up_down(tmp_path):
    dummy_script = os.path.abspath("tests/integration/dummy_service.py")
    
    compose_content = {
        'services': {
            'db': {
                'image': 'dummy-db',
                'command': ['python', dummy_script],
                'environment': {'APP_ENV': 'prod', 'PYTHONUNBUFFERED': '1'}
            },
            'web': {
                'image': 'dummy-web',
                'command': ['python', dummy_script],
                'depends_on': ['db'],
                'environment': {'APP_ENV': 'prod', 'PYTHONUNBUFFERED': '1'}
            }
        }
    }
    
    compose_file = tmp_path / "docker-compose.yml"
    with open(compose_file, 'w') as f:
        yaml.dump(compose_content, f)
        
    parser = ComposeParser()
    config = parser.parse(str(compose_file))
    
    orchestrator = ServiceOrchestrator(config, base_dir=str(tmp_path))
    
    # Up
    orchestrator.up()
    
    status = orchestrator.ps()
    assert status['db'] == 'running'
    assert status['web'] == 'running'
    
    # Wait a bit
    time.sleep(2)
    
    # Down
    orchestrator.down()
    
    status = orchestrator.ps()
    assert 'exited' in status['db'] or status['db'] == 'stopped'
    assert 'exited' in status['web'] or status['web'] == 'stopped'
    
    # Check logs
    db_log = tmp_path / ".d2p" / "logs" / "db.log"
    web_log = tmp_path / ".d2p" / "logs" / "web.log"
    assert db_log.exists()
    assert web_log.exists()
