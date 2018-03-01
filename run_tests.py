#!/usr/bin/python3
"""
Runs all python tests from the CPFMachines package.
"""

import unittest
import sys

from .config_data_tests import *
from .hook_config_tests import *
from .cpf_job_config_tests import *

if __name__ == '__main__':
    unittest.main()
