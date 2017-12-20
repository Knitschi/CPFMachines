#!/usr/bin/env python3

"""
This script runs the CppCodeBaseMachines setupdDockerContainer.py script, 
but adds additional CppCodeBaseJenkinsjob jobs.

The script takes a .json config file for the machine setup, which can
contain an additional dictionary for defineing CppCodeBase jobs.


{
  ...
  "CppCodeBaseJobs" : {
    "MyCppCodeBaseJob" : "ssh://me@repository_machine:/share/MyRepo.git"
  },
  ...
}

"""

import sys
import os
import json
import shutil

from ..CppCodeBaseMachines import setupDockerContainer

from . import CppCodeBaseJenkinsjob_version

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

# The address of the official CppCodeBaseJenkinsjob repository.
# Is it good enough to have this hardcoded here?
_JENKINSJOB_REPOSITORY = 'ssh://admin@datenbunker/share/GitRepositories/CppCodeBaseJenkinsjob.git'


def main(config_file):

    # read .json config file
    config_values = _readconfig_file(config_file)
    config_file_dir = os.path.dirname(config_file)
    temp_config_file = 'TempConfig.json'
    abs_temp_config_file = config_file_dir + '/' + temp_config_file

    # create the job .xml files that are used by jenkins.
    ccb_jobs_dict = config_values['CppCodeBaseJobs']
    temp_dir = 'temp'
    abs_temp_dir = config_file_dir + '/' + temp_dir
    os.makedirs(abs_temp_dir)
    job_dict = {}
    for job_base_name, build_repository in ccb_jobs_dict.items():
        xml_file = job_name + '.xml'
        xml_file_path = temp_dir + '/' + xml_file
        abs_xml_file_path = abs_temp_dir + '/' + xml_file
        job_dict[get_job_name(job_base_name)] = xml_file_path
        configure_job_config_file(abs_xml_file_path, job_name, build_repository, _JENKINSJOB_REPOSITORY)

    # Extend the config values with the generated jobs.
    config_values['JenkinsJobConfigFiles'].update(job_dict)

    # Extend the config values with the scripts that need to
    # be approved to run the jenkinsfile.
    approved_scripts = [
        "new groovy.json.JsonSlurperClassic",
        "method groovy.json.JsonSlurperClassic parseText java.lang.String"
    ]
    config_values['JenkinsApprovedScripts'].extend(approved_scripts)
    
    # Write extended config to a temporary config file for the setup script from CppCodeBaseMachines.
    with open(abs_temp_config_file, 'w') as outfile:
        json.dump(config_values, outfile)

    # run the setup script from CppCodeBaseMachines
    CppCodeBaseMachines.main(temp_config_file)

    # clean up the temporary files
    shutil.rmtree(abs_temp_dir)
    os.remove(abs_temp_config_file)


def get_job_name(job_base_name):
    """
    Add the version to the base name.
    """
    return job_base_name + '-' + CppCodeBaseJenkinsjob_version.PACKAGE_VERSION


def configure_job_config_file(xml_file_path, job_name, build_repository_address, jenkinsjob_repository_address):
    """
    Fills in the blanks in the config file and copies it to the given job
    directory.
    """
    # TODO this should be the version tag once automatic versioning for CppCodeBaseJenkinsjob works.
    tag_or_branch = 'master'
    _configure_file(_TEMPLATE_FILE, xml_file_path, {
        '$JOB_NAME' : job_name,
        '$JENKINSFILE_TAG_OR_BRANCH' : tag_or_branch,
        '$BUILD_REPOSITORY' : build_repository_address,
        '$JENKINSJOB_REPOSITORY' : jenkinsjob_repository_address
    })


def _readconfig_file(config_file):
    print('----- Read configuration file ' + config_file)
    with open(config_file) as file:
        data = json.load(file)
    pprint.pprint(data)
    return data


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
