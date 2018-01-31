#!/usr/bin/env python3
"""
This module contains automated tests for the config_data module.
"""

import unittest

from . import config_data


class TestConfigData(unittest.TestCase):
    """
    Fixture class for testing the FakeFileSystemAccess class.
    """
    def setUp(self):
        self.sut = 'bla'


    def test_1(self):
        self.assertEqual(self.sut, 'blub')

        
