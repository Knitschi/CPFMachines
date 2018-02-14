#!/usr/bin/env python3
"""
This module defines the structure of the config file that is used by the setup script.
It also offers utilities create empty config files and read the contents of the file into
python classes.

\TODO insert doxygen documentation here. How can we comment the example file without duplication?
Can we add comments to the KEY definitions that are visible in the docs?

"""

import json
import collections
import pprint

from pathlib import PureWindowsPath, PurePosixPath, PurePath

from . import cpfmachines_version

# define config file keys
KEY_VERSION = 'CPFMachinesVersion'

KEY_LOGIN_DATA = 'HostMachines'
KEY_MACHINE_ID = 'MachineID'
KEY_MACHINE_NAME = 'HostNameOrIP'
KEY_USER = 'User'
KEY_PASSWORD = 'Password'
KEY_OSTYPE = 'OSType'
KEY_TEMPDIR = 'TemporaryDirectory'

KEY_JENKINS_MASTER_HOST = 'JenkinsMasterHost'
KEY_HOST_JENKINS_MASTER_SHARE = 'HostJenkinsMasterShare'

KEY_WEB_SERVER_HOST = 'WebServerHost'
KEY_HOST_HTML_SHARE = 'HostHTMLShare'

KEY_REPOSITORY_HOST = 'RepositoryHost'
KEY_SSH_DIR = 'SSHDir'

KEY_JENKINS_SLAVES = 'JenkinsSlaves'
KEY_EXECUTORS = "Executors"
KEY_CONTAINER_NAME = "ContainerName"

KEY_JENKINS_CONFIG = 'JenkinsConfig'
KEY_USE_UNCONFIGURED_JENKINS = 'UseUnconfiguredJenkins'
KEY_JENKINS_ADMIN_USER = 'JenkinsAdminUser'
KEY_JENKINS_ADMIN_USER_PASSWORD = 'JenkinsAdminUserPassword'
KEY_JENKINS_ACCOUNT_CONFIG_FILES = 'JenkinsAccountConfigFiles'
KEY_JENKINS_JOB_CONFIG_FILES = 'JenkinsJobConfigFiles'
KEY_CPF_JOBS = 'CPFJobs'
KEY_JENKINS_APPROVED_SYSTEM_COMMANDS = 'JenkinsApprovedSystemCommands'
KEY_JENKINS_APPROVED_SCRIPT_SIGNATURES = 'JenkinsApprovedScriptSignatures'


# directories on jenkins-master
# This is the location of the jenkins configuration files on the jenkins-master.
JENKINS_HOME_JENKINS_MASTER_CONTAINER = PurePosixPath('/var/jenkins_home')
_HTML_SHARE_WEB_SERVER_CONTAINER = PurePosixPath('/var/www/html')


class ConfigData:
    """
    This class holds all the information from a CPFMachines config file.
    """
    _LINUX_SLAVE_BASE_NAME = 'jenkins-slave-linux'

    def __init__(self, config_dict):
        # objects that contain the config data
        self.file_version = ''
        self.host_machine_infos = []
        self.jenkins_master_host_config = JenkinsMasterHostConfig()
        self.web_server_host_config = WebserverHostConfig()
        self.repository_host_config = RepositoryHostConfig()
        self.jenkins_slave_configs = []
        self.jenkins_config = JenkinsConfig()

        # internal
        self._config_file_dict = config_dict

        # fill data members and check validity
        self._import_config_data()
        self._check_data_validity()
        self._configure_container()
        self._container_dict = self._get_container_machine_dictionary() 


    def is_linux_machine(self, machine_id):
        info  = self.get_host_info(machine_id)
        return info.os_type == 'Linux'


    def is_windows_machine(self, machine_id):
        info  = self.get_host_info(machine_id)
        return info.os_type == 'Windows'


    def get_all_container(self):
        """
        Returns the names of all the containers in the infrastructure.
        """
        return self._container_dict.keys()

    def get_container_machines(self):
        """
        Returns all ids of host machines that run a docker instance.
        """
        return set(self._container_dict.values())

    def get_container_host(self, container):
        return self._container_dict[container]


    def get_host_info(self, machine_id):
        """
        Get the connection data for a certain host machine.
        """
        return next((x for x in self.host_machine_infos if x.machine_id == machine_id), None)


    def _get_container_machine_dictionary(self):
        """
        Returns a dictionary with all docker container as keys and
        the associated host machine_ids as values.
        """
        id_dict = {}
        id_dict[self.jenkins_master_host_config.container_conf.container_name] = self.jenkins_master_host_config.machine_id
        id_dict[self.web_server_host_config.container_conf.container_name] = self.web_server_host_config.machine_id
        for slave_config in self.jenkins_slave_configs:
            if slave_config.container_conf:
                id_dict[slave_config.container_conf.container_name] = slave_config.machine_id
        return id_dict


    def _import_config_data(self):
        """
        Fills the object with data from the file and derived values.
        This also does validity checks on the data.
        """
        self.file_version = self._config_file_dict[KEY_VERSION]
        self._read_host_machine_data()
        self._read_jenkins_master_host_config()
        self._read_web_server_host_config()
        self._read_repository_host_config()
        self._read_jenkins_slave_configs()
        self._read_jenkins_master_config()


    def _read_host_machine_data(self):
        """
        Reads the information under the KEY_LOGIN_DATA key.
        """
        host_machines = _get_checked_value(self._config_file_dict, KEY_LOGIN_DATA)
        for machine_dict in host_machines:
            machine = HostMachineInfo()
            machine.machine_id = _get_checked_value(machine_dict, KEY_MACHINE_ID)
            machine.host_name = _get_checked_value(machine_dict, KEY_MACHINE_NAME)
            machine.user_name = _get_checked_value(machine_dict, KEY_USER)
            if KEY_PASSWORD in machine_dict: # password is optional
                machine.user_password = machine_dict[KEY_PASSWORD]
            machine.os_type = _get_checked_value(machine_dict, KEY_OSTYPE)

            if machine.os_type == "Windows":
                machine.temp_dir = PureWindowsPath(_get_checked_value(machine_dict, KEY_TEMPDIR))
            elif machine.os_type == "Linux":
                machine.temp_dir = PurePosixPath(_get_checked_value(machine_dict, KEY_TEMPDIR))
            else:
                raise Exception('Function needs to be extended to handle os type ' + machine.os_type)

            self.host_machine_infos.append(machine)


    def _read_jenkins_master_host_config(self):
        """
        Reads the information under the 
        """
        config_dict = _get_checked_value(self._config_file_dict, KEY_JENKINS_MASTER_HOST)

        self.jenkins_master_host_config.machine_id = _get_checked_value(config_dict, KEY_MACHINE_ID)
        self.jenkins_master_host_config.jenkins_home_share = PurePosixPath(_get_checked_value(config_dict, KEY_HOST_JENKINS_MASTER_SHARE))


    def _read_web_server_host_config(self):
        """
        Reads the information under the KEY_WEB_SERVER_HOST key.
        """
        config_dict = _get_checked_value(self._config_file_dict, KEY_WEB_SERVER_HOST)

        self.web_server_host_config.machine_id = _get_checked_value(config_dict, KEY_MACHINE_ID)
        self.web_server_host_config.host_html_share_dir = PurePosixPath(_get_checked_value(config_dict, KEY_HOST_HTML_SHARE))


    def _read_repository_host_config(self):
        """
        Reads the information under the KEY_REPOSITORY_HOST key.
        """
        config_dict = _get_checked_value(self._config_file_dict, KEY_REPOSITORY_HOST)

        self.repository_host_config.machine_id = _get_checked_value(config_dict, KEY_MACHINE_ID)
        self.repository_host_config.ssh_dir = PurePosixPath(_get_checked_value(config_dict, KEY_SSH_DIR))


    def _read_jenkins_slave_configs(self):
        """
        Reads the information under the KEY_JENKINS_SLAVES key.
        """
        config_dict_list = _get_checked_value(self._config_file_dict, KEY_JENKINS_SLAVES)

        for config_dict in config_dict_list:
            slave_config = JenkinsSlaveConfig()
            slave_config.machine_id = _get_checked_value(config_dict, KEY_MACHINE_ID)
            slave_config.executors = int(_get_checked_value(config_dict, KEY_EXECUTORS))

            self.jenkins_slave_configs.append(slave_config)


    def _read_jenkins_master_config(self):
        """
        Reads the information under the KEY_JENKINS_CONFIG key.
        """
        config_dict = _get_checked_value(self._config_file_dict, KEY_JENKINS_CONFIG)

        self.jenkins_config.use_unconfigured_jenkins = _get_checked_value(config_dict, KEY_USE_UNCONFIGURED_JENKINS)
        self.jenkins_config.admin_user = _get_checked_value(config_dict, KEY_JENKINS_ADMIN_USER)
        self.jenkins_config.admin_user_password = _get_checked_value(config_dict, KEY_JENKINS_ADMIN_USER_PASSWORD)
        
        account_config_dict = _get_checked_value(config_dict, KEY_JENKINS_ACCOUNT_CONFIG_FILES)
        for key, value in account_config_dict.items():
            self.jenkins_config.account_config_files.append(ConfigItem(key, value))

        job_config_dict = _get_checked_value(config_dict, KEY_JENKINS_JOB_CONFIG_FILES)
        for key, value in job_config_dict.items():
            self.jenkins_config.job_config_files.append(ConfigItem(key, value))

        cpf_jobs_config_dict = _get_checked_value(config_dict, KEY_CPF_JOBS)
        for key, value in cpf_jobs_config_dict.items():
            self.jenkins_config.cpf_jobs.append(CPFJobConfig(key, value))

        self.jenkins_config.approved_system_commands = config_dict[KEY_JENKINS_APPROVED_SYSTEM_COMMANDS]
        self.jenkins_config.approved_script_signatures = config_dict[KEY_JENKINS_APPROVED_SCRIPT_SIGNATURES]


    def _check_data_validity(self):
        """
        Checks if the data from the config file makes sence.
        """
        self._check_file_version()
        self._check_one_linux_machine_available()
        self._check_master_and_webserver_use_linux_machines()
        self._check_all_hosts_are_in_use()
        self._check_host_ids_are_unique()
        self._check_accounts_are_unique()
        self._check_jenkins_slave_executor_number()


    def _check_file_version(self):
        """
        Checks that the version of the file and of the version of the library are the same.
        """
        file_version = _get_checked_value(self._config_file_dict, KEY_VERSION)
        if not file_version == cpfmachines_version.CPFMACHINES_VERSION:
            raise Exception("Config file Error! The version of the config file ({0}) does not fit the version of the CPFMachines package ({1})."
                            .format(file_version, cpfmachines_version.CPFMACHINES_VERSION))

    
    def _check_one_linux_machine_available(self):
        """
        Checks that at least on of the host machines is a linux machine.
        """
        for data in self.host_machine_infos:
            if data.os_type == "Linux":
                return
        raise Exception("Config file Error! The CPFMachines configuration must at least contain one Linux host machine.")
        

    def _check_master_and_webserver_use_linux_machines(self):
        """
        These to machines are currently implemented as docker containers and therefor need a linux host.
        """
        if not self.is_linux_machine(self.jenkins_master_host_config.machine_id):
            raise Exception("Config file Error! The host for the jenkins master must be a Linux machine.")

        if not self.is_linux_machine(self.web_server_host_config.machine_id):
            raise Exception("Config file Error! The host for the web server must be a Linux machine.")


    def _check_all_hosts_are_in_use(self):
        """
        Make sure no unused hosts are in the file which is probably an error.
        """
        # get all machines that are in use
        used_machines = []
        used_machines.append(self.jenkins_master_host_config.machine_id)
        used_machines.append(self.web_server_host_config.machine_id)
        used_machines.append(self.repository_host_config.machine_id)
        for slave_config in self.jenkins_slave_configs:
            used_machines.append(slave_config.machine_id)

        # now check if all defined hosts are within the used machines list
        for host_config in self.host_machine_infos:
            found = next((x for x in used_machines if x == host_config.machine_id ), None)
            if found is None:
                raise Exception("Config file Error! The host machine with id {0} is not used.".format(host_config.machine_id))


    def _check_host_ids_are_unique(self):
        host_ids = []
        for host_config in self.host_machine_infos:
            host_ids.append(host_config.machine_id)
        
        if len(host_ids) > len(set(host_ids)):
            raise Exception("Config file Error! The host machine ids need to be unique in the {0} list.".format(KEY_LOGIN_DATA))


    def _check_accounts_are_unique(self):
        """
        Make sure that each combination of user and host machine only occurs once in the host config data.
        """
        accounts = []
        for host_config in self.host_machine_infos:
            accounts.append( host_config.user_name + host_config.host_name)

        if len(accounts) > len(set(accounts)):
            raise Exception("Config file Error! The host machine accounts ({0} + {1}) need to be unique in the {2} list.".format(KEY_MACHINE_NAME, KEY_USER, KEY_LOGIN_DATA) )


    def _check_jenkins_slave_executor_number(self):
        for slave_config in self.jenkins_slave_configs:
            if slave_config.executors < 1:
                raise  Exception("Config file Error! Values for key {0} must be larger than zero.".format(KEY_EXECUTORS) )


    def _configure_container(self):
        """
        Sets values to the member variables that hold container names and ips.
        Container names are unique across all hosts.
        """
        # jenkins-master
        self.jenkins_master_host_config.container_conf.container_name = 'jenkins-master'
        self.jenkins_master_host_config.container_conf.container_user = 'jenkins'
        self.jenkins_master_host_config.container_conf.container_image_name = 'jenkins-master-image'
        self.jenkins_master_host_config.container_conf.published_ports = {8080:8080}
        self.jenkins_master_host_config.container_conf.host_volumes = { self.jenkins_master_host_config.jenkins_home_share : JENKINS_HOME_JENKINS_MASTER_CONTAINER}
        if not self.jenkins_config.use_unconfigured_jenkins: # Switch off the jenkins configuration wizard at startup when jenkins is configured by the script.
            self.jenkins_master_host_config.container_conf.envvar_definitions = ['JAVA_OPTS="-Djenkins.install.runSetupWizard=false"']

        # cft-web-server
        self.web_server_host_config.container_conf.container_name = 'cpf-web-server'
        self.web_server_host_config.container_conf.container_user = 'root'
        self.web_server_host_config.container_conf.container_image_name = 'cpf-web-server-image'
        mapped_ssh_port = 23
        self.web_server_host_config.container_ssh_port = mapped_ssh_port
        self.web_server_host_config.container_conf.published_ports = {80:80, mapped_ssh_port:22}
        mapped_ssh_port += 1
        self.web_server_host_config.container_conf.host_volumes = {self.web_server_host_config.host_html_share_dir : _HTML_SHARE_WEB_SERVER_CONTAINER}
        

        # set names and ips to linux slave container
        ip_index = 4
        linux_name_index = 0
        windows_name_index = 0
        for slave_config in self.jenkins_slave_configs:
            if self.is_linux_machine(slave_config.machine_id):
                slave_config.slave_name = 'CPF-{0}-linux-slave-{1}'.format(cpfmachines_version.CPFMACHINES_VERSION, linux_name_index)
                slave_config.container_conf = ContainerConfig()
                slave_config.container_conf.container_name = "{0}-{1}".format(self._LINUX_SLAVE_BASE_NAME, linux_name_index)
                linux_name_index += 1
                slave_config.container_conf.container_user = 'jenkins'
                ip_index += 1
                slave_config.container_conf.container_image_name = self._LINUX_SLAVE_BASE_NAME + '-image'

            elif self.is_windows_machine(slave_config.machine_id):
                slave_config.slave_name = 'CPF-{0}-windows-slave-{1}'.format(cpfmachines_version.CPFMACHINES_VERSION, windows_name_index)
                windows_name_index += 1

            else:
                raise Exception('Function needs to be extended to handle os type of machine ' + slave_config.machine_id )

        # set the mapped ssh ports
        forbidden_ports = (80, 8080) # these are already used by jenkins and the webserver
        for slave_config in self.jenkins_slave_configs:
            if self.is_linux_machine(slave_config.machine_id):
                # do not use ports that are used othervise
                while mapped_ssh_port in forbidden_ports:
                    mapped_ssh_port += 1
                slave_config.container_conf.published_ports = {mapped_ssh_port:22}
                mapped_ssh_port += 1



class HostMachineInfo:
    """
    Objects of this class hold the information that is required for an ssh login
    """

    def __init__(self):
        self.machine_id = ''
        self.host_name = ''
        self.user_name = ''
        self.user_password = ''
        self.os_type = ''
        self.temp_dir = None


class JenkinsMasterHostConfig:
    """
    Data class that holds the information from the KEY_MASTER_AND_WEB_SERVER_HOST key.
    """
    def __init__(self):
        self.machine_id = ''                        # The host machine on which the container is run.
        self.jenkins_home_share = PurePosixPath()   # The directory on the host that is shared with the containers home directory.
        self.container_conf = ContainerConfig()     # Information about the container.


class ContainerConfig:
    """
    Data class that holds information about a container.
    """
    def __init__(self):
        self.container_name = ''            # The name of the container.
        self.container_user = ''            # The name of the user that runs the services in the container.
        self.container_image_name = ''      # The name of the image which is used to instantiate the container.
        self.published_ports = {}           # The key is the port on the host, the value the port in the container.
        self.host_volumes = {}              # The key is the path on the host, the value the path in the container.
        self.envvar_definitions = []         # Environment variables that are defined in the container.


class WebserverHostConfig:
    """
    Data class that holds the configuration of the web-server host machine.
    """
    def __init__(self):
        self.machine_id = ''
        self.host_html_share_dir = PurePosixPath()      
        self.container_ssh_port = None                  # The port on the host that is mapped to the containers ssh port.
        self.container_conf = ContainerConfig()


class RepositoryHostConfig:
    """
    Data class that holds the information from the KEY_REPOSITORY_HOST key.
    """
    def __init__(self):
        self.machine_id = ''
        self.ssh_dir = ''


class JenkinsSlaveConfig:
    """
    Data class that holds the information from one item under the KEY_JENKINS_SLAVES key.
    """
    def __init__(self):
        self.machine_id = ''
        self.slave_name = ''
        self.executors = ''
        self.container_conf = None


class JenkinsConfig:
    """
    Data class that holds the information from the KEY_JENKINS_CONFIG key.
    """
    def __init__(self):
        self.use_unconfigured_jenkins = False   # Setting this option will prevent the pre-configuation of jenkins. Needed for createing a first account xml file?
        self.admin_user = ''
        self.admin_user_password = ''
        self.account_config_files = []
        self.job_config_files = []
        self.cpf_jobs = []
        self.approved_system_commands = []
        self.approved_script_signatures = []


class ConfigItem:
    """
    Data class that holds the information about pieces of config information
    that jenkins holds in a single config.xml file.
    """
    def __init__(self, name_arg, xml_file_arg):
        self.name = name_arg
        self.xml_file = PurePath(xml_file_arg)


class CPFJobConfig:
    """
    Data class that holds the information from the KEY_CPF_JOBS key.
    """
    def __init__(self, job_name_arg, repository_address ):
        self.job_name = job_name_arg
        self.repository = repository_address


def write_example_config_file(file_path):
    """
    This function creates a small CPFMachines config file for documentation purposes.
    """
    # create an empty dictionary with all possible config values.
    config_dict = get_example_config_dict()
    _write_json_file(config_dict, file_path)


def read_json_file(config_file):
    """
    Returns the content of a json file as dictionary.
    """
    with open(str(config_file)) as file:
        data = json.load(file)
    return data


def get_example_config_dict():
    """
    Returns a dictionary that contains the data of a valid example configuration.
    """
    config_dict = {
        KEY_VERSION : cpfmachines_version.CPFMACHINES_VERSION,
        KEY_LOGIN_DATA : [
            {
                KEY_MACHINE_ID : 'MyMaster',
                KEY_MACHINE_NAME : 'lhost3',
                KEY_USER : 'fritz',
                KEY_PASSWORD : '1234password',
                KEY_OSTYPE : 'Linux',
                KEY_TEMPDIR : '/home/fritz/temp'
            },
            {
                KEY_MACHINE_ID : 'MyLinuxSlave',
                KEY_MACHINE_NAME : '192.168.0.5',
                KEY_USER : 'fritz',
                KEY_PASSWORD : '1234password',
                KEY_OSTYPE : 'Linux',
                KEY_TEMPDIR : '/home/fritz/temp'
            },
            {
                KEY_MACHINE_ID : 'MyWindowsSlave',
                KEY_MACHINE_NAME : 'whost12',
                KEY_USER : 'fritz',
                KEY_OSTYPE : 'Windows',
                KEY_TEMPDIR : 'C:/temp'
            },
        ],
        KEY_JENKINS_MASTER_HOST : {
            KEY_MACHINE_ID : 'MyMaster',
            KEY_HOST_JENKINS_MASTER_SHARE : '/home/fritz/jenkins_home'
        },
        KEY_WEB_SERVER_HOST : {
            KEY_MACHINE_ID : 'MyMaster',
            KEY_HOST_HTML_SHARE : '/home/fritz/cpf_html_share',
        },
        KEY_REPOSITORY_HOST : {
            KEY_MACHINE_ID : 'MyMaster',
            KEY_SSH_DIR : '/home/fritz/.ssh'
        },
        KEY_JENKINS_SLAVES : [
            {
                KEY_MACHINE_ID : 'MyLinuxSlave',
                KEY_EXECUTORS : '2'
            },
            {
                KEY_MACHINE_ID : 'MyMaster',
                KEY_EXECUTORS : '1'
            },
            {
                KEY_MACHINE_ID : 'MyWindowsSlave',
                KEY_EXECUTORS : '1'
            },
        ],
        KEY_JENKINS_CONFIG : {
            KEY_USE_UNCONFIGURED_JENKINS : False,
            KEY_JENKINS_ADMIN_USER : 'fritz',
            KEY_JENKINS_ADMIN_USER_PASSWORD : '1234password',
            KEY_JENKINS_ACCOUNT_CONFIG_FILES : {
                'hans' : 'UserHans.xml'
            },
            KEY_JENKINS_JOB_CONFIG_FILES : {
                'MyCustomJob' : 'MyCustomJob.xml'
            },
            KEY_CPF_JOBS : {
                'BuildMyCPFProject' : 'ssh://fritz@mastermachine:/home/fritz/repositories/BuildMyCPFProject.git'
            },
            KEY_JENKINS_APPROVED_SYSTEM_COMMANDS : [
            ],
            KEY_JENKINS_APPROVED_SCRIPT_SIGNATURES : [
                '<script signature from my MyCustomJob jenkinsfile>'
            ]
        }
    }
    return config_dict


def _write_json_file(config_dict, file_path):
    """
    Writes a dictionary to .json file.
    """
    config_values = collections.OrderedDict(sorted(config_dict.items(), key=lambda t: t[0]))

    with open(file_path, 'w') as file:
        json.dump(config_values, file, indent=2)


def _get_checked_value(dictionary, key):
    """
    Checks that the given key exists in the dictionary and that
    it has a non empty value.
    """
    if key in dictionary:
        value = dictionary[key]
        value_string = str(value)
        if value_string: # we check the string to prevent problems when the value is False
            return value
        else:
            raise Exception("The config file is missing a value for key {0}".format(key))

    raise Exception("The config file is missing an entry with key {0}".format(key))

