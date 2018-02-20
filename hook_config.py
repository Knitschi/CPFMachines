

import getpass

from pathlib import PurePosixPath, PureWindowsPath

from ..CPFMachines import config_data
from ..CPFMachines.setup import dev_message 


KEY_JENKINS_ACCOUNT = 'JenkinsAccount'
KEY_JENKINS_URL = 'JenkinsUrl'
KEY_JENKINS_USER = 'JenkinsUser'
KEY_JENKINS_PASSWORD = 'JenkinsPassword'

KEY_REPOSITORY_MACHINES = 'RepositoryMachines'

KEY_CPF_BUILDJOBS = 'CPFBuildJobs'
KEY_JENKINSJOB_BASE_NAME = 'JenkinsJobBasename'
KEY_HOOKED_REPOSITORIES = 'HookedRepositories'

KEY_HOOK_DIRECTORY = 'HookDirectory'
KEY_BUILDJOB_PACKAGE_ARGUMENT = 'BuildJobPackageArg'


###################################################################################
class HookConfigData:
    """
    A class that contains all the information form a configuration file for the deploy_githooks.py script.
    """
    def __init__(self, config_file_dict):

        self.jenkins_account_info = JenkinsAccountInfo()
        self.repository_host_infos = []
        self.hook_configs = []

        self._read_config_data(config_file_dict)


    def get_host_info(self, machine_id):
        return next((x for x in self.repository_host_infos if x.machine_id == machine_id), None)


    def _read_config_data(self, config_dict):
        self._read_jenkins_account_info(config_dict)
        self._read_repository_host_infos(config_dict)
        self._read_hook_configs(config_dict)


    def _read_jenkins_account_info(self, config_dict):
        account_dict = config_dict[KEY_JENKINS_ACCOUNT]
        self.jenkins_account_info.url = config_data._get_checked_value(account_dict, KEY_JENKINS_URL)
        self.jenkins_account_info.user = config_data._get_checked_value(account_dict, KEY_JENKINS_USER)
        self.jenkins_account_info.password = account_dict[KEY_JENKINS_PASSWORD]

        if not self.jenkins_account_info.password:
            prompt_message = "Please enter the password for jenkins user {0}:".format(self.jenkins_account_info.user)
            self.jenkins_account_info.password = getpass.getpass(prompt_message)


    def _read_repository_host_infos(self, config_dict):
        for host_info_dict in config_dict[KEY_REPOSITORY_MACHINES]:
            self.repository_host_infos.append(config_data.HostMachineInfo(host_info_dict))


    def _read_hook_configs(self, config_dict):
        for job_hooks_config_dict in config_dict[KEY_CPF_BUILDJOBS ]:
            job_name = config_data._get_checked_value(job_hooks_config_dict, KEY_JENKINSJOB_BASE_NAME)
            for hook_config_dict in job_hooks_config_dict[KEY_HOOKED_REPOSITORIES]:
                
                project_hook_config = CPFProjectHookConfig()
                project_hook_config.jenkins_job_basename = job_name
                project_hook_config.machine_id = config_data._get_checked_value(hook_config_dict, config_data.KEY_MACHINE_ID)

                hook_dir = config_data._get_checked_value(hook_config_dict, KEY_HOOK_DIRECTORY)
                host_info = self.get_host_info(project_hook_config.machine_id)
                if host_info.is_windows_machine():
                    project_hook_config.hook_dir = PureWindowsPath(hook_dir)
                elif host_info.is_linux_machine():
                    project_hook_config.hook_dir = PurePosixPath(hook_dir)
                else:
                    raise Exception("Unknown os type {0}".format(host_info.os_type))
                
                # package arg is optional
                project_hook_config.buildjob_package_arg = ''
                if KEY_BUILDJOB_PACKAGE_ARGUMENT in hook_config_dict:
                    project_hook_config.buildjob_package_arg = hook_config_dict[KEY_BUILDJOB_PACKAGE_ARGUMENT]

                self.hook_configs.append(project_hook_config)


class JenkinsAccountInfo:
    """
    Login data for a jenkins account.
    """
    def __init__(self):
        self.url = ''
        self.user = ''
        self.password = ''


class CPFProjectHookConfig:
    """
    This class holds information about the hooks for one CPF project.
    """
    def __init__(self):
        self.jenkins_job_basename = ''
        self.machine_id = ''
        self.hook_dir = ''



###################################################################################

def write_example_config_file(file_path):
    """
    This function creates a small CPFMachines config file for documentation purposes.
    """
    # create an empty dictionary with all possible config values.
    config_dict = get_example_config_dict()
    config_data._write_json_file(config_dict, file_path)

def get_example_config_dict():
    """
    Returns a dictionary that contains the data of a valid example configuration.
    """
    config_dict = {
        KEY_JENKINS_ACCOUNT : {
            KEY_JENKINS_URL : 'http://MyMaster:8080',
            KEY_JENKINS_USER : 'fritz',
            KEY_JENKINS_PASSWORD : '1234password',
        },
        KEY_REPOSITORY_MACHINES : [
            {
                config_data.KEY_MACHINE_ID : 'MyMaster',
                config_data.KEY_MACHINE_NAME : 'lhost3',
                config_data.KEY_USER : 'fritz',
                config_data.KEY_PASSWORD : '1234password',
                config_data.KEY_OSTYPE : 'Linux',
                config_data.KEY_TEMPDIR : '/home/fritz/temp'
            },
        ],
        KEY_CPF_BUILDJOBS : [
            {
                KEY_JENKINSJOB_BASE_NAME : 'BuildMyCPFProject',
                KEY_HOOKED_REPOSITORIES : [
                    {
                        config_data.KEY_MACHINE_ID : 'MyMaster',
                        KEY_HOOK_DIRECTORY : '/home/fritz/repositories/BuildMyCPFProject.git/hooks'
                    },
                    {
                        config_data.KEY_MACHINE_ID : 'MyMaster',
                        KEY_HOOK_DIRECTORY : '/home/fritz/repositories/MyPackage.git/hooks'
                    },
                ]
            }
        ]
    }
    return config_dict