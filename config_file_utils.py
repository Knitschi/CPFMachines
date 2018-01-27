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

KEY_JENKINS_CONFIG = 'JenkinsConfig'
KEY_USE_UNCONFIGURED_JENKINS = 'UseUnconfiguredJenkins'
KEY_JENKINS_ADMIN_USER = 'JenkinsAdminUser'
KEY_JENKINS_ADMIN_USER_PASSWORD = 'JenkinsAdminUserPassword'
KEY_JENKINS_ACCOUNT_CONFIG_FILES = 'JenkinsAccountConfigFiles'
KEY_JENKINS_JOB_CONFIG_FILES = 'JenkinsJobConfigFiles'
KEY_CPP_CODE_BASE_JOBS = 'CppCodeBaseJobs'
KEY_JENKINS_APPROVED_SYSTEM_COMMANDS = 'JenkinsApprovedSystemCommands'
KEY_JENKINS_APPROVED_SCRIPT_SIGNATURES = 'JenkinsApprovedScriptSignatures'


class MachineData:
    """Objects of this class hold the information that is required for an ssh login"""

    def __init__(self):
        self.machine_name = ''
        self.user_name = ''
        self.password = ''
        self.os_type = ''

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
    print('----- Read configuration file ' + config_file)
    with open(config_file) as file:
        data = json.load(file)
    pprint.pprint(data)
    return data


def check_config_file_content(config_dict):
    """
    Checks that the config file has the required content.
    """

    # version check
    # are all required values available
    # does data make sense

    return True

def get_login_data(config_dict):
    """
    Reads the machine login date from a config file dictionary.
    Returns a map that contains machine ids as keys and MachineData objects as values.
    """
    login_data_object_map = {}
    login_data_dict = config_dict[KEY_LOGIN_DATA]
    for key, value in login_data_dict:
        login_data = MachineData()
        login_data.machine_name = value[KEY_MACHINE_NAME]
        login_data.user_name = value[KEY_USER]
        login_data.password = value[KEY_PASSWORD]
        login_data.os_type = value[KEY_OSTYPE]

        if not login_data.password:
            prompt_message = "Please enter the password for account {0}@{}.".format(login_data.user_name, login_data.machine_name)
            login_data.password = getpass.getpass(prompt_message)

        login_data_object_map[key] = login_data

    return login_data_object_map

