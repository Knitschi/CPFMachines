#!/usr/bin/env python3
"""
This module contains automated tests for the hook_config module.
"""

import unittest
import pprint

from hook_config import *

class TestHookConfig(unittest.TestCase):
    """
    Fixture class for testing the FakeFileSystemAccess class.
    """
    def test_reading_the_config_file_works(self):
        """
        Happy case test for reading a config file.
        """
        sut = HookConfigData(get_example_config_dict())

        # jenkins account
        self.assertEqual( sut.jenkins_account_info.url, 'http://MyMaster:8080' )
        self.assertEqual( sut.jenkins_account_info.user, 'fritz' )
        self.assertEqual( sut.jenkins_account_info.password, '1234password' )

        # repository host data
        self.assertEqual( sut.repository_host_infos[0].machine_id, 'MyMaster' )
        self.assertEqual( sut.repository_host_infos[0].host_name, 'lhost3' )
        self.assertEqual( sut.repository_host_infos[0].user_name, 'fritz' )
        self.assertEqual( sut.repository_host_infos[0].user_password, '1234password' )
        self.assertEqual( sut.repository_host_infos[0].os_type, 'Linux' )
        self.assertEqual( sut.repository_host_infos[0].temp_dir, PurePosixPath('/home/fritz/temp') )

        # job hook configs
        self.assertEqual( sut.hook_configs[0].jenkins_job_basename, 'BuildMyCPFProject' )
        self.assertEqual( sut.hook_configs[0].machine_id, 'MyMaster' )
        self.assertEqual( sut.hook_configs[0].hook_dir, PurePosixPath('/home/fritz/repositories/BuildMyCPFProject.git/hooks') )

        # job hook configs
        self.assertEqual( sut.hook_configs[1].jenkins_job_basename, 'BuildMyCPFProject' )
        self.assertEqual( sut.hook_configs[1].machine_id, 'MyMaster' )
        self.assertEqual( sut.hook_configs[1].hook_dir, PurePosixPath('/home/fritz/repositories/MyPackage.git/hooks') )

