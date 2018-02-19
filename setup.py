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
        configure_job_config_file(abs_xml_file_path, job_name, cpf_job_config.repository, _JENKINSJOB_REPOSITORY, webserver_host)

    # Extend the config values with the generated jobs.
    config_dict[config_data.KEY_JENKINS_CONFIG][config_data.KEY_JENKINS_JOB_CONFIG_FILES].update(job_dict)

    # Extend the config values with the scripts that need to
    # be approved to run the jenkinsfile.
    approved_script_signatures = [
        'new groovy.json.JsonSlurperClassic',
        'method groovy.json.JsonSlurperClassic parseText java.lang.String',
        'staticMethod org.codehaus.groovy.runtime.DefaultGroovyMethods matches java.lang.String java.util.regex.Pattern',
        'new java.lang.Exception java.lang.String',
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
    _configure_file(_TEMPLATE_FILE, xml_file_path, {
        '$JOB_NAME' : job_name,
        '$JENKINSFILE_TAG_OR_BRANCH' : tag_or_branch,
        '$BUILD_REPOSITORY' : build_repository_address,
        '$JENKINSJOB_REPOSITORY' : jenkinsjob_repository_address,
        '$WEBSERVER_HOST' : webserver_host,
    })


def _configure_file(source_file, dest_file, replacement_dictionary):
    """
    Searches in sourceFile for the keys in replacementDictionary, replaces them
    with the values and writes the result to destFile.
    """
    # Open target file
    config_file = io.open(dest_file, 'w')

    # Read the lines from the template, substitute the values, and write to the new config file
    for line in io.open(source_file, 'r'):
        for key, value in replacement_dictionary.items():
            line = line.replace(key, value)
        config_file.write(line)

    # Close target file
    config_file.close()


def _run_command(command, print_output=False, print_command=False, ignore_return_code=False):
    """
    Runs the given command and returns its standard output.
    The function throws if the command fails. In this case the output is always printed.

    Problems:
    This fails to return the complete output of "docker logs jenkins-master"
    However when print_output is set to true, it prints everything on the command line.
    """
    working_dir = os.getcwd()
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        cwd=working_dir)

    # print output as soon as it is generated.
    output = ''
    lines_iterator = iter(process.stdout.readline, b"")
    while process.poll() is None:
        for line in lines_iterator:
            nline = line.rstrip()
            line_string = nline.decode("utf-8")
            output += line_string + "\r\n"
            if print_output:
                print(line_string, end="\r\n", flush=True) # yield line

    out, err = process.communicate()
    retcode = process.returncode

    if print_command:
        output = command + '\n'

    # the iso codec helped to fix a problem with the output when sshing on the windows container.
    err_output = err.decode("ISO-8859-1")

    if print_output:
        print(output)
        print(err_output)

    if not ignore_return_code and retcode != 0:
        if not print_output:                         # always print the output in case of an error
            print(output)
            print(err_output)
        error = (
            'Command "{0}" executed in directory "{1}" returned error code {2}.'
            ).format(command, working_dir, str(retcode))
        raise Exception(error)

    return output

if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
