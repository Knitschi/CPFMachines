"""
This script is used to generate an example configuration .json file that can be used with the setup.py script.
"""

import sys
from config_data import *


if __name__ == '__main__':
    write_example_config_file(sys.argv[1])