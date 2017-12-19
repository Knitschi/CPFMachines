#!/usr/bin/env python3

import shutil
import os
import io
import sys

from . import CppCodeBaseJenkinsjob_version

# locations
_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
_TEMPLATE_FILE = _SCRIPT_DIR + '/config.xml.in'


def add_cppcodebase_job(job_base_name, jenkins_directory, build_repository_address, jenkinsjob_repository_address ):
    """
    This function adds a CppCodeBase build-job with name <job_name>-<version>
    to the jenkins instance that used jenkins_directory as working directory.
    If the job already exists, it will be overwritten.
    """
    # remove the existing job
    job_name = get_job_name(job_base_name)
    job_dir = _get_job_dir(jenkins_directory, job_name)
    _clear_directory(job_dir)

    # add a new config.xml file
    _configure_job_config_file(job_dir, job_name, build_repository_address, jenkinsjob_repository_address)


def get_job_name(job_base_name):
    """
    Add the version to the base name.
    """
    return job_base_name + '-' + CppCodeBaseJenkinsjob_version.PACKAGE_VERSION


def configure_file(source_file, dest_file, replacement_dictionary):
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


def _get_job_dir(jenkins_directory, job_name):
    """
    Returns the directory for a job configuration file relative
    to the jenkins home directory.
    """
    return jenkins_directory + '/jobs/' + job_name


def _configure_job_config_file(dest_dir, job_name, build_repository_address, jenkinsjob_repository_address):
    """
    Fills in the blanks in the config file and copies it to the given job
    directory.
    """
    # TODO this should be the version tag once automatic versioning for CppCodeBaseJenkinsjob works.
    tag_or_branch = 'master'
    configure_file(_TEMPLATE_FILE, dest_dir + '/config.xml', {
        '$JOB_NAME' : job_name,
        '$JENKINSFILE_TAG_OR_BRANCH' : tag_or_branch,
        '$BUILD_REPOSITORY' : build_repository_address,
        '$JENKINSJOB_REPOSITORY' : jenkinsjob_repository_address
    })


def _clear_directory(directory):
    """
    This functions deletes the given directory and all its content and
    recreates it.

    The function is duplicated in the CppCodeBaseMachines
    setupDockerContainer.py file.
    """
    if os.path.isdir(directory):
        shutil.rmtree(directory)
    os.makedirs(directory)

