# D2P - Docker to Python

A production-ready Docker alternative that runs containerized workloads as native Python processes with container-like isolation on Linux.

## Overview

D2P (Docker to Python) converts Docker Compose configurations and Dockerfiles into native system processes. It provides:

- **Process Isolation**: Linux namespaces (PID, NET, MNT, IPC, UTS) for process isolation
- **Resource Limits**: cgroup v2 integration for CPU, memory, and I/O constraints  
- **Filesystem Isolation**: chroot/pivot_root implementation for filesystem views
- **Image Registry**: Pull images from Docker Hub and OCI-compatible registries
- **Network Virtualization**: Virtual networks with DNS-based service discovery
- **Volume Management**: Named volumes, bind mounts, and tmpfs support
- **Health Monitoring**: Docker-style health checks with restart policies

## Installation

```bash
pip install d2p
```

Or install from source:

```bash
git clone https://github.com/Symbo-gif/Dock_Python.git
cd Dock_Python
pip install -e .
```

## Quick Start

### Running Docker Compose Files

```bash
# Start services
d2p up

# Start in background
d2p up -d

# View status
d2p ps

# View logs
d2p logs

# Stop services
d2p down
```

### Using a Custom Compose File

```bash
d2p -f my-compose.yml up
```

### Image Management

```bash
# Pull an image from Docker Hub
d2p image pull nginx:latest

# List cached images
d2p image ls

# Get image information
d2p image info python:3.12
```

### Volume Management

```bash
# List volumes
d2p volume ls

# Create a volume
d2p volume create my-data

# Remove a volume
d2p volume rm my-data

# Prune unused volumes
d2p volume prune
```

### System Information

```bash
d2p info
```

## Architecture

D2P follows a clean modular architecture:

```
PARSERS → MODELS → CONVERTERS → RUNNERS → MANAGERS
```

### Components

- **PARSERS**: Parse Docker Compose YAML and Dockerfiles
- **MODELS**: Pydantic models for services, images, and configurations
- **BUILDERS**: Build images from Dockerfiles with layer caching
- **RUNNERS**: Execute processes with lifecycle management
- **MANAGERS**: Orchestrate services, networks, volumes, and health
- **ISOLATION**: Linux namespace, cgroup, and filesystem isolation
- **REGISTRY**: Pull images from Docker Hub and OCI registries

## Isolation Features

### Linux Namespaces

On Linux with appropriate privileges, D2P can isolate processes using:

- **PID namespace**: Separate process ID space
- **NET namespace**: Isolated network stack
- **MNT namespace**: Private mount points
- **IPC namespace**: Separate IPC resources
- **UTS namespace**: Custom hostname

### Resource Limits (cgroups v2)

Control resource usage per service:

```yaml
services:
  web:
    image: nginx
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
```

### Filesystem Isolation

When running as root on Linux:
- chroot for filesystem isolation
- Bind mounts for volumes
- tmpfs for temporary filesystems

## Docker Compose Support

D2P supports common Docker Compose features:

```yaml
version: '3.8'

services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
    environment:
      DEBUG: "true"
    volumes:
      - ./html:/usr/share/nginx/html:ro
    depends_on:
      - api
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost"]
      interval: 30s
      timeout: 10s
      retries: 3

  api:
    build:
      context: ./api
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
    environment:
      DATABASE_URL: postgres://db:5432/app

  db:
    image: postgres:13
    volumes:
      - db_data:/var/lib/postgresql/data
    environment:
      POSTGRES_PASSWORD: secret

volumes:
  db_data:
```

## Dockerfile Support

D2P can parse and build from Dockerfiles:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "app.py"]
```

### Multi-Stage Builds

```dockerfile
FROM node:18 AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
```

## API Usage

### Programmatic Usage

```python
from d2p.PARSERS.compose_parser import ComposeParser
from d2p.MANAGERS.service_orchestrator import ServiceOrchestrator

# Parse compose file
parser = ComposeParser()
config = parser.parse("docker-compose.yml")

# Create orchestrator
orchestrator = ServiceOrchestrator(config)

# Start services
orchestrator.up()

# Get status
status = orchestrator.ps()
print(status)

# Stop services
orchestrator.down()
```

### Using the Registry Client

```python
from d2p.REGISTRY.registry_client import RegistryClient

client = RegistryClient()

# Get image info
info = client.get_image_info("nginx:latest")
print(info)

# Pull image
rootfs = client.pull_image("python:3.12-slim")
```

### Using Isolation Features

```python
from d2p.ISOLATION import IsolatedRunner, IsolationConfig, NamespaceType

config = IsolationConfig(
    namespaces=NamespaceType.BASIC,
    hostname="my-container",
    cpu_limit=0.5,
    memory_limit="256m"
)

runner = IsolatedRunner("my-service", config)
process = runner.run(["python", "app.py"], env={"DEBUG": "1"})
```

## Platform Support

| Feature | Linux (root) | Linux (user) | macOS | Windows |
|---------|-------------|--------------|-------|---------|
| Process orchestration | ✅ | ✅ | ✅ | ✅ |
| Docker Compose parsing | ✅ | ✅ | ✅ | ✅ |
| Dockerfile parsing | ✅ | ✅ | ✅ | ✅ |
| Image pulling | ✅ | ✅ | ✅ | ✅ |
| Namespace isolation | ✅ | Partial | ❌ | ❌ |
| Cgroup limits | ✅ | ❌ | ❌ | ❌ |
| Filesystem isolation | ✅ | ❌ | ❌ | ❌ |

## Requirements

- Python 3.9+
- Linux for full isolation features (works on all platforms with reduced features)

### Dependencies

- pydantic >= 2.0
- pyyaml >= 6.0
- click >= 8.0
- psutil >= 5.9
- tenacity >= 8.0
- python-dotenv >= 1.0
- jinja2 >= 3.0

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

### Code Style

```bash
black src/ tests/
```

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Authors

- Michael Maillet
- Damien Davison
- Sacha Davison

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
