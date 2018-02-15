#!/usr/bin/env python3

"""
This script is used to generate a post-receive hook script for
git that is then copied to a number of given directories.
The hook script is used to trigger the CPF jenkins job that is
defined by the CPFJenkinsjob module.
"""

import sys
import io
import os
import subprocess
import json
import pprint
from pathlib import PurePath

from ..CPFMachines import setup as machines_setup
from ..CPFMachines import config_data
from ..CPFMachines import fileutil
from ..CPFMachines.connections import ConnectionsHolder

from . import add_jenkinsjob
from . import setup
from . import hook_config

_SCRIPT_DIR = PurePath(os.path.dirname(os.path.realpath(__file__)))

_POST_RECEIVE_HOOK_TEMPLATE = 'post-receive.in'


def main(config_file):
    """
    Entry of the script.
    """

    # read configuration
    config_dict = config_data.read_json_file(config_file)
    config = hook_config.HookConfigData(config_dict)

    print('----- Establish ssh connections to repository machines')
    connections = ConnectionsHolder(config.repository_host_infos)

    script_template = _SCRIPT_DIR.joinpath('post-receive.in')

    # Configure one hook for each given package.
    # The hook needs to tell the buildjob which package was changed,
    # so the job can update that package in the build repository.
    print('----- Copy hook scripts to repositories')
    for hook in config.hook_configs:
        
        # Create the hook script from the template
        generated_hook_script = _SCRIPT_DIR.joinpath('post-receive')
        if os.path.isfile(str(generated_hook_script)):
            os.remove(str(generated_hook_script))

        replacement_dict = {
            '@JENKINS_URL@' : config.jenkins_account_info.url,
            '@JENKINS_USER@' : config.jenkins_account_info.user,
            '@JENKINS_PASSWORD@' : config.jenkins_account_info.password,
            '@JENKINS_JOB_NAME@' : setup.get_job_name(hook.jenkins_job_basename),
            '@CPF_PACKAGE@' : hook.buildjob_package_arg
        }
        machines_setup.configure_file(script_template, generated_hook_script, replacement_dict)

        # copy the script to the repository
        dest_file = hook.hook_dir.joinpath(generated_hook_script.name)
        connection = connections.get_connection(hook.machine_id)
        if connection.info.is_windows_machine():
            # If this happens, we need to generalize CPFMachines.fileutil.copy_textfile_from_local_to_linux()
            # and let it handle all cases of line ending transitions.
            raise Exception("This script needs to be extended to support windows repository machines.")
        
        fileutil.copy_textfile_from_local_to_linux(connection, generated_hook_script, dest_file)
        fileutil.make_remote_file_executable(connection, dest_file)

        # clean up the script
        os.remove(generated_hook_script)



if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
