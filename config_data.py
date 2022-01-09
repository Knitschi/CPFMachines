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

import cpfmachines_version

# define config file keys
KEY_VERSION = 'CPFMachinesVersion'

KEY_LOGIN_DATA = 'HostMachines'
KEY_MACHINE_ID = 'MachineID'
KEY_HOST = 'HostNameOrIP'
KEY_USER = 'User'
KEY_PASSWORD = 'Password'
KEY_OSTYPE = 'OSType'
KEY_TEMPDIR = 'TemporaryDirectory'

KEY_JENKINS_MASTER_HOST = 'JenkinsMasterHost'
KEY_HOST_JENKINS_MASTER_SHARE = 'HostJenkinsMasterShare'

KEY_SSH_REPOSITORY_HOSTS = 'SSHRepositoryHosts'
KEY_SSH_DIR = 'SSHDir'

KEY_HTTPS_REPOSITORY_HOSTS = 'HTTPSRepositoryHosts'

KEY_JENKINS_SLAVES = 'JenkinsSlaves'
KEY_EXECUTORS = "Executors"
KEY_CONTAINER_NAME = "ContainerName"

KEY_JENKINS_CONFIG = 'JenkinsConfig'
KEY_USE_UNCONFIGURED_JENKINS = 'UseUnconfiguredJenkins'
KEY_JENKINS_ADMIN_USER = 'JenkinsAdminUser'
KEY_JENKINS_ADMIN_USER_PASSWORD = 'JenkinsAdminUserPassword'
KEY_JENKINS_ACCOUNT_CONFIG_FILES = 'JenkinsAccountConfigFiles'
KEY_JENKINS_JOB_CONFIG_FILES = 'JenkinsJobConfigFiles'
KEY_JENKINS_APPROVED_SYSTEM_COMMANDS = 'JenkinsApprovedSystemCommands'
KEY_JENKINS_APPROVED_SCRIPT_SIGNATURES = 'JenkinsApprovedScriptSignatures'

KEY_CPF_JOBS = 'CPFJobs'
KEY_JENKINSJOB_BASE_NAME = 'JenkinsJobBasename'
KEY_CI_REPOSITORY = 'CIRepository'
KEY_BUILD_RESULT_REPOSITORY = 'BuildResultRepository'
KEY_BUILD_RESULT_REPOSITORY_PROJECT_SUBDIRECTORY = 'BuildResultRepositoryProjectSubdirectory'
KEY_CPFCMake_DIR = 'CPFCMake_DIR'
KEY_CPFBuildscripts_DIR = 'CPFBuildscripts_DIR'
KEY_CIBuildConfigurations_DIR = 'CIBuildConfigurations_DIR'

KEY_WEBSERVER = 'WebServer'

# locations
# This is the location of the jenkins configuration files on the jenkins-master.
JENKINS_HOME_JENKINS_MASTER_CONTAINER = PurePosixPath('/var/jenkins_home')
# The location of the web repository on the web-server container
WEB_SERVER_REPOSITORY_DIR = '/home/'


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
        self.ssh_repository_host_accesses = []
        self.https_repository_accesses = []
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
        return self.get_host_info(machine_id).is_linux_machine()


    def is_windows_machine(self, machine_id):
        return self.get_host_info(machine_id).is_windows_machine()


    def get_all_container(self):
        """
        Returns the names of all the containers in the infrastructure.
        """
        return list(self._container_dict)

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
        for slave_config in self.jenkins_slave_configs:
            if slave_config.container_conf:
                id_dict[slave_config.container_conf.container_name] = slave_config.machine_id

        for cpf_job_config in self.jenkins_config.cpf_job_configs:
            if cpf_job_config.webserver_config.machine_id:
                id_dict[cpf_job_config.webserver_config.container_conf.container_name] = cpf_job_config.webserver_config.machine_id

        return id_dict


    def _import_config_data(self):
        """
        Fills the object with data from the file and derived values.
        This also does validity checks on the data.
        """
        self.file_version = self._config_file_dict[KEY_VERSION]
        self._read_host_machine_data()
        self._read_jenkins_master_host_config()
        self._read_ssh_repository_host_configs()
        self._read_https_repository_host_configs()
        self._read_jenkins_slave_configs()
        self._read_jenkins_master_config()


    def _read_host_machine_data(self):
        """
        Reads the information under the KEY_LOGIN_DATA key.
        """
        host_machines = get_checked_value(self._config_file_dict, KEY_LOGIN_DATA)
        for machine_dict in host_machines:
            self.host_machine_infos.append(HostMachineInfo(machine_dict))


    def _read_jenkins_master_host_config(self):
        """
        Reads the information under the KEY_JENKINS_MASTER_HOST key.
        """
        config_dict = get_checked_value(self._config_file_dict, KEY_JENKINS_MASTER_HOST)

        self.jenkins_master_host_config.machine_id = get_checked_value(config_dict, KEY_MACHINE_ID)
        self.jenkins_master_host_config.jenkins_home_share = PurePosixPath(get_checked_value(config_dict, KEY_HOST_JENKINS_MASTER_SHARE))


    def _read_ssh_repository_host_configs(self):
        """
        Reads the information under the KEY_SSH_REPOSITORY_HOSTS key.
        """
        config_dict_list = get_checked_value(self._config_file_dict, KEY_SSH_REPOSITORY_HOSTS)
        for config_dict in config_dict_list:
            repository_config = SSHRepositoryConfig()
            repository_config.machine_id = get_checked_value(config_dict, KEY_MACHINE_ID)
            repository_config.ssh_dir = PurePosixPath(get_checked_value(config_dict, KEY_SSH_DIR))
            self.ssh_repository_host_accesses.append(repository_config)


    def _read_https_repository_host_configs(self):
        """
        Reads the information under the KEY_HTTPS_REPOSITORY_HOSTS key.
        """
        config_dict_list = get_checked_value(self._config_file_dict, KEY_HTTPS_REPOSITORY_HOSTS)
        for config_dict in config_dict_list:
            repository_config = HTTPSRepositoryHostConfig()

            repository_config.host_name = get_checked_value(config_dict, KEY_HOST)
            repository_config.user_name = get_checked_value(config_dict, KEY_USER)
            if KEY_PASSWORD in config_dict: # password is optional
                repository_config.user_password = config_dict[KEY_PASSWORD]

            self.https_repository_accesses.append(repository_config)


    def _read_jenkins_slave_configs(self):
        """
        Reads the information under the KEY_JENKINS_SLAVES key.
        """
        config_dict_list = get_checked_value(self._config_file_dict, KEY_JENKINS_SLAVES)

        for config_dict in config_dict_list:
            slave_config = JenkinsSlaveConfig()
            slave_config.machine_id = get_checked_value(config_dict, KEY_MACHINE_ID)
            slave_config.executors = int(get_checked_value(config_dict, KEY_EXECUTORS))

            self.jenkins_slave_configs.append(slave_config)


    def _read_jenkins_master_config(self):
        """
        Reads the information under the KEY_JENKINS_CONFIG key.
        """
        config_dict = get_checked_value(self._config_file_dict, KEY_JENKINS_CONFIG)

        self.jenkins_config.use_unconfigured_jenkins = get_checked_value(config_dict, KEY_USE_UNCONFIGURED_JENKINS)
        self.jenkins_config.admin_user = get_checked_value(config_dict, KEY_JENKINS_ADMIN_USER)
        self.jenkins_config.admin_user_password = get_checked_value(config_dict, KEY_JENKINS_ADMIN_USER_PASSWORD)
        
        account_config_dict = get_checked_value(config_dict, KEY_JENKINS_ACCOUNT_CONFIG_FILES)
        for key, value in account_config_dict.items():
            self.jenkins_config.account_config_files.append(ConfigItem(key, value))

        job_config_dict = get_checked_value(config_dict, KEY_JENKINS_JOB_CONFIG_FILES)
        for key, value in job_config_dict.items():
            self.jenkins_config.job_config_files.append(ConfigItem(key, value))

        # cpf jobs
        self._read_cpf_job_configs(config_dict)

        # approved scripts
        self.jenkins_config.approved_system_commands = config_dict[KEY_JENKINS_APPROVED_SYSTEM_COMMANDS]
        self.jenkins_config.approved_script_signatures = config_dict[KEY_JENKINS_APPROVED_SCRIPT_SIGNATURES]


    def _read_cpf_job_configs(self, jenkins_config_dict):
        """
        Reads a list of cpf jenkins job configurations from the config file dictionary. 
        """
        job_config_dict_list = get_checked_value(jenkins_config_dict, KEY_CPF_JOBS)
        for job_config_dict in job_config_dict_list:
            config = CPFJobConfig()
            config.base_job_name = get_checked_value(job_config_dict, KEY_JENKINSJOB_BASE_NAME)
            config.ci_repository = get_checked_value(job_config_dict, KEY_CI_REPOSITORY)
            config.result_repository = get_checked_value(job_config_dict, KEY_BUILD_RESULT_REPOSITORY)
            config.result_repository_project_subdirectory = PurePosixPath(get_checked_value(job_config_dict, KEY_BUILD_RESULT_REPOSITORY_PROJECT_SUBDIRECTORY))
            config.CPFCMake_DIR = PurePosixPath(get_checked_value(job_config_dict, KEY_CPFCMake_DIR))
            config.CPFBuildscripts_DIR = PurePosixPath(get_checked_value(job_config_dict, KEY_CPFBuildscripts_DIR))
            config.CIBuildConfigurations_DIR = PurePosixPath(get_checked_value(job_config_dict, KEY_CIBuildConfigurations_DIR))


            # Using a cpf provided webserver is optional
            if KEY_WEBSERVER in job_config_dict:
                webserver_config_dict = get_checked_value(job_config_dict, KEY_WEBSERVER)
                config.webserver_config.machine_id = get_checked_value(webserver_config_dict, KEY_MACHINE_ID)

            self.jenkins_config.cpf_job_configs.append(config)


    def _check_data_validity(self):
        """
        Checks if the data from the config file makes sence.
        """
        self._check_file_version()
        self._check_one_linux_machine_available()
        self._check_container_use_linux_hosts()
        self._check_all_hosts_are_in_use()
        self._check_host_ids_are_unique()
        self._check_accounts_are_unique()
        self._check_jenkins_slave_executor_number()


    def _check_file_version(self):
        """
        Checks that the version of the file and of the version of the library are the same.
        """
        file_version = get_checked_value(self._config_file_dict, KEY_VERSION)
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


    def _check_container_use_linux_hosts(self):
        """
        Check that all container hosts are linux machines.
        """
        # jenkins master
        if not self.is_linux_machine(self.jenkins_master_host_config.machine_id):
            raise Exception("Config file Error! The host for the jenkins master must be a Linux machine.")

        # web server hosts
        for job_config in self.jenkins_config.cpf_job_configs:
            machine_id = job_config.webserver_config.machine_id
            if machine_id and not self.is_linux_machine(machine_id):
                raise Exception("Config file Error! The webserver container host with {0} \"{1}\" is not a Linux machine.".format(KEY_MACHINE_ID, machine_id))


    def _check_all_hosts_are_in_use(self):
        """
        Make sure no unused hosts are in the file which is probably an error.
        """
        # get all machines that are in use
        used_machines = []
        used_machines.append(self.jenkins_master_host_config.machine_id)

        for host_config in self.ssh_repository_host_accesses:
            used_machines.append(host_config.machine_id)
        
        for slave_config in self.jenkins_slave_configs:
            used_machines.append(slave_config.machine_id)

        for job_config in self.jenkins_config.cpf_job_configs:
            used_machines.append(job_config.webserver_config.machine_id)

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
            raise Exception("Config file Error! The host machine accounts ({0} + {1}) need to be unique in the {2} list.".format(KEY_HOST, KEY_USER, KEY_LOGIN_DATA) )


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
        used_ports = set([8080])
        self.jenkins_master_host_config.container_conf.host_volumes = { self.jenkins_master_host_config.jenkins_home_share : JENKINS_HOME_JENKINS_MASTER_CONTAINER}
        if not self.jenkins_config.use_unconfigured_jenkins: # Switch off the jenkins configuration wizard at startup when jenkins is configured by the script.
            self.jenkins_master_host_config.container_conf.envvar_definitions = ['JAVA_OPTS="-Djenkins.install.runSetupWizard=false"']
       

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

        # set the mapped ports for slave and web container
        mapped_ssh_port = 23
        for slave_config in self.jenkins_slave_configs:
            if self.is_linux_machine(slave_config.machine_id):
                # do not use ports that are used otherwise
                while mapped_ssh_port in used_ports:
                    mapped_ssh_port += 1
                used_ports.add( mapped_ssh_port)

                slave_config.container_conf.published_ports = {mapped_ssh_port:22}


        # set mapped ports and names of web-server container
        mapped_web_port = 8081
        for job_config in self.jenkins_config.cpf_job_configs:
            if job_config.webserver_config.machine_id:  # Setting up a webserver is optional

                while mapped_ssh_port in used_ports:
                    mapped_ssh_port += 1
                used_ports.add( mapped_ssh_port)
            
                while mapped_web_port in used_ports:
                    mapped_web_port += 1
                used_ports.add(mapped_web_port)

                job_config.webserver_config.container_ssh_port = mapped_ssh_port
                job_config.webserver_config.container_web_port = mapped_web_port
            
                job_config.webserver_config.container_conf.container_name = '{0}-web-server'.format(job_config.base_job_name)
                job_config.webserver_config.container_conf.container_user = 'jenkins'
                job_config.webserver_config.ssh_dir = PurePosixPath('/home/' + job_config.webserver_config.container_conf.container_user + '/.ssh')
                job_config.webserver_config.container_conf.container_image_name = 'cpf-web-server-image'
                job_config.webserver_config.container_conf.published_ports = {mapped_web_port:80, mapped_ssh_port:22}


        self._next_free_ssh_port = mapped_ssh_port



class HostMachineInfo:
    """
    Objects of this class hold the information that is required for an ssh login
    """

    def __init__(self, host_info_dict):
        self.machine_id = get_checked_value(host_info_dict, KEY_MACHINE_ID)
        self.host_name = get_checked_value(host_info_dict, KEY_HOST)
        self.user_name = get_checked_value(host_info_dict, KEY_USER)
        
        self.user_password = ''
        if KEY_PASSWORD in host_info_dict: # password is optional
            self.user_password = host_info_dict[KEY_PASSWORD]
        
        self.os_type = get_checked_value(host_info_dict, KEY_OSTYPE)
        self.temp_dir = None
        if self.os_type == "Windows":
            self.temp_dir = PureWindowsPath(get_checked_value(host_info_dict, KEY_TEMPDIR))
        elif self.os_type == "Linux":
            self.temp_dir = PurePosixPath(get_checked_value(host_info_dict, KEY_TEMPDIR))
        else:
            raise Exception('Function needs to be extended to handle os type ' + self.os_type)

    def is_windows_machine(self):
        return self.os_type == "Windows"

    def is_linux_machine(self):
        return self.os_type == "Linux"


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
        self.envvar_definitions = []        # Environment variables that are defined in the container.


class SSHRepositoryConfig:
    """
    Data class that holds the information from the KEY_SSH_REPOSITORY_HOSTS key.
    This is intended for git repositories that are hosted in the local network
    and can be accessed with the ssh protocol.
    """
    def __init__(self):
        self.machine_id = ''
        self.ssh_dir = ''


class HTTPSRepositoryHostConfig:
    """
    Data class that holds the credentials for repositories that are accessed via https.
    """
    def __init__(self):
        self.host_name = ''
        self.user_name = ''
        self.user_password = ''


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
        self.cpf_job_configs = []
        self.account_config_files = []
        self.job_config_files = []
        self.approved_system_commands = []
        self.approved_script_signatures = []


class CPFJobConfig:
    """
    Data class that holds the information from the KEY_CPF_JOBS key.
    """
    def __init__(self):
        self.base_job_name = ''                                         # The name of the buildjob
        self.ci_repository = ''                                         # The repository that contains the CPF ci-project that shall be build.
        self.result_repository = ''                                     # The address of the git repository that provides the content of the hosted pages.
        self.result_repository_project_subdirectory = PurePosixPath()   # The subdirectory in the build_result_repository that shall be published.
        self.CPFCMake_DIR = PurePosixPath()                             # Absolute or relative path to the directory that holds the CPFCMake module. This is handed to the 0_CopyScripts script.
        self.CPFBuildscripts_DIR = PurePosixPath()                      # Absolute or relative path to the directory that holds the CPFBuildscripts module. This is handed to the 0_CopyScripts script.                                       
        self.CIBuildConfigurations_DIR = PurePosixPath()                # Absolute or relative path to the directory that holds the CIBuildConfigurations. This is handed to the 0_CopyScripts script.
        self.webserver_config = WebserverConfig()                       # The configuration of the webserver that is used publish this jobs build results.

class WebserverConfig:
    """
    Data class that holds the configuration of the web-server host machine.
    """
    def __init__(self):
        self.machine_id = ''                                            # The id of the host machine of the webserver container.
        self.container_ssh_port = None                                  # The port on the host that is mapped to the containers ssh port.
        self.container_web_port = None                                  # The port on the host that is mapped to the containers port 80 under which the webpage can be reached.
        self.container_conf = ContainerConfig()                         # More information about the container that runs the web-server.
        self.ssh_dir = ''

class ConfigItem:
    """
    Data class that holds the information about pieces of config information
    that jenkins holds in a single config.xml file.
    """
    def __init__(self, name_arg, xml_file_arg):
        self.name = name_arg
        self.xml_file = PurePath(xml_file_arg)


def write_example_config_file(file_path):
    """
    This function creates a small CPFMachines config file for documentation purposes.
    """
    # create an empty dictionary with all possible config values.
    config_dict = get_example_config_dict()
    write_json_file(config_dict, file_path)


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
                KEY_HOST : 'lhost3',
                KEY_USER : 'fritz',
                KEY_PASSWORD : '1234password',
                KEY_OSTYPE : 'Linux',
                KEY_TEMPDIR : '/home/fritz/temp'
            },
            {
                KEY_MACHINE_ID : 'MyLinuxSlave',
                KEY_HOST : '192.168.0.5',
                KEY_USER : 'fritz',
                KEY_PASSWORD : '1234password',
                KEY_OSTYPE : 'Linux',
                KEY_TEMPDIR : '/home/fritz/temp'
            },
            {
                KEY_MACHINE_ID : 'MyWindowsSlave',
                KEY_HOST : 'whost12',
                KEY_USER : 'fritz',
                KEY_OSTYPE : 'Windows',
                KEY_TEMPDIR : 'C:/temp'
            },
        ],
        KEY_JENKINS_MASTER_HOST : {
            KEY_MACHINE_ID : 'MyMaster',
            KEY_HOST_JENKINS_MASTER_SHARE : '/home/fritz/jenkins_home'
        },
        KEY_SSH_REPOSITORY_HOSTS : [
            {
                KEY_MACHINE_ID : 'MyMaster',
                KEY_SSH_DIR : '/home/fritz/.ssh'
            },
            {
                KEY_MACHINE_ID : 'MyLinuxSlave',
                KEY_SSH_DIR : '/home/fritz/.ssh'
            }
        ],
        KEY_HTTPS_REPOSITORY_HOSTS : [
            {
                KEY_HOST : 'github.com',
                KEY_USER : 'Fritz',
                KEY_PASSWORD : '1234password'
            },
            {
                KEY_HOST : 'gitlab.com',
                KEY_USER : 'Fratz',
                KEY_PASSWORD : '5678password'
            }
        ],
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
            KEY_CPF_JOBS : [
                {
                    KEY_JENKINSJOB_BASE_NAME : 'MyCPFProject1',
                    KEY_CI_REPOSITORY : 'ssh://fritz@mastermachine:/home/fritz/repositories/MyCPFProject1.git',
                    KEY_BUILD_RESULT_REPOSITORY : 'ssh://fritz@mastermachine:/home/fritz/repositories/buildresults',
                    KEY_BUILD_RESULT_REPOSITORY_PROJECT_SUBDIRECTORY : 'projects/MyCPFProject1',
                    KEY_CPFCMake_DIR : 'Sources/CPFCMake',
                    KEY_CPFBuildscripts_DIR : 'Sources/CPFBuildscripts',
                    KEY_CIBuildConfigurations_DIR : 'Sources/CIBuildConfigurations',
                    KEY_WEBSERVER : {
                        KEY_MACHINE_ID : 'MyMaster'
                    }
                },
                {
                    KEY_JENKINSJOB_BASE_NAME : 'MyCPFProject2',
                    KEY_CI_REPOSITORY : 'https://github.com/Fritz/MyCPFProject2.git',
                    KEY_BUILD_RESULT_REPOSITORY : 'ssh://fritz@mastermachine:/home/fritz/repositories/buildresults',
                    KEY_BUILD_RESULT_REPOSITORY_PROJECT_SUBDIRECTORY : 'projects/MyCPFProject2',
                    KEY_CPFCMake_DIR : 'C:/CPFCMake',
                    KEY_CPFBuildscripts_DIR : 'C:/CPFBuildscripts',
                    KEY_CIBuildConfigurations_DIR : 'C:/CIBuildConfigurations',
                    KEY_WEBSERVER : {
                        KEY_MACHINE_ID : 'MyMaster'
                    }
                },
                {
                    KEY_JENKINSJOB_BASE_NAME : 'MyCPFProject3',
                    KEY_CI_REPOSITORY : 'https://github.com/Fritz/MyCPFProject3.git',
                    KEY_BUILD_RESULT_REPOSITORY : 'https://github.com/Knitschi/Knitschi.github.io.git',
                    KEY_BUILD_RESULT_REPOSITORY_PROJECT_SUBDIRECTORY : 'MyCPFProject3',
                    KEY_CPFCMake_DIR : 'Sources/external/CPFCMake',
                    KEY_CPFBuildscripts_DIR : 'Sources/external/CPFBuildscripts',
                    KEY_CIBuildConfigurations_DIR : 'Sources/external/CIBuildConfigurations'
                }
            ],
            KEY_JENKINS_ACCOUNT_CONFIG_FILES : {
                'hans' : 'UserHans.xml'
            },
            KEY_JENKINS_JOB_CONFIG_FILES : {
                'MyCustomJob' : 'MyCustomJob.xml'
            },
            KEY_JENKINS_APPROVED_SYSTEM_COMMANDS : [
                'ssh bla blub'
            ],
            KEY_JENKINS_APPROVED_SCRIPT_SIGNATURES : [
                '<script signature from my MyCustomJob jenkinsfile>'
            ]
        }
    }

    return config_dict


def write_json_file(config_dict, file_path):
    """
    Writes a dictionary to .json file.
    """
    config_values = collections.OrderedDict(sorted(config_dict.items(), key=lambda t: t[0]))

    with open(file_path, 'w') as file:
        json.dump(config_values, file, indent=2)


def get_checked_value(dictionary, key):
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


