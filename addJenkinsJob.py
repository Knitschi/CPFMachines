#!/usr/bin/env python3

import shutil
import os
import io
import sys


# locations
_scriptDir = os.path.dirname(os.path.realpath(__file__))
_templateFile = _scriptDir + '/config.xml.in'

_jenkinsfileVersion='0.0.0'     # todo: get version from repo.


def addCppCodeBaseJob( jobName, repositoryAddress, jenkinsDirectory):
    """
    This function adds a CppCodeBase build-job with name <jobName>-<version> to the jenkins instance
    that used jenkinsDirectory as working directory. If the job already exists, it will be overwritten.
    """
    # remove the existing job
    jobDir = _getJobDir(jenkinsDirectory, jobName)
    _clearDirectory(jobDir)

    # add a new config.xml file
    _configureJobConifgFile(jobDir, jobName, repositoryAddress)


def _getJobDir( jenkinsDirectory, jobName):
    return jenkinsDirectory + '/jobs/' + jobName


def _configureJobConifgFile( destDir, jobName, repositoryAddress ):
    """
    Fills in the blanks in the config file and copies it to the given job directory.
    """
    _configureFile(_templateFile,destDir + '/config.xml', { 
        '$JOB_NAME' : jobName,
        '$JENKINSFILE_VERSION' : _jenkinsfileVersion,
        '$BUILD_REPOSITORY' : repositoryAddress
    } )


def _clearDirectory(directory):
    """
    This functions deletes the given directory and all its content and recreates it.

    The function is duplicated in the CppCodeBaseMachines setupDockerContainer.py file.
    """
    if(os.path.isdir(directory)):
        shutil.rmtree(directory)
    os.makedirs(directory)


def _configureFile( sourceFile, destFile, replacementDictionary ):
    """
    Searches in sourceFile for the keys in replacementDictionary, replaces them
    with the values and writes the result to destFile.

    The function is duplicated in the CppCodeBaseMachines setupDockerContainer.py file.
    """
    # Open target file
    configFile = io.open( destFile, 'w')

    # Read the lines from the template, substitute the values, and write to the new config file
    for line in io.open( sourceFile, 'r'):
        for key, value in replacementDictionary.items():
            line = line.replace( key, value)
        configFile.write(line)

    # Close target file
    configFile.close()
