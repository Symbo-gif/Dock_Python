# Copyright 2024 Michael Maillet, Damien Davison, Sacha Davison
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Command Line Interface for D2P.
"""
import click
import os
import sys
from ..PARSERS.compose_parser import ComposeParser
from ..MANAGERS.service_orchestrator import ServiceOrchestrator
from ..MANAGERS.log_aggregator import LogAggregator
from ..MANAGERS.volume_manager import VolumeManager
from ..CONVERTERS.to_python_package import PythonPackageConverter
from ..CONVERTERS.to_systemd import SystemdConverter


@click.group()
@click.option('--file', '-f', default='docker-compose.yml', help='Compose file path')
@click.pass_context
def cli(ctx, file):
    """
    D2P - Docker to Process converter and orchestrator.
    
    Allows running Docker Compose setups as native system processes
    with container-like isolation on Linux.
    """
    ctx.ensure_object(dict)
    ctx.obj['file'] = file
    if os.path.exists(file):
        parser = ComposeParser()
        ctx.obj['config'] = parser.parse(file)
        ctx.obj['orchestrator'] = ServiceOrchestrator(ctx.obj['config'])


@cli.command()
@click.option('--detach', '-d', is_flag=True, help='Run in background')
@click.pass_context
def up(ctx, detach):
    """Start services defined in the compose file."""
    orchestrator = ctx.obj.get('orchestrator')
    if orchestrator:
        try:
            orchestrator.up()
            click.echo("Services started.")
            
            if not detach:
                click.echo("Running... Press Ctrl+C to stop.")
                # Keep main thread alive and wait for interrupt
                import time
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            click.echo("\nStopping services...")
            orchestrator.down()
        except Exception as e:
            click.echo(f"Error: {e}")
    else:
        click.echo(f"Error: {ctx.obj['file']} not found.")


@cli.command()
@click.pass_context
def down(ctx):
    """Stop all running services."""
    orchestrator = ctx.obj.get('orchestrator')
    if orchestrator:
        orchestrator.down()
        click.echo("Services stopped.")
    else:
        click.echo(f"Error: {ctx.obj['file']} not found.")


@cli.command()
@click.pass_context
def ps(ctx):
    """List service status."""
    orchestrator = ctx.obj.get('orchestrator')
    if orchestrator:
        status = orchestrator.ps()
        click.echo(f"{'SERVICE':20} {'STATUS':15}")
        click.echo("-" * 35)
        for name, state in status.items():
            click.echo(f"{name:20} {state:15}")
    else:
        click.echo(f"Error: {ctx.obj['file']} not found.")


@cli.command()
@click.pass_context
@click.argument('services', nargs=-1)
def logs(ctx, services):
    """Tail logs for services."""
    config = ctx.obj.get('config')
    if not config:
        click.echo(f"Error: {ctx.obj['file']} not found.")
        return
        
    if not services:
        services = list(config.services.keys())
    
    aggregator = LogAggregator(".d2p/logs")
    aggregator.tail_logs(list(services))


@cli.command()
@click.option('--type', '-t', type=click.Choice(['python', 'systemd']), default='python')
@click.option('--out', '-o', default='dist', help='Output directory')
@click.pass_context
def convert(ctx, type, out):
    """Convert to native format."""
    config = ctx.obj.get('config')
    if not config:
        click.echo(f"Error: {ctx.obj['file']} not found.")
        return

    if type == 'python':
        converter = PythonPackageConverter(config, source_dir=".")
        converter.convert(out)
    elif type == 'systemd':
        converter = SystemdConverter(config)
        converter.convert(out)


# Volume management commands
@cli.group()
def volume():
    """Manage volumes."""
    pass


@volume.command('ls')
def volume_list():
    """List all volumes."""
    vm = VolumeManager()
    volumes = vm.list_volumes()
    
    if not volumes:
        click.echo("No volumes found.")
        return
    
    click.echo(f"{'VOLUME NAME':30} {'DRIVER':10} {'SIZE':15}")
    click.echo("-" * 55)
    for vol in volumes:
        size = vm.get_volume_size(vol.name)
        size_str = _format_size(size)
        click.echo(f"{vol.name:30} {vol.driver:10} {size_str:15}")


@volume.command('create')
@click.argument('name')
def volume_create(name):
    """Create a volume."""
    vm = VolumeManager()
    vol = vm.create_volume(name)
    click.echo(f"Created volume: {vol.name}")


@volume.command('rm')
@click.argument('name')
@click.option('--force', '-f', is_flag=True, help='Force removal')
def volume_remove(name, force):
    """Remove a volume."""
    vm = VolumeManager()
    if vm.remove_volume(name, force=force):
        click.echo(f"Removed volume: {name}")
    else:
        click.echo(f"Volume not found: {name}")


@volume.command('prune')
def volume_prune():
    """Remove unused volumes."""
    vm = VolumeManager()
    result = vm.prune()
    click.echo(f"Removed {len(result['volumes_removed'])} volume(s)")


# Image management commands  
@cli.group()
def image():
    """Manage images."""
    pass


@image.command('pull')
@click.argument('image_name')
def image_pull(image_name):
    """Pull an image from a registry."""
    try:
        from ..REGISTRY.registry_client import RegistryClient
        
        client = RegistryClient()
        rootfs = client.pull_image(image_name)
        click.echo(f"Image pulled to: {rootfs}")
    except Exception as e:
        click.echo(f"Error pulling image: {e}")


@image.command('ls')
def image_list():
    """List cached images."""
    try:
        from ..REGISTRY.image_cache import ImageCache
        
        cache = ImageCache()
        images = cache.list_images()
        
        if not images:
            click.echo("No images found.")
            return
        
        click.echo(f"{'REFERENCE':40} {'SIZE':15} {'PULLED':25}")
        click.echo("-" * 80)
        for img in images:
            size_str = _format_size(img.size)
            click.echo(f"{img.reference[:40]:40} {size_str:15} {img.pulled_at[:25]:25}")
    except Exception as e:
        click.echo(f"Error listing images: {e}")


@image.command('info')
@click.argument('image_name')
def image_info(image_name):
    """Get information about an image."""
    try:
        from ..REGISTRY.registry_client import RegistryClient
        
        client = RegistryClient()
        info = client.get_image_info(image_name)
        
        click.echo(f"Reference: {info.get('reference', 'N/A')}")
        click.echo(f"Digest: {info.get('digest', 'N/A')[:32]}...")
        click.echo(f"Created: {info.get('created', 'N/A')}")
        click.echo(f"OS/Arch: {info.get('os', 'N/A')}/{info.get('architecture', 'N/A')}")
        click.echo(f"Layers: {info.get('layers', 'N/A')}")
        
        if info.get('cmd'):
            click.echo(f"Cmd: {' '.join(info['cmd'])}")
        if info.get('entrypoint'):
            click.echo(f"Entrypoint: {' '.join(info['entrypoint'])}")
    except Exception as e:
        click.echo(f"Error getting image info: {e}")


# System commands
@cli.command()
def info():
    """Display system information."""
    click.echo("D2P - Docker to Python")
    click.echo(f"Python: {sys.version.split()[0]}")
    click.echo(f"Platform: {sys.platform}")
    
    # Check isolation capabilities
    is_linux = sys.platform.startswith('linux')
    is_root = False
    if is_linux:
        try:
            is_root = os.geteuid() == 0
        except AttributeError:
            pass
    
    click.echo(f"\nIsolation capabilities:")
    click.echo(f"  Linux: {'Yes' if is_linux else 'No'}")
    click.echo(f"  Root: {'Yes' if is_root else 'No'}")
    
    if is_linux:
        # Check cgroup v2
        cgroup_v2 = os.path.exists("/sys/fs/cgroup/cgroup.controllers")
        click.echo(f"  Cgroups v2: {'Yes' if cgroup_v2 else 'No'}")
        
        # Check user namespaces
        user_ns_file = "/proc/sys/kernel/unprivileged_userns_clone"
        if os.path.exists(user_ns_file):
            try:
                with open(user_ns_file, 'r') as f:
                    user_ns = f.read().strip() == "1"
                click.echo(f"  User namespaces: {'Yes' if user_ns else 'No'}")
            except:
                click.echo("  User namespaces: Unknown")


def _format_size(size_bytes: int) -> str:
    """Format a size in bytes to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def main():
    """
    Main entry point for the CLI.
    """
    cli(obj={})


if __name__ == '__main__':
    main()
