#!/usr/bin/env python3

import shutil
import os

# locations
_scriptDir = os.path.dirname(os.path.realpath(__file__))
_templateFile = _scriptDir + '/config.xml.in'

_jenkinsfileVersion='0.0.0'     # todo: get version from repo.

_placeholderStrings = [ '$JOB_NAME', , ]

def addCppCodeBaseJob( jobName, repositoryAddress, jenkinsDirectory):
    """
    This function adds a CppCodeBase build-job with name <jobName>-<version> to the jenkins instance
    that used jenkinsDirectory as working directory. If the job already exists, it will be overwritten.
    """
    # remove the existing job
    jobDir = jenkinsDirectory + '/jobs/' + jobName
    shutil.rmtree(jobDir)
    os.makedirs(jobDir)

    # add a new config.xml file
    _configureJobConifgFile(jobDir, jobName, repositoryAddress)


def _configureJobConifgFile( destDir, jobName, repositoryAddress ):
    """
    Fills in the blanks in the config file and copies it to the given job directory.
    """
    # Open target file
    configFile = io.open( destDir + '/config.xml', 'w')

    # Read the lines from the template, substitute the values, and write to the new config file
    for line in io.open(_templateFile, 'r'):
        line = line.replace( '$JOB_NAME', jobName )
        line = line.replace( '$JENKINSFILE_VERSION', _jenkinsfileVersion )
        line = line.replace( '$BUILD_REPOSITORY', repositoryAddress)
        configFile.write(line)

    # Close target file
    configFile.close()



