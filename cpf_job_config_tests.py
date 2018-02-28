#!/usr/bin/env python3
"""
This module contains automated tests for the hook_config module.
"""

import unittest
import pprint
from pathlib import PurePosixPath

from ..CPFMachines import config_data

from .cpf_job_config import *
from . import setup

class TestCPFJobConfig(unittest.TestCase):
    """
    Fixture class for testing the CPFJobConfig class.
    """
    def test_reading_the_cpf_job_config_works(self):
        
        sut = CPFJobConfigs(get_example_config_dict())

        # JOB 1
        self.assertEqual( sut.job_configs[0].job_name, 'MyCPFProject1')
        self.assertEqual( sut.job_configs[0].repository, 'ssh://fritz@mastermachine:/home/fritz/repositories/MyCPFProject1.git')

        self.assertEqual( sut.job_configs[0].webserver_config.machine_id, 'MyMaster')
        self.assertEqual( sut.job_configs[0].webserver_config.host_html_share_dir, PurePosixPath('/home/fritz/mycpfproject1_html_share'))
        self.assertEqual( sut.job_configs[0].webserver_config.container_ssh_port, 25)
        self.assertEqual( sut.job_configs[0].webserver_config.container_web_port, 80)

        self.assertEqual( sut.job_configs[0].webserver_config.container_conf.container_name, 'cpf-web-server-0')
        self.assertEqual( sut.job_configs[0].webserver_config.container_conf.container_user, 'root')
        self.assertEqual( sut.job_configs[0].webserver_config.container_conf.container_image_name, 'cpf-web-server-image')
        self.assertEqual( sut.job_configs[0].webserver_config.container_conf.published_ports, {80:80, 25:22})
        self.assertEqual( sut.job_configs[0].webserver_config.container_conf.host_volumes, {PurePosixPath('/home/fritz/mycpfproject1_html_share') : PurePosixPath('/var/www/html')})
        self.assertEqual( sut.job_configs[0].webserver_config.container_conf.envvar_definitions, [])


        # JOB 2
        self.assertEqual( sut.job_configs[1].job_name, 'MyCPFProject2')
        self.assertEqual( sut.job_configs[1].repository, 'ssh://fritz@mastermachine:/home/fritz/repositories/MyCPFProject2.git')

        self.assertEqual( sut.job_configs[1].webserver_config.machine_id, 'MyMaster')
        self.assertEqual( sut.job_configs[1].webserver_config.host_html_share_dir, PurePosixPath('/home/fritz/mycpfproject2_html_share'))
        self.assertEqual( sut.job_configs[1].webserver_config.container_ssh_port, 26)
        self.assertEqual( sut.job_configs[1].webserver_config.container_web_port, 81)

        self.assertEqual( sut.job_configs[1].webserver_config.container_conf.container_name, 'cpf-web-server-1')
        self.assertEqual( sut.job_configs[1].webserver_config.container_conf.container_user, 'root')
        self.assertEqual( sut.job_configs[1].webserver_config.container_conf.container_image_name, 'cpf-web-server-image')
        self.assertEqual( sut.job_configs[1].webserver_config.container_conf.published_ports, {81:80, 26:22})
        self.assertEqual( sut.job_configs[1].webserver_config.container_conf.host_volumes, {PurePosixPath('/home/fritz/mycpfproject2_html_share') : PurePosixPath('/var/www/html')})
        self.assertEqual( sut.job_configs[1].webserver_config.container_conf.envvar_definitions, [])


    def test_validation_checks_web_server_container_use_linux_machines(self):

        # setup
        config_dict = get_example_config_dict()
        config_dict[config_data.KEY_JENKINS_CONFIG][KEY_CPF_JOBS][0][KEY_WEBSERVER_CONFIG][config_data.KEY_MACHINE_ID] = 'MyWindowsSlave'

        # execute
        self.assertRaises(Exception, CPFJobConfigs, config_dict)


    def test_validation_checks_that_all_hosts_are_in_use(self):
        """
        If a host is not referenced, it is probably an error in the config file.
        """
        # setup
        config_dict = get_example_config_dict()
        # add a host that is not used
        not_used_host_dict = {
                config_data.KEY_MACHINE_ID : 'MyMaster2',
                config_data.KEY_MACHINE_NAME : 'lhost4',
                config_data.KEY_USER : 'fritz',
                config_data.KEY_PASSWORD : '1234password',
                config_data.KEY_OSTYPE : 'Linux'
            }
        config_dict[config_data.KEY_LOGIN_DATA].append(not_used_host_dict)

        # execute
        self.assertRaises(Exception, CPFJobConfigs, config_dict)

