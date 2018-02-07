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

import addJenkinsJob
import setup_docker_container_with_cpf_jobs

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

_POST_RECEIVE_HOOK_TEMPLATE = 'post-receive.in'


def main():
    """
    Entry of the script.
    """

    # read configuration
    config_file = sys.argv[1]
    config_values = _read_config_file(config_file)
    jenkins_url = config_values['JenkinsUrl']
    jenkins_user = config_values['JenkinsUser']
    jenkins_password = config_values['JenkinsPassword']
    jenkins_job_base_name = config_values['JenkinsJobBasename']
    package_repo_target_directories = config_values['CPFPackageRepoHookDirectories']

    script_template = _SCRIPT_DIR + '/post-receive.in'

    # Configure one hook for each given package.
    # The hook needs to tell the buildjob which package was changed,
    # so the job can update that package in the build repository.
    temp_files = ['']
    for package, hook_directory in package_repo_target_directories.items():
        replacement_dict = {
            '@JENKINS_URL@' : jenkins_url,
            '@JENKINS_USER@' : jenkins_user,
            '@JENKINS_PASSWORD@' : jenkins_password,
            '@JENKINS_JOB_NAME@' : setup_docker_container_with_cpf_jobs.get_job_name(jenkins_job_base_name),
            '@CPF_PACKAGE@' : package
        }
        temp_script = _SCRIPT_DIR + '/post-receive_' + package
        temp_files.append(temp_script)
        addJenkinsJob.configure_file(script_template, temp_script, replacement_dict)

        # copy the file to the repository
        dest_file = hook_directory + '/post-receive'
        _scp_copy_file(temp_script, dest_file)
        _make_remote_file_executable(dest_file)

        # clean up the script
        os.remove(temp_script)


def _read_config_file(config_file):
    print('----- Read configuration file ' + config_file)
    with open(config_file) as file:
        data = json.load(file)
    pprint.pprint(data)
    return data


def _scp_copy_file(source, dest):
    """
    Runs the scp command for the given pathes.
    """
    _run_command('scp ' + source + ' ' + dest)


def _make_remote_file_executable(remote_file):
    """
    Runs the chmod +x command for the file over ssh.
    """
    machine, path = remote_file.split(':')
    _run_command('ssh ' + machine + ' "chmod +x ' + path + '"' )


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
    sys.exit(main())
