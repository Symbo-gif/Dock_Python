"""
Command Line Interface for D2P.
"""
import click
import os
from ..PARSERS.compose_parser import ComposeParser
from ..MANAGERS.service_orchestrator import ServiceOrchestrator
from ..MANAGERS.log_aggregator import LogAggregator
from ..CONVERTERS.to_python_package import PythonPackageConverter
from ..CONVERTERS.to_systemd import SystemdConverter

@click.group()
@click.option('--file', '-f', default='docker-compose.yml', help='Compose file path')
@click.pass_context
def cli(ctx, file):
    """
    D2P - Docker to Process converter and orchestrator.
    
    Allows running Docker Compose setups as native system processes.
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
    """List service status"""
    orchestrator = ctx.obj.get('orchestrator')
    if orchestrator:
        status = orchestrator.ps()
        click.echo(f"{'SERVICE':15} {'STATUS':10}")
        click.echo("-" * 25)
        for name, state in status.items():
            click.echo(f"{name:15} {state:10}")
    else:
        click.echo(f"Error: {ctx.obj['file']} not found.")

@cli.command()
@click.pass_context
@click.argument('services', nargs=-1)
def logs(ctx, services):
    """Tail logs"""
    if not services:
        services = list(ctx.obj['config'].services.keys())
    
    aggregator = LogAggregator(".d2p/logs")
    aggregator.tail_logs(services)

@cli.command()
@click.option('--type', '-t', type=click.Choice(['python', 'systemd']), default='python')
@click.option('--out', '-o', default='dist', help='Output directory')
@click.pass_context
def convert(ctx, type, out):
    """Convert to native format"""
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

def main():
    """
    Main entry point for the CLI.
    """
    cli(obj={})

if __name__ == '__main__':
    main()
