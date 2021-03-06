#!/usr/bin/env python3

import shutil
import os
import io
import sys

from . import setup

# locations
_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


def add_cpf_job(job_base_name, jenkins_directory, build_repository_address, jenkinsjob_repository_address ):
    """
    This function adds a CMakeProjectFramework build-job with name <job_name>-<version>
    to the jenkins instance that used jenkins_directory as working directory.
    If the job already exists, it will be overwritten.
    """
    # remove the existing job
    job_name = setup.get_job_name(job_base_name)
    job_dir = _get_job_dir(jenkins_directory, job_name)
    _clear_directory(job_dir)

    # add a new config.xml file
    setup.configure_job_config_file(job_dir, job_name, build_repository_address, jenkinsjob_repository_address)


def _get_job_dir(jenkins_directory, job_name):
    """
    Returns the directory for a job configuration file relative
    to the jenkins home directory.
    """
    return jenkins_directory + '/jobs/' + job_name


def _clear_directory(directory):
    """
    This functions deletes the given directory and all its content and
    recreates it.

    The function is duplicated in the CPFMachines
    setupDockerContainer.py file.
    """
    if os.path.isdir(directory):
        shutil.rmtree(directory)
    os.makedirs(directory)

