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
import getpass
import paramiko

from . import cppcodebasemachines_version

# define config file keys
KEY_VERSION = 'CppCodeBaseMachinesVersion'

KEY_LOGIN_DATA = 'MachineLoginData'
KEY_MACHINE_NAME = 'MachineName'
KEY_USER = 'User'
KEY_PASSWORD = 'Password'
KEY_OSTYPE = 'OSType'

KEY_MASTER_AND_WEB_SERVER_HOST = 'JenkinsMasterAndWebServerHost'
KEY_MACHINE_ID = 'MachineID'
KEY_HOST_HTML_SHARE = 'HostHTMLShare'
KEY_HOST_JENKINS_MASTER_SHARE = 'HostJenkinsMasterShare'
KEY_HOST_TEMP_DIR = 'HostTempDir'

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
KEY_CPP_CODE_BASE_JOBS = 'CppCodeBaseJobs'
KEY_JENKINS_APPROVED_SYSTEM_COMMANDS = 'JenkinsApprovedSystemCommands'
KEY_JENKINS_APPROVED_SCRIPT_SIGNATURES = 'JenkinsApprovedScriptSignatures'




class HostMachineConnection:
    """
    Objects of this class hold the information that is required for an ssh login
    """

    def __init__(self):
        self.machine_name = ''
        self.user_name = ''
        self.os_type = ''
        self.ssh_client = paramiko.SSHClient()


class MasterAndWebServerHostConfig:
    """
    Data class that holds the information from the KEY_MASTER_AND_WEB_SERVER_HOST key.
    """
    def __init__(self):
        self.machine_id = ''
        self.host_html_share_dir = ''
        self.host_jenkins_master_share = ''
        self.host_temp_dir = ''
        self.web_server_container_name = ''
        self.web_server_container_ip = ''
        self.jenkins_master_container_name = ''
        self.jenkins_master_container_ip = ''

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
        self.executors = ''
        self.container_name = ''
        self.container_ip = ''


class JenkinsConfig:
    """
    Data class that holds the information from the KEY_JENKINS_CONFIG key.
    """
    def __init__(self):
        self.use_unconfigured_jenkins = False
        self.admin_user = ''
        self.admin_user_password = ''
        self.account_config_files = []
        self.job_config_files = []
        self.cpp_codebase_jobs = []
        self.approved_system_commands = []
        self.approved_script_signatures = []


class JenkinsAccountConfig:
    """
    Data class that holds the information from the KEY_JENKINS_ACCOUNT_CONFIG_FILES key.
    """
    def __init__(self, user_name_arg, xml_file):
        self.user_name = user_name_arg
        self.xml_config_file = xml_file


class JenkinsJobConfig:
    """
    Data class that holds the information from the KEY_JENKINS_JOB_CONFIG_FILES key.
    """
    def __init__(self, job_name_arg, xml_file):
        self.job_name = job_name_arg
        self.xml_config_file = xml_file


class CppCodeBaseJobConfig:
    """
    Data class that holds the information from the KEY_CPP_CODE_BASE_JOBS key.
    """
    def __init__(self, job_name_arg, repository_address ):
        self.job_name = job_name_arg
        self.repository = repository_address


def write_example_config_file(file_path):
    """
    This function creates a small CppCodeBaseMachines config file for documentation purposes.
    """
    # create an empty dictionary with all possible config values.

    config_dict = {
        KEY_VERSION : cppcodebasemachines_version.CPPCODEBASEMACHINES_VERSION,
        KEY_LOGIN_DATA : {
            'MyMasterMachine' : {
                KEY_MACHINE_NAME : 'mastermachine',
                KEY_USER : 'fritz',
                KEY_PASSWORD : '1234password',
                KEY_OSTYPE : 'Linux'
            },
            'MyLinuxSlave' : {
                KEY_MACHINE_NAME : 'linuxslave',
                KEY_USER : 'fritz',
                KEY_PASSWORD : '1234password',
                KEY_OSTYPE : 'Linux'
            },
            'MyWindowsSlave' : {
                KEY_MACHINE_NAME : 'windowsslave',
                KEY_USER : 'fritz',
                KEY_PASSWORD : '1234password',
                KEY_OSTYPE : 'Windows'
            },
        },
        KEY_MASTER_AND_WEB_SERVER_HOST : {
            KEY_MACHINE_ID : 'MyMasterMachine',
            KEY_HOST_HTML_SHARE : '/home/fritz/ccb_html_share',
            KEY_HOST_JENKINS_MASTER_SHARE : '/home/fritz/jenkins_home',
            KEY_HOST_TEMP_DIR : '/home/fritz/temp'
        },
        KEY_REPOSITORY_HOST : {
            KEY_MACHINE_ID : 'MyMasterMachine',
            KEY_SSH_DIR : '/home/fritz/.ssh'
        },
        KEY_JENKINS_SLAVES : [
            {
                KEY_MACHINE_ID : 'MyLinuxSlave',
                KEY_EXECUTORS : '1'
                KEY_CONTAINER_NAME : 'jenkins-slave-0'
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
                'fitz' : 'UserFritz.xml'
            },
            KEY_JENKINS_JOB_CONFIG_FILES : {
                'MyCustomJob' : 'MyCustomJob.xml'
            },
            KEY_CPP_CODE_BASE_JOBS : {
                'BuildMyCppCodeBase' : 'ssh://fritz@mastermachine:/home/fritz/repositories/BuildMyCppCodeBase.git'
            },
            KEY_JENKINS_APPROVED_SYSTEM_COMMANDS : [
            ],
            KEY_JENKINS_APPROVED_SCRIPT_SIGNATURES : [
                '<script signature from my MyCustomJob jenkinsfile>'
            ]
        }
    }

    config_values = collections.OrderedDict(sorted(config_dict.items(), key=lambda t: t[0]))

    with open(file_path, 'w') as file:
        json.dump(config_values, file, indent=2)


def read_json_file(config_file):
    """
    Returns the content of a json file as dictionary.
    """
    with open(config_file) as file:
        data = json.load(file)
    return data


def check_file_version(config_dict):
    """
    Checks that the version of the file and of the version of the library are the same.
    """
    file_version = _get_checked_value(config_dict, KEY_VERSION)
    if not file_version == cppcodebasemachines_version.CPPCODEBASEMACHINES_VERSION:
        raise Exception("The version of the config file ({0}) does not fit the version of the CppCodeBaseMachines package ({1})."
                        .format(file_version, cppcodebasemachines_version.CPPCODEBASEMACHINES_VERSION))


def get_host_machine_connections(config_dict):
    """
    Reads the machine login date from a config file dictionary.
    Returns a map that contains machine ids as keys and HostMachineConnection objects as values.
    """
    login_data_object_map = {}
    login_data_dict = _get_checked_value(config_dict, KEY_LOGIN_DATA)
    for key, value in login_data_dict.items():
        login_data = HostMachineConnection()
        login_data.machine_name = _get_checked_value(value, KEY_MACHINE_NAME)
        login_data.user_name = _get_checked_value(value, KEY_USER)
        login_data.os_type = _get_checked_value(value, KEY_OSTYPE)

        # The password is optional so we do not check for it.
        password = value[KEY_PASSWORD]
        if not password:
            prompt_message = "Please enter the password for account {0}@{1}.".format(login_data.user_name, login_data.machine_name)
            password = getpass.getpass(prompt_message)

        # make the connection
        login_data.ssh_client.load_system_host_keys()
        login_data.ssh_client.set_missing_host_key_policy(paramiko.WarningPolicy)
        login_data.ssh_client.connect(login_data.machine_name, port=22, username=login_data.user_name, password=password)

        login_data_object_map[key] = login_data

    return login_data_object_map


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


def get_master_and_web_host_config(config_dict):
    """
    Reads information from the config_file dictionary into an MasterAndWebServerHostConfig object and returns it.
    """
    config_data = MasterAndWebServerHostConfig()
    host_config_dict = _get_checked_value(config_dict, KEY_MASTER_AND_WEB_SERVER_HOST)

    config_data.machine_id = _get_checked_value(host_config_dict, KEY_MACHINE_ID)
    config_data.host_html_share_dir = _get_checked_value(host_config_dict, KEY_HOST_HTML_SHARE)
    config_data.host_jenkins_master_share = _get_checked_value(host_config_dict, KEY_HOST_JENKINS_MASTER_SHARE)
    config_data.host_temp_dir = _get_checked_value(host_config_dict, KEY_HOST_TEMP_DIR)

    return config_data


def get_repository_host_config(config_dict):
    """
    Reads information from the config_file dictionary into an RepositoryHostConfig object and returns it.
    """
    config_data = RepositoryHostConfig()
    host_config_dict = _get_checked_value(config_dict, KEY_REPOSITORY_HOST)

    config_data.machine_id = _get_checked_value(host_config_dict, KEY_MACHINE_ID)
    config_data.ssh_dir = _get_checked_value(host_config_dict, KEY_SSH_DIR)

    return config_data


def get_jenkins_slave_configs(config_dict):
    """
    Reads information from the config_file dictionary into a list of JenkinsSlaveConfig objects and returns it.
    """
    object_list = []
    config_data_list = _get_checked_value(config_dict, KEY_JENKINS_SLAVES)
    for slave_dict in config_data_list:
        slave_data = JenkinsSlaveConfig()
        slave_data.machine_id = _get_checked_value(slave_dict, KEY_MACHINE_ID)
        slave_data.executors = _get_checked_value(slave_dict, KEY_EXECUTORS)
        if slave_dict.contains(KEY_CONTAINER_NAME):
            slave_data.container_name = slave_dict[KEY_CONTAINER_NAME]
        object_list.append(slave_data)

    return object_list


def get_jenkins_config(config_dict):
    """
    Reads information from the config_file dictionary into an JenkinsConfig object and returns it.
    """
    config_data = JenkinsConfig()
    jenkins_config_dict = _get_checked_value(config_dict, KEY_JENKINS_CONFIG)

    config_data.use_unconfigured_jenkins = _get_checked_value(jenkins_config_dict, KEY_USE_UNCONFIGURED_JENKINS)
    config_data.admin_user = _get_checked_value(jenkins_config_dict, KEY_JENKINS_ADMIN_USER)
    config_data.admin_user_password = _get_checked_value(jenkins_config_dict, KEY_JENKINS_ADMIN_USER_PASSWORD)
    
    account_config_dict = _get_checked_value(jenkins_config_dict, KEY_JENKINS_ACCOUNT_CONFIG_FILES)
    for key, value in account_config_dict.items():
        config_data.account_config_files.append(JenkinsAccountConfig(key, value))

    job_config_dict = _get_checked_value(jenkins_config_dict, KEY_JENKINS_JOB_CONFIG_FILES)
    for key, value in job_config_dict.items():
        config_data.account_config_files.append(JenkinsJobConfig(key, value))

    ccb_jobs_config_dict = _get_checked_value(jenkins_config_dict, KEY_CPP_CODE_BASE_JOBS)
    for key, value in ccb_jobs_config_dict.items():
        config_data.account_config_files.append(CppCodeBaseJobConfig(key, value))

    config_data.approved_system_commands = jenkins_config_dict[KEY_JENKINS_APPROVED_SYSTEM_COMMANDS]
    config_data.approved_script_signatures = jenkins_config_dict[KEY_JENKINS_APPROVED_SCRIPT_SIGNATURES]

    return config_data


def get_linux_jenkins_slaves(ssh_connections, slave_configs):
    """
    returns the machine ids for all slaves the belong to a linux host machine.
    """
    linux_machine_ids = []
    for slave_config in slave_configs:
        connection = ssh_connections[slave_config.machine_id]
        if connection.os_type == 'Linux':
            linux_machine_ids.append(connection.machine_id)

    return linux_machine_ids
