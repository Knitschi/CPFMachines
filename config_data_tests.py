#!/usr/bin/env python3
"""
This module contains automated tests for the config_data module.
"""

import unittest
import os
import pprint

from .config_data import *
from . import cppcodebasemachines_version


class TestConfigData(unittest.TestCase):
    """
    Fixture class for testing the FakeFileSystemAccess class.
    """
    def test_reading_the_config_file_works(self):
        """
        Happy case test for reading a config file.
        """
        # execute
        sut = ConfigData(get_example_config_dict())

        # verify
        self.assertEqual( sut.file_version, cppcodebasemachines_version.CPPCODEBASEMACHINES_VERSION)

        # host machine data
        self.assertEqual( sut.host_machine_connections[0].machine_id, 'MyMaster' )
        self.assertEqual( sut.host_machine_connections[0].host_name, 'lhost3' )
        self.assertEqual( sut.host_machine_connections[0].user_name, 'fritz' )
        self.assertEqual( sut.host_machine_connections[0].user_password, '1234password' )
        self.assertEqual( sut.host_machine_connections[0].os_type, 'Linux' )

        self.assertEqual( sut.host_machine_connections[1].machine_id, 'MyLinuxSlave' )
        self.assertEqual( sut.host_machine_connections[1].host_name, '192.168.0.5' )
        self.assertEqual( sut.host_machine_connections[1].user_name, 'fritz' )
        self.assertEqual( sut.host_machine_connections[1].user_password, '1234password' )
        self.assertEqual( sut.host_machine_connections[1].os_type, 'Linux' )

        self.assertEqual( sut.host_machine_connections[2].machine_id, 'MyWindowsSlave' )
        self.assertEqual( sut.host_machine_connections[2].host_name, 'whost12' )
        self.assertEqual( sut.host_machine_connections[2].user_name, 'fritz' )
        self.assertEqual( sut.host_machine_connections[2].user_password, '1234password' )
        self.assertEqual( sut.host_machine_connections[2].os_type, 'Windows' )

        # jenkins master host data
        self.assertEqual( sut.jenkins_master_host_config.machine_id, 'MyMaster')
        self.assertEqual( sut.jenkins_master_host_config.jenkins_home_share, '/home/fritz/jenkins_home')
        self.assertEqual( sut.jenkins_master_host_config.host_temp_dir, '/home/fritz/temp')
        self.assertEqual( sut.jenkins_master_host_config.container_name, 'jenkins-master')
        self.assertEqual( sut.jenkins_master_host_config.container_ip, '172.19.0.3')

        # web server host data
        self.assertEqual( sut.web_server_host_config.machine_id, 'MyMaster')
        self.assertEqual( sut.web_server_host_config.host_html_share_dir, '/home/fritz/ccb_html_share')
        self.assertEqual( sut.web_server_host_config.container_name, 'ccb-web-server')
        self.assertEqual( sut.web_server_host_config.container_ip, '172.19.0.2')

        # repository host data
        self.assertEqual( sut.repository_host_config.machine_id , 'MyMaster')
        self.assertEqual( sut.repository_host_config.ssh_dir , '/home/fritz/.ssh')

        # jenkins slave config
        self.assertEqual( sut.jenkins_slave_configs[0].machine_id , 'MyLinuxSlave')
        self.assertEqual( sut.jenkins_slave_configs[0].executors , 1)
        self.assertEqual( sut.jenkins_slave_configs[0].container_name , '')
        self.assertEqual( sut.jenkins_slave_configs[0].container_ip , '')

        self.assertEqual( sut.jenkins_slave_configs[1].machine_id , 'MyWindowsSlave')
        self.assertEqual( sut.jenkins_slave_configs[1].executors , 1)
        self.assertEqual( sut.jenkins_slave_configs[1].container_name , '')
        self.assertEqual( sut.jenkins_slave_configs[1].container_ip , '')

        # jenkins master config
        self.assertEqual( sut.jenkins_config.use_unconfigured_jenkins , False)
        self.assertEqual( sut.jenkins_config.admin_user , 'fritz')
        self.assertEqual( sut.jenkins_config.admin_user_password , '1234password')
        self.assertEqual( sut.jenkins_config.account_config_files[0].user_name , 'hans')
        self.assertEqual( sut.jenkins_config.account_config_files[0].xml_config_file , 'UserHans.xml')
        self.assertEqual( sut.jenkins_config.job_config_files[0].job_name , 'MyCustomJob')
        self.assertEqual( sut.jenkins_config.job_config_files[0].xml_config_file , 'MyCustomJob.xml')
        self.assertEqual( sut.jenkins_config.cpp_codebase_jobs[0].job_name , 'BuildMyCppCodeBase')
        self.assertEqual( sut.jenkins_config.cpp_codebase_jobs[0].repository , 'ssh://fritz@mastermachine:/home/fritz/repositories/BuildMyCppCodeBase.git')
        self.assertFalse( sut.jenkins_config.approved_system_commands )
        self.assertEqual( sut.jenkins_config.approved_script_signatures[0] , '<script signature from my MyCustomJob jenkinsfile>')


    def test_validation_checks_version(self):
        """
        For now, the version in the file must exactly fit the version of the reading library.
        """
        # setup
        config_dict = get_example_config_dict()
        config_dict[KEY_VERSION] = '0.0.A'

        # execute
        self.assertRaises(Exception, ConfigData, config_dict)


    def test_validation_checks_one_linux_machine_available(self):
        """
        The jenkins master and web-server require a linux machine, so at least one must be available.
        """
        # setup
        config_dict = get_example_config_dict()
        del config_dict[KEY_LOGIN_DATA][0:2]

        # execute
        self.assertRaises(Exception, ConfigData, config_dict)


    def test_validation_checks_container_use_linux_machines(self):
        """
        The jenkins-master and web-server must be assigned to a Linux host machine.
        """
        # setup
        config_dict = get_example_config_dict()
        config_dict[KEY_JENKINS_MASTER_HOST][KEY_MACHINE_ID] = 'MyWindowsSlave'

        # execute
        self.assertRaises(Exception, ConfigData, config_dict)

        # setup
        config_dict = get_example_config_dict()
        config_dict[KEY_WEB_SERVER_HOST][KEY_MACHINE_ID] = 'MyWindowsSlave'

        # execute
        self.assertRaises(Exception, ConfigData, config_dict)


    def test_validation_checks_that_all_hosts_are_in_use(self):
        """
        If a host is not referenced, it is probably an error in the config file.
        """
        # setup
        config_dict = get_example_config_dict()
        # add a host that is not used
        not_used_host_dict = {
                KEY_MACHINE_ID : 'MyMaster2',
                KEY_MACHINE_NAME : 'lhost4',
                KEY_USER : 'fritz',
                KEY_PASSWORD : '1234password',
                KEY_OSTYPE : 'Linux'
            }
        config_dict[KEY_LOGIN_DATA].append(not_used_host_dict)

        # execute
        self.assertRaises(Exception, ConfigData, config_dict)


    def test_validation_checks_that_host_ids_are_unique(self):
        """
        The code requires that host ids to be unique.
        """
        # setup
        config_dict = get_example_config_dict()
        # add a host that with an existing id
        not_used_host_dict = {
                KEY_MACHINE_ID : 'MyMaster',
                KEY_MACHINE_NAME : 'lhost4',
                KEY_USER : 'fritz',
                KEY_PASSWORD : '1234password',
                KEY_OSTYPE : 'Linux'
            }
        config_dict[KEY_LOGIN_DATA].append(not_used_host_dict)

        # execute
        self.assertRaises(Exception, ConfigData, config_dict)


    def test_validation_checks_that_host_accounts_are_unique(self):
        """
        It is probably an error in the config file if an account gets used more than once.
        """
        # setup
        config_dict = get_example_config_dict()
        # let the linux slave use the same account as the linux master
        config_dict[KEY_LOGIN_DATA][1][KEY_MACHINE_NAME] = config_dict[KEY_LOGIN_DATA][0][KEY_MACHINE_NAME]

        # execute
        self.assertRaises(Exception, ConfigData, config_dict)


    def test_validation_checks_that_slave_executors_number(self):
        """
        Zero or less executors in a jenkins slave makes no sense.
        """
        # setup
        config_dict = get_example_config_dict()
        config_dict[KEY_JENKINS_SLAVES][0][KEY_EXECUTORS] = 0

        # execute
        self.assertRaises(Exception, ConfigData, config_dict)

