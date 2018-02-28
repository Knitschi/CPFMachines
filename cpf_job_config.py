#!/usr/bin/env python3

import pprint
from pathlib import PurePosixPath

from ..CPFMachines import config_data


KEY_CPF_JOBS = 'CPFJobs'
KEY_JENKINSJOB_BASE_NAME = 'JenkinsJobBasename'
KEY_REPOSITORY = 'Repository'

KEY_WEBSERVER_CONFIG = 'WebServerConfig'
KEY_HOST_HTML_SHARE = 'HostHTMLShare'


_HTML_SHARE_WEB_SERVER_CONTAINER = PurePosixPath('/var/www/html')


class CPFJobConfigs:
    """
    A class that contains the configuration of the CPF jenkins jobs.
    """
    def __init__(self, config_dict):
        self.job_configs = []
        self.base_config = config_data.ConfigData(config_dict)

        self._get_cpf_job_configs(config_dict)
        self._validate_values()
        self._set_container_config()


    def _get_cpf_job_configs(self, config_dict):
        """
        Reads a list of cpf jenkins job configurations from the config file dictionary. 
        """
        jenkins_config_dict = config_data.get_checked_value(config_dict, config_data.KEY_JENKINS_CONFIG)
        job_config_dict_list = config_data.get_checked_value(jenkins_config_dict, KEY_CPF_JOBS)
        for job_config_dict in job_config_dict_list:
            config = CPFJobConfig()
            config.job_name = config_data.get_checked_value(job_config_dict, KEY_JENKINSJOB_BASE_NAME)
            config.repository = config_data.get_checked_value(job_config_dict, KEY_REPOSITORY)

            webserver_config_dict = config_data.get_checked_value(job_config_dict, KEY_WEBSERVER_CONFIG)
            config.webserver_config.machine_id = config_data.get_checked_value(webserver_config_dict, config_data.KEY_MACHINE_ID)
            config.webserver_config.host_html_share_dir = PurePosixPath(config_data.get_checked_value(webserver_config_dict, KEY_HOST_HTML_SHARE))

            self.job_configs.append(config)


    def _validate_values(self):
        """
        Checks if the config values make sense.
        """
        self._check_container_use_linux_hosts()
        self._check_all_hosts_are_in_use()


    def _check_container_use_linux_hosts(self):
        """
        Check that all webserver hosts are linux machines.
        """
        for job_config in self.job_configs:
            machine_id = job_config.webserver_config.machine_id
            if not self.base_config.is_linux_machine(machine_id):
                raise Exception("Config file Error! The webserver container host with {0} \"{1}\" is not a Linux machine.".format(config_data.KEY_MACHINE_ID, machine_id))


    def _check_all_hosts_are_in_use(self):
        """
        Make sure no unused hosts are in the file which is probably an error.
        """
        # get all machines that are in use
        used_machines = []
        used_machines.append(self.base_config.jenkins_master_host_config.machine_id)
        used_machines.append(self.base_config.repository_host_config.machine_id)
        for slave_config in self.base_config.jenkins_slave_configs:
            used_machines.append(slave_config.machine_id)

        for job_config in self.job_configs:
            used_machines.append(job_config.webserver_config.machine_id)

        # now check if all defined hosts are within the used machines list
        for host_config in self.base_config.host_machine_infos:
            found = next((x for x in used_machines if x == host_config.machine_id ), None)
            if found is None:
                raise Exception("Config file Error! The host machine with id {0} is not used.".format(host_config.machine_id))


    def _set_container_config(self):
        """
        Fills in values for the web-server container configuration.
        """
        ssh_port = self.base_config.get_next_free_ssh_port()
        used_ports = self.base_config.get_used_ports()
        web_port = 80
        web_server_index = 0

        for job_config in self.job_configs:
            while web_port in used_ports:
                web_port += 1
            used_ports.add(web_port)

            while ssh_port in used_ports:
                ssh_port += 1
            used_ports.add(ssh_port)
            
            job_config.webserver_config.container_ssh_port = ssh_port
            job_config.webserver_config.container_web_port = web_port
            
            job_config.webserver_config.container_conf.container_name = 'cpf-web-server-{0}'.format(web_server_index)
            web_server_index += 1
            job_config.webserver_config.container_conf.container_user = 'root'
            job_config.webserver_config.container_conf.container_image_name = 'cpf-web-server-image'
            job_config.webserver_config.container_conf.published_ports = {web_port:80, ssh_port:22}
            job_config.webserver_config.container_conf.host_volumes = {job_config.webserver_config.host_html_share_dir : _HTML_SHARE_WEB_SERVER_CONTAINER}





class CPFJobConfig:
    """
    Data class that holds the information from the KEY_CPF_JOBS key.
    """
    def __init__(self):
        self.job_name = ''
        self.repository = ''
        self.webserver_config = WebserverConfig()


class WebserverConfig:
    """
    Data class that holds the configuration of the web-server host machine.
    """
    def __init__(self):
        self.machine_id = ''                                # The id of the host machine of the webserver container.
        self.host_html_share_dir = PurePosixPath()          # A directory on the host machine that is shared with the containers html directory. This can be used to look at the page content.
        self.container_ssh_port = None                      # The port on the host that is mapped to the containers ssh port.
        self.container_web_port = None                      # The port on the host that is mapped to the containers port 80 under which the webpage can be reached.
        self.container_conf = config_data.ContainerConfig() # More information about the container that runs the web-server.



def get_example_config_dict():
    """
    Returns a dictionary as it would come from a valid configuration file.
    """
    base_dict = config_data.get_example_config_dict()

    cpf_jobs_list = [
        {
            KEY_JENKINSJOB_BASE_NAME : 'MyCPFProject1',
            KEY_REPOSITORY : 'ssh://fritz@mastermachine:/home/fritz/repositories/MyCPFProject1.git',
            KEY_WEBSERVER_CONFIG : {
                config_data.KEY_MACHINE_ID : "MyMaster",
                KEY_HOST_HTML_SHARE : "/home/fritz/mycpfproject1_html_share",
            }
        },
        {
            KEY_JENKINSJOB_BASE_NAME : 'MyCPFProject2',
            KEY_REPOSITORY : 'ssh://fritz@mastermachine:/home/fritz/repositories/MyCPFProject2.git',
            KEY_WEBSERVER_CONFIG : {
                config_data.KEY_MACHINE_ID : "MyMaster",
                KEY_HOST_HTML_SHARE : "/home/fritz/mycpfproject2_html_share",
            }
        },
    ]

    base_dict[config_data.KEY_JENKINS_CONFIG][KEY_CPF_JOBS] = cpf_jobs_list

    return base_dict