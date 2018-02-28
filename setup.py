#!/usr/bin/env python3

"""
This script runs the CPFMachines setupdDockerContainer.py script, 
but adds additional CPFJenkinsjob jobs.

The script takes a .json config file for the machine setup, which can
contain an additional dictionary for defineing CMakeProjectFramework jobs.


{
  ...
  "CPFJobs" : {
    "MyCPFProjectJob" : "ssh://me@repository_machine:/share/MyRepo.git"
  },
  ...
}

"""

import sys
import os
import json
import shutil
import pprint
import io

from ..CPFMachines import setup
from ..CPFMachines import config_data

from . import cpfjenkinsjob_version
from . import cpf_job_config

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))



# The address of the official CPFJenkinsjob repository.
# Is it good enough to have this hardcoded here?
_JENKINSJOB_REPOSITORY = 'ssh://admin@datenbunker/share/GitRepositories/CPFJenkinsjob.git'
_TEMPLATE_FILE = _SCRIPT_DIR + '/config.xml.in'


def main(config_file):

    if not os.path.isabs(config_file):
        config_file = os.getcwd() + '/' + config_file

    # read .json config file
    config_dict = config_data.read_json_file(config_file)
    config = config_data.ConfigData(config_dict)
    config_file_dir = os.path.dirname(config_file)
    temp_config_file = 'TempConfig.json'
    abs_temp_config_file = config_file_dir + '/' + temp_config_file

    # create the job .xml files that are used by jenkins.
    temp_dir = 'temp'
    abs_temp_dir = config_file_dir + '/' + temp_dir
    if not os.path.exists(abs_temp_dir):
        os.makedirs(abs_temp_dir)

    job_dict = {}
    for cpf_job_config in config.jenkins_config.cpf_jobs:
        job_name = get_job_name(cpf_job_config.job_name)
        xml_file = job_name + '.xml'
        xml_file_path = temp_dir + '/' + xml_file
        abs_xml_file_path = abs_temp_dir + '/' + xml_file
        job_dict[job_name] = xml_file_path
        webserver_host = config.get_host_info(config.web_server_host_config.machine_id).host_name
        _configure_job_config_file(abs_xml_file_path, job_name, cpf_job_config.repository, _JENKINSJOB_REPOSITORY, webserver_host)

    # Extend the config values with the generated jobs.
    config_dict[config_data.KEY_JENKINS_CONFIG][config_data.KEY_JENKINS_JOB_CONFIG_FILES].update(job_dict)

    # Extend the config values with the scripts that need to
    # be approved to run the jenkinsfile.
    approved_script_signatures = [
        'new groovy.json.JsonSlurperClassic',
        'method groovy.json.JsonSlurperClassic parseText java.lang.String',
        'staticMethod org.codehaus.groovy.runtime.DefaultGroovyMethods matches java.lang.String java.util.regex.Pattern',
        'new java.lang.Exception java.lang.String',
        'method java.lang.String join java.lang.CharSequence java.lang.CharSequence[]'
    ]
    config_dict[config_data.KEY_JENKINS_CONFIG][config_data.KEY_JENKINS_APPROVED_SCRIPT_SIGNATURES].extend(approved_script_signatures)
    
    # Write extended config to a temporary config file for the setup script from CPFMachines.
    with open(abs_temp_config_file, 'w') as outfile:
        json.dump(config_dict, outfile)

    # run the setup script from CPFMachines
    setup.main(temp_config_file)

    # clean up the temporary files
    shutil.rmtree(abs_temp_dir)
    os.remove(abs_temp_config_file)


def get_job_name(job_base_name):
    """
    Add the version to the base name.
    """
    return job_base_name + '-' + cpfjenkinsjob_version.CPFJENKINSJOB_VERSION


def configure_job_config_file(xml_file_path, job_name, build_repository_address, jenkinsjob_repository_address, webserver_host):
    """
    Fills in the blanks in the config file and copies it to the given job
    directory.
    """
    # TODO this should be the version tag once automatic versioning for CPFJenkinsjob works.
    tag_or_branch = 'master'
    setup.configure_file(_TEMPLATE_FILE, xml_file_path, {
        '$JOB_NAME' : job_name,
        '$JENKINSFILE_TAG_OR_BRANCH' : tag_or_branch,
        '$BUILD_REPOSITORY' : build_repository_address,
        '$JENKINSJOB_REPOSITORY' : jenkinsjob_repository_address,
        '$WEBSERVER_HOST' : webserver_host,
    })


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
