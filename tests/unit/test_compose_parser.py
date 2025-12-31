import yaml
import os
from d2p.PARSERS.compose_parser import ComposeParser

def test_parse(tmp_path):
    compose_content = {
        'version': '3.8',
        'services': {
            'web': {
                'image': 'nginx:latest',
                'ports': ['80:80'],
                'environment': {
                    'DEBUG': 'true'
                },
                'restart': 'always'
            },
            'db': {
                'image': 'postgres:13',
                'volumes': ['db_data:/var/lib/postgresql/data']
            }
        },
        'volumes': {
            'db_data': {}
        }
    }
    
    compose_file = tmp_path / "docker-compose.yml"
    with open(compose_file, 'w') as f:
        yaml.dump(compose_content, f)
        
    parser = ComposeParser()
    config = parser.parse(str(compose_file))
    
    assert 'web' in config.services
    assert 'db' in config.services
    assert config.services['web'].image_name == 'nginx:latest'
    assert config.services['web'].ports == {80: 80}
    assert config.services['web'].environment['DEBUG'] == 'true'
    assert config.services['web'].restart_policy.condition == 'always'
    
    assert 'db_data' in config.volumes
    assert config.services['db'].volumes[0].source == 'db_data'
    assert config.services['db'].volumes[0].target == '/var/lib/postgresql/data'
