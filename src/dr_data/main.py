import os
import argparse
import logging
import sys
import json
from os.path import exists
from dr_data.utilities.file import FileUtility
from dr_data.utilities.cache import Cache
from dr_data.utilities.db import DatabaseUtility
from dr_data.config import *
from dr_data.biopsy import Biopsy
from dr_data.inject import Inject
from dr_data.transplant import Transplant

from dr_data import __version__

__author__ = AUTHOR
__copyright__ = COPYRIGHT
__license__ = LICENSE

_logger = logging.getLogger(__name__)


class Main:
    def __init__(self, args):
        self.parser = argparse.ArgumentParser(
            description=MAIN_DESCRIPTION,
            epilog="Version: {version}".format(version=__version__))
        self.arguments = self.parse_args(args)

        if self.arguments.config:
            self.cache = Cache(config_path=self.arguments.config, cache_location='generated-schemas')
            self.configuration = self.load_configuration(self.arguments.config)
        else:
            self.cache = Cache(config_path=os.getenv(ENV_CONFIG_NAME), cache_location='generated-schemas')
            self.configuration = self.load_configuration(os.getenv(ENV_CONFIG_NAME))

        self.database_name = self.configuration['db']['database']
        self.db_util = DatabaseUtility(self.configuration['db'])
        self.schema_data = None

    def load_configuration(self, config_path):
        configuration_file = os.getenv(ENV_CONFIG_NAME)
        if not config_path and not configuration_file:
            raise argparse.ArgumentTypeError(NO_CONFIG_ARGUMENT.format(env_name=ENV_CONFIG_NAME))
        if config_path:
            json_config = json.loads(FileUtility.read_file(config_path))
            self.cache.append('config_path', config_path)
            return json_config

    def parse_args(self, args):
        # transplant arguments
        self.parser.add_argument('-t', '--transplant', help="Insert one or all CSV files to table", action='store_true')
        self.parser.add_argument('-source', help="Used in conjuctions with `transplant` The CSV source file or directory. if directory, csv filenames need to match table names ", type=str)
        self.parser.add_argument('-destination', help="Used in conjuctions with `transplant` and `source`. if `source` is a file. destination TABLE is required", type=str)

        # inject arguments
        self.parser.add_argument('-i', '--inject', help="Inserts one or many randomly regenerated rows", action='store_true')
        self.parser.add_argument('-rows', help="How may rows do you want to load per table in the database, default is set in configuration", type=int)

        # biopsy arguments
        self.parser.add_argument('-b', '--biopsy', help="Explicitly exports a schema and table insertion-order JSON files", action='store_true')
        self.parser.add_argument('-export', help="The directory PATH to export the JSON files", type=str)

        # cleanse (truncate) arguments
        self.parser.add_argument('-c', '--cleanse', help="Truncates all the values in the database", action='store_true')
        self.parser.add_argument('-config', help="configuration file or set {env_name}=<path> env variable".format(env_name=ENV_CONFIG_NAME), type=str)
        return self.parser.parse_args(args)

    def setup_logging(self):
        log_format = "[%(asctime)s] %(levelname)s:%(name)s: %(message)s"
        logging.basicConfig(
            level=logging.INFO, stream=sys.stdout, format=log_format, datefmt="%Y-%m-%d %H:%M:%S"
        )

    def execute_biopsy(self):
        if not self.arguments.export:
            sys.tracebacklimit=0
            raise argparse.ArgumentTypeError(BIOPSY_NO_EXPORT)
        if not os.path.isdir(self.arguments.export):
            sys.tracebacklimit=0
            raise argparse.ArgumentTypeError(BIOPSY_EXPORT_NOT_EXIST.format(path=self.arguments.export))

        print(BIOPSY_START_MESSAGE.format(database=self.database_name))
        self.schema_data = Biopsy(self.configuration, self.cache).execute_cmd()
        schema_filename = "{db_name}_schema".format(db_name=self.database_name)
        insertion_order_filename = "{db_name}_biopsy_insertion_order".format(db_name=self.database_name)

        FileUtility.generate_json_file(schema_filename, self.arguments.export, self.schema_data[0])
        print(BIOPSY_GENERATED_SCHEMA.format(filename=schema_filename))

        FileUtility.generate_json_file(insertion_order_filename, self.arguments.export, self.schema_data[1])
        print(BIOPSY_GENERATED_INSERT_ORDER_SCHEMA.format(filename=insertion_order_filename))
        print(BIOPSY_COMPLETE_MESSAGE.format(database=self.database_name, export_path=self.arguments.export))

    def execute_cleanse(self):
        self.db_util .truncate_db()
        print(CLEANSE_COMPLETE_MESSAGE.format(database=self.database_name))

    def execute_inject(self):
        if not self.arguments.rows:
            sys.tracebacklimit=0
            raise argparse.ArgumentTypeError(INJECT_NO_ROWS)
        self.schema_data = Biopsy(self.configuration, self.cache).execute_cmd()
        Inject(self.schema_data[1], self.configuration['db']).execute_cmd(self.arguments.rows)
        print(INJECT_COMPLETE_MESSAGE.format(database=self.database_name, rows=self.arguments.rows))

    def execute_transplant(self):
        print(TRANSPLANT_START_MESSAGE.format(database=self.database_name))
        self.schema_data = Biopsy(self.configuration, self.cache).execute_cmd()
        transplant = Transplant(self.configuration['db'])
        if not self.arguments.source:
            sys.tracebacklimit=0
            raise argparse.ArgumentTypeError(TRANSPLANT_NO_SOURCE)

        if os.path.isfile(self.arguments.source):
            if not self.arguments.destination:
                sys.tracebacklimit=0
                raise argparse.ArgumentTypeError(TRANSPLANT_NO_DESTINATION)
            if not FileUtility.is_csv_file(self.arguments.source):
                raise argparse.ArgumentTypeError(TRANSPLANT_NOT_CSV)
            transplant.execute_file_cmd(self.arguments.source, self.arguments.destination)
            print(TRANSPLANT_COMPLETE_MESSAGE.format(database=self.database_name))
            sys.exit()

        if os.path.isdir(self.arguments.source):
            transplant.execute_directory_cmd(self.arguments.source, self.schema_data)
            print(TRANSPLANT_COMPLETE_MESSAGE.format(database=self.database_name))
            sys.exit()

    def execute_cmd(self):
        self.setup_logging()
        if self.arguments.transplant:
            self.execute_transplant()
        elif self.arguments.inject:
            self.execute_inject()
        elif self.arguments.biopsy:
            self.execute_biopsy()
        elif self.arguments.cleanse:
            self.execute_cleanse()
        else:
            print(NO_ARGUMENTS + "\n")
            self.parser.print_help()


def run():
    Main(sys.argv[1:]).execute_cmd()


if __name__ == '__main__':
    run()