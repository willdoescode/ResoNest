import click
from .build_manager import LoggerConfig, CommandRunnerConfig, SimulatorConfig, ProgressConfig, BuildManager

def common_options(func):
    return click.option(
        '-v', '--verbose',
        is_flag=True,
        help='Enable verbose output.'
    )(func)

@click.group(context_settings={'help_option_names': ['-h', '--help']})
def cli():
    pass

@cli.command()
@common_options
def install(verbose: bool):
    logger_config = LoggerConfig(level='DEBUG' if verbose else 'INFO', show_time=False)
    runner_config = CommandRunnerConfig(shell=False, check=True)
    simulator_config = SimulatorConfig()
    progress_config = ProgressConfig(refresh_per_second=10)

    manager = BuildManager(
        config=simulator_config,
        logger_config=logger_config,
        runner_config=runner_config,
        progress_config=progress_config,
        verbose=verbose
    )

    manager.install_app()

@cli.command()
@common_options
def uninstall(verbose: bool):
    logger_config = LoggerConfig(level='DEBUG' if verbose else 'INFO', show_time=False)
    runner_config = CommandRunnerConfig(shell=False, check=True)
    simulator_config = SimulatorConfig()
    progress_config = ProgressConfig(refresh_per_second=10)

    manager = BuildManager(
        config=simulator_config,
        logger_config=logger_config,
        runner_config=runner_config,
        progress_config=progress_config,
        verbose=verbose
    )

    manager.uninstall_app()

@cli.command()
@common_options
def refresh(verbose: bool):
    logger_config = LoggerConfig(level='DEBUG' if verbose else 'INFO', show_time=False)
    runner_config = CommandRunnerConfig(shell=False, check=True)
    simulator_config = SimulatorConfig()
    progress_config = ProgressConfig(refresh_per_second=10)

    manager = BuildManager(
        config=simulator_config,
        logger_config=logger_config,
        runner_config=runner_config,
        progress_config=progress_config,
        verbose=verbose
    )

    manager.refresh_app()

if __name__ == '__main__':
    cli()
