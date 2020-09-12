#!/usr/bin/python3
"""
Runs all python tests from the CPFMachines package.
"""

from pathlib import PurePath
import os
import sys
import unittest

# Add the script path to the python path
_SCRIPT_DIR = PurePath(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(str(_SCRIPT_DIR))


from config_data_tests import *
from hook_config_tests import *

if __name__ == '__main__':
    unittest.main()
