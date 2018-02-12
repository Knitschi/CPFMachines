#!/usr/bin/env python3
"""
This module contains automated tests for the config_data module.
"""

import unittest
import os
import pprint

from .config_data import *
from . import cpfmachines_version


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
        self.assertEqual( sut.file_version, cpfmachines_version.CPFMACHINES_VERSION)

        # host machine data
        self.assertEqual( sut.host_machine_connections[0].machine_id, 'MyMaster' )
        self.assertEqual( sut.host_machine_connections[0].host_name, 'lhost3' )
        self.assertEqual( sut.host_machine_connections[0].user_name, 'fritz' )
        self.assertEqual( sut.host_machine_connections[0].user_password, '1234password' )
        self.assertEqual( sut.host_machine_connections[0].os_type, 'Linux' )
        self.assertEqual( sut.host_machine_connections[0].temp_dir, PurePosixPath('/home/fritz/temp') )

        self.assertEqual( sut.host_machine_connections[1].machine_id, 'MyLinuxSlave' )
        self.assertEqual( sut.host_machine_connections[1].host_name, '192.168.0.5' )
        self.assertEqual( sut.host_machine_connections[1].user_name, 'fritz' )
        self.assertEqual( sut.host_machine_connections[1].user_password, '1234password' )
        self.assertEqual( sut.host_machine_connections[1].os_type, 'Linux' )
        self.assertEqual( sut.host_machine_connections[1].temp_dir, PurePosixPath('/home/fritz/temp') )

        self.assertEqual( sut.host_machine_connections[2].machine_id, 'MyWindowsSlave' )
        self.assertEqual( sut.host_machine_connections[2].host_name, 'whost12' )
        self.assertEqual( sut.host_machine_connections[2].user_name, 'fritz' )
        self.assertEqual( sut.host_machine_connections[2].user_password, '' )
        self.assertEqual( sut.host_machine_connections[2].os_type, 'Windows' )
        self.assertEqual( sut.host_machine_connections[2].temp_dir, None )

        # jenkins master host data
        self.assertEqual( sut.jenkins_master_host_config.machine_id, 'MyMaster')
        self.assertEqual( sut.jenkins_master_host_config.jenkins_home_share, PurePosixPath('/home/fritz/jenkins_home'))
        self.assertEqual( sut.jenkins_master_host_config.container_conf.container_name, 'jenkins-master')
        self.assertEqual( sut.jenkins_master_host_config.container_conf.container_user, 'jenkins')
        self.assertEqual( sut.jenkins_master_host_config.container_conf.container_ip, '172.19.0.3')
        self.assertEqual( sut.jenkins_master_host_config.container_conf.container_image_name, 'jenkins-master-image')
        self.assertEqual( sut.jenkins_master_host_config.container_conf.mapped_ssh_host_port, None)
        
        # web server host data
        self.assertEqual( sut.web_server_host_config.machine_id, 'MyMaster')
        self.assertEqual( sut.web_server_host_config.host_html_share_dir, PurePosixPath('/home/fritz/cpf_html_share'))
        self.assertEqual( sut.web_server_host_config.container_conf.container_name, 'cpf-web-server')
        self.assertEqual( sut.web_server_host_config.container_conf.container_user, 'root')
        self.assertEqual( sut.web_server_host_config.container_conf.container_ip, '172.19.0.2')
        self.assertEqual( sut.web_server_host_config.container_conf.container_image_name, 'cpf-web-server-image')
        self.assertEqual( sut.web_server_host_config.container_conf.mapped_ssh_host_port, 23)

        # repository host data
        self.assertEqual( sut.repository_host_config.machine_id , 'MyMaster')
        self.assertEqual( sut.repository_host_config.ssh_dir , PurePosixPath('/home/fritz/.ssh'))

        # jenkins slave config
        self.assertEqual( sut.jenkins_slave_configs[0].machine_id , 'MyLinuxSlave')
        self.assertEqual( sut.jenkins_slave_configs[0].slave_name , 'CPF-' + cpfmachines_version.CPFMACHINES_VERSION + '-linux-slave-0' )
        self.assertEqual( sut.jenkins_slave_configs[0].executors , 2)
        self.assertEqual( sut.jenkins_slave_configs[0].container_conf.container_name , 'jenkins-slave-linux-0')
        self.assertEqual( sut.jenkins_slave_configs[0].container_conf.container_user , 'jenkins')
        self.assertEqual( sut.jenkins_slave_configs[0].container_conf.container_ip , '172.19.0.4')
        self.assertEqual( sut.jenkins_slave_configs[0].container_conf.container_image_name , 'jenkins-slave-linux-image')
        self.assertEqual( sut.jenkins_slave_configs[0].container_conf.mapped_ssh_host_port , 24)

        self.assertEqual( sut.jenkins_slave_configs[1].machine_id , 'MyMaster')
        self.assertEqual( sut.jenkins_slave_configs[1].slave_name , 'CPF-' + cpfmachines_version.CPFMACHINES_VERSION + '-linux-slave-1' )
        self.assertEqual( sut.jenkins_slave_configs[1].executors , 1)
        self.assertEqual( sut.jenkins_slave_configs[1].container_conf.container_name , 'jenkins-slave-linux-1')
        self.assertEqual( sut.jenkins_slave_configs[1].container_conf.container_user , 'jenkins')
        self.assertEqual( sut.jenkins_slave_configs[1].container_conf.container_ip , '172.19.0.5')
        self.assertEqual( sut.jenkins_slave_configs[1].container_conf.container_image_name , 'jenkins-slave-linux-image')
        self.assertEqual( sut.jenkins_slave_configs[1].container_conf.mapped_ssh_host_port , 25)

        self.assertEqual( sut.jenkins_slave_configs[2].machine_id , 'MyWindowsSlave')
        self.assertEqual( sut.jenkins_slave_configs[2].slave_name , 'CPF-' + cpfmachines_version.CPFMACHINES_VERSION + '-windows-slave-0' )
        self.assertEqual( sut.jenkins_slave_configs[2].executors , 1)
        self.assertEqual( sut.jenkins_slave_configs[2].container_conf, None)

        # jenkins master config
        self.assertEqual( sut.jenkins_config.use_unconfigured_jenkins , False)
        self.assertEqual( sut.jenkins_config.admin_user , 'fritz')
        self.assertEqual( sut.jenkins_config.admin_user_password , '1234password')
        self.assertEqual( sut.jenkins_config.account_config_files[0].name , 'hans')
        self.assertEqual( str(sut.jenkins_config.account_config_files[0].xml_file) , 'UserHans.xml')
        self.assertEqual( sut.jenkins_config.job_config_files[0].name , 'MyCustomJob')
        self.assertEqual( str(sut.jenkins_config.job_config_files[0].xml_file) , 'MyCustomJob.xml')
        self.assertEqual( sut.jenkins_config.cpf_jobs[0].job_name , 'BuildMyCPFProject')
        self.assertEqual( sut.jenkins_config.cpf_jobs[0].repository , 'ssh://fritz@mastermachine:/home/fritz/repositories/BuildMyCPFProject.git')
        self.assertFalse( sut.jenkins_config.approved_system_commands )
        self.assertEqual( sut.jenkins_config.approved_script_signatures[0] , '<script signature from my MyCustomJob jenkinsfile>')


    def test_get_host_machine_connection(self):
        # setup
        sut = ConfigData(get_example_config_dict())

        # execute and verify
        machine_ids = ['MyMaster','MyLinuxSlave','MyWindowsSlave']
        for machine_id in machine_ids:
            connection = sut.get_host_machine_connection(machine_id)
            self.assertEqual(machine_id, connection.machine_id)


    def test_get_container_machine_dictionary(self):
        """
        Verify the output is correct.
        """
        # setup
        sut = ConfigData(get_example_config_dict())

        # execute
        machine_dict = sut.get_container_machine_dictionary()

        # verify
        expected_machine_dict = {
            'cpf-web-server' : 'MyMaster',
            'jenkins-master' : 'MyMaster',
            'jenkins-slave-linux-0' : 'MyLinuxSlave',
            'jenkins-slave-linux-1' : 'MyMaster',
        }
        self.assertEqual(machine_dict, expected_machine_dict)


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


    def test_validation_checks_that_container_hosts_have_temp_dir(self):
        """
        We need a temporary directory for the build-context when building
        docker container.
        """
        config_dict = get_example_config_dict()
        config_dict[KEY_LOGIN_DATA][1][KEY_TEMPDIR] = ''

        # execute
        self.assertRaises(Exception, ConfigData, config_dict)
