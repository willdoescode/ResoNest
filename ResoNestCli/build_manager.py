import sys
import subprocess
from pathlib import Path
from pydantic import BaseModel, Field, model_validator
from loguru import logger
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, SpinnerColumn
from rich.console import Console
from rich.logging import RichHandler


class LoggerConfig(BaseModel):
    level: str = Field(default='INFO', description='Logging level')
    show_time: bool = Field(default=False, description='Whether to show timestamps in logs')

class CommandRunnerConfig(BaseModel):
    shell: bool = Field(default=False, description='Whether to use the shell as the program to execute')
    check: bool = Field(default=True, description='Whether to raise an exception if the command exits with a non-zero status')

class SimulatorConfig(BaseModel):
    device_name: str = Field(default='iPhone 16 Plus', description='Name of the iOS simulator device')
    os_version: str = Field(default='18.0', description='OS version of the simulator')
    scheme: str = Field(default='ResoNest', description='Xcode project scheme')
    configuration: str = Field(default='Debug', description='Build configuration')
    destination: str = Field(
        default='platform=iOS Simulator,name=iPhone 16 Plus,OS=18.0',
        description='Destination for xcodebuild'
    )
    derived_data_path: Path = Field(default=Path('build'), description='Derived data path')
    app_path: Path | None = Field(default=None, description='Path to the built app')

    @model_validator(mode='after')
    def set_app_path(cls, values):
        if values.app_path is None:
            derived_data_path = values.derived_data_path
            configuration = values.configuration
            scheme = values.scheme
            values.app_path = derived_data_path / 'Build' / 'Products' / f'{configuration}-iphonesimulator' / f'{scheme}.app'
        return values

class ProgressConfig(BaseModel):
    refresh_per_second: int = Field(default=10, description='How often to refresh the progress bar')

class LoggerManager:
    def __init__(self, config: LoggerConfig):
        self.console = Console()
        logger.remove()  
        rich_handler = RichHandler(console=self.console, markup=True, show_time=config.show_time)
        logger.add(rich_handler, level=config.level.upper())
    
    def get_logger(self):
        return logger
    
class CommandRunner:
    def __init__(self, config: CommandRunnerConfig, logger: LoggerManager):
        self.shell = config.shell
        self.check = config.check
        self.logger = logger

    def run(self, command: list[str], description: str = '') -> str:
        self.logger.debug(f'Executing command: {' '.join(command)}')
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=self.shell,
                check=self.check,
            )
            for line in result.stdout.splitlines():
                self.logger.debug(line)
            return result.stdout
        except subprocess.CalledProcessError as e:
            self.logger.error(f'Command failed: {' '.join(command)}')
            if self.check:
                for line in e.stdout.splitlines():
                    self.logger.error(line)
                sys.exit(1)
            return e.stdout

    def run_safe(self, command: list[str], description: str = '') -> tuple[bool, str]:
        self.logger.debug(f'Executing command safely: {' '.join(command)}')
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=self.shell,
                check=False,  
            )
            success = result.returncode == 0
            if success:
                for line in result.stdout.splitlines():
                    self.logger.debug(line)
            else:
                self.logger.warning(f'Command failed (but continuing): {' '.join(command)}')
                for line in result.stdout.splitlines():
                    self.logger.debug(line)
            return (success, result.stdout)
        except Exception as e:
            self.logger.error(f'Exception while running command: {e}')
            return (False, str(e))




class SimulatorManager:
    def __init__(self, config: SimulatorConfig, command_runner: CommandRunner, logger: LoggerManager):
        self.config = config
        self.command_runner = command_runner
        self.logger = logger

    def get_bundle_identifier(self) -> str:
        plist_path = self.config.app_path / 'Info.plist'
        if not plist_path.exists():
            self.logger.error(f'Info.plist not found at {plist_path}')
            sys.exit(1)
        self.command_runner.run(['plutil', '-convert', 'xml1', str(plist_path)], description='Converting plist')
        command = ['/usr/libexec/PlistBuddy', '-c', 'Print :CFBundleIdentifier', str(plist_path)]
        result = self.command_runner.run(command, description='Retrieving CFBundleIdentifier')
        bundle_identifier = result.strip()
        self.logger.debug(f'Retrieved CFBundleIdentifier: {bundle_identifier}')
        return bundle_identifier

    def boot_simulator(self):
        self.logger.debug('Checking simulator boot status...')
        self.command_runner.run(['xcrun', 'simctl', 'bootstatus', self.config.device_name], description='Checking boot status')
        self.logger.debug('Booting simulator...')
        self.command_runner.run(['xcrun', 'simctl', 'boot', self.config.device_name], description='Booting simulator')

    def install_app(self):
        self.logger.debug('Installing app on simulator...')
        self.command_runner.run(['xcrun', 'simctl', 'install', 'booted', str(self.config.app_path)], description='Installing app')

    def launch_app(self, bundle_identifier: str):
        self.logger.debug('Launching app on simulator...')
        self.command_runner.run(['xcrun', 'simctl', 'launch', 'booted', bundle_identifier], description='Launching app')

    def uninstall_app(self, bundle_identifier: str):
        self.logger.debug('Uninstalling app from simulator...')
        self.command_runner.run(['xcrun', 'simctl', 'uninstall', 'booted', bundle_identifier], description='Uninstalling app')

    def is_app_installed(self) -> bool:
        bundle_identifier = self.get_bundle_identifier()
        self.logger.debug(f'Checking if app with bundle identifier \'{bundle_identifier}\' is installed.')
        success, _ = self.command_runner.run_safe(
            ['xcrun', 'simctl', 'get_app_container', 'booted', bundle_identifier],
            description='Checking if app is installed'
        )
        if success:
            self.logger.info('App is already installed on the simulator.')
        else:
            self.logger.info('App is not installed on the simulator.')
        return success



class ProgressManager:
    def __init__(self, config: ProgressConfig, console: Console):
        self.config = config
        self.console = console

    def __enter__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn('[progress.description]{task.description}'),
            BarColumn(bar_width=None),
            TextColumn('{task.percentage:>3.0f}%'),
            TimeRemainingColumn(),
            console=self.console,
            transient=True,
            refresh_per_second=self.config.refresh_per_second,
        )
        self.progress.start()
        return self.progress

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.progress.stop()


class BuildManager:
    def __init__(self, config: SimulatorConfig, logger_config: LoggerConfig, runner_config: CommandRunnerConfig, progress_config: ProgressConfig, verbose: bool = False):
        self.logger_manager = LoggerManager(logger_config)
        self.logger = self.logger_manager.get_logger()

        self.command_runner = CommandRunner(runner_config, self.logger)

        self.simulator_manager = SimulatorManager(config, self.command_runner, self.logger)

        self.progress_manager = ProgressManager(progress_config, self.logger_manager.console)

    def install_app(self):
        self.logger.info('Starting installation...')

        if self.simulator_manager.is_app_installed():
            self.logger.info('App is already installed on the simulator. Skipping installation.')
            bundle_identifier = self.simulator_manager.get_bundle_identifier()
            self.simulator_manager.launch_app(bundle_identifier)
            self.logger.info('App launched on simulator.')
            return
        else:
            self.logger.info('App is not installed. Proceeding with installation.')

        steps = [
            (
                [
                    'xcodebuild', 'clean',
                    '-scheme', self.simulator_manager.config.scheme,
                    '-configuration', self.simulator_manager.config.configuration,
                    '-destination', self.simulator_manager.config.destination,
                    '-derivedDataPath', str(self.simulator_manager.config.derived_data_path)
                ],
                20,
                'Cleaning build'
            ),
            (
                [
                    'xcodebuild', 'build',
                    '-scheme', self.simulator_manager.config.scheme,
                    '-configuration', self.simulator_manager.config.configuration,
                    '-destination', self.simulator_manager.config.destination,
                    '-derivedDataPath', str(self.simulator_manager.config.derived_data_path),
                    '-sdk', 'iphonesimulator'
                ],
                50,
                'Building app'
            ),
            (
                [
                    'xcrun', 'simctl', 'install', 'booted', str(self.simulator_manager.config.app_path)
                ],
                20,
                'Installing app on simulator'
            ),
            (
                [
                    'xcrun', 'simctl', 'launch', 'booted', self.simulator_manager.get_bundle_identifier()
                ],
                10,
                'Launching app on simulator'
            )
        ]

        with self.progress_manager as progress:
            task = progress.add_task('Installation Progress', total=100)
            for command, increment, step_desc in steps:
                self.logger.info(step_desc)
                self.command_runner.run(command, description=step_desc)
                progress.update(task, advance=increment)
        self.logger.info('Installation and launch completed.')

    def uninstall_app(self):
        self.logger.info('Starting uninstallation...')
        bundle_identifier = None
        if self.simulator_manager.config.app_path.exists():
            bundle_identifier = self.simulator_manager.get_bundle_identifier()
        else:
            command = [
                'xcodebuild',
                '-scheme', self.simulator_manager.config.scheme,
                '-configuration', self.simulator_manager.config.configuration,
                '-showBuildSettings'
            ]
            result = self.command_runner.run(command, description='Retrieving build settings')
            for line in result.splitlines():
                if 'PRODUCT_BUNDLE_IDENTIFIER' in line:
                    bundle_identifier = line.split('=')[1].strip()
                    break
            if bundle_identifier is None:
                self.logger.error('Failed to retrieve CFBundleIdentifier.')
                sys.exit(1)
        self.logger.debug(f'Retrieved CFBundleIdentifier: {bundle_identifier}')

        steps = [
            (
                [
                    'xcrun', 'simctl', 'uninstall', 'booted', bundle_identifier
                ],
                100,
                'Uninstalling app from simulator'
            )
        ]

        with self.progress_manager as progress:
            task = progress.add_task('Uninstallation Progress', total=100)
            for command, increment, step_desc in steps:
                self.logger.info(step_desc)
                self.command_runner.run(command, description=step_desc)
                progress.update(task, advance=increment)
        self.logger.info('App uninstalled from the simulator.')

    def refresh_app(self):
        self.logger.info('Refreshing the app...')
        self.uninstall_app()
        self.install_app()
        self.logger.info('Refresh completed.')