#!/usr/bin/env python3

# This script removes and adds and starts all docker container of the CppCodeBase project infrastructure.
# Arguments:
# 1. - The path to a configuration json file. (An empty file can be generated with the createEmptyConfigFiles.py script)



import os
import sys
import socket
import distutils.dir_util
import subprocess
import shutil
import io
import json
import pprint
import getpass
import requests
import time
import urllib

_scriptDir = os.path.dirname(os.path.realpath(__file__))

# Constants
# The version of the jenkins CI server that is installed on the jenkins-master machine.
_JENKINS_VERSION = '2.89.1'
# The sha256 checksum of the jenkins.war package of the given jenkins version.
_JENKINS_SHA256 = 'f9f363959042fce1615ada81ae812e08d79075218c398ed28e68e1302c4b272f'

# container
# The name of the container that hosts the web-server that hosts the documentation of a
# CppCodeBase project.
_WEBSERVER_CONTAINER = 'ccb-web-server'
# The IP address of the _WEBSERVER_CONTAINER in the docker network.
_WEBSERVER_CONTAINERIP = '172.19.0.2'

# The name of the docker container that runs the jenkins CI server.
_JENINS_MASTER_CONTAINER = 'jenkins-master'
# The IP address of the _JENINS_MASTER_CONTAINER in the docker network.
_JENINS_MASTER_CONTAINERIP = '172.19.0.3'

# The base name of the linux based docker containers that are used as build-slaves.
# The name is also used for the node in the jenkins configuration.
# The final name adds '-<index>' to the base name.
_LINUX_SLAVE_BASE_NAME = 'jenkins-slave-linux'
# The ip address of the first and for now only linux slave container.
_JENKINS_LINUX_SLAVE_CONTAINER_IP = '172.19.0.4'

# docker network
_DOCKER_NETWORK_NAME = 'CppCodeBaseNetwork'


# derived constants
# In the future there may be multiple slaves so the script provides the _LINUX_SLAVE_INDEX to
# destinguish between them.
_LINUX_SLAVE_INDEX = 0
_WINDOWS_SLAVE_INDEX = 0
_FULL_LINUX_JENKINS_SLAVE_NAME = _LINUX_SLAVE_BASE_NAME + '-' + str(_LINUX_SLAVE_INDEX)
_FULL_WINDOWS_JENKINS_SLAVE_NAME = 'jenkins-slave-windows-' + str(_WINDOWS_SLAVE_INDEX)


# Files
_PUBLIC_KEY_FILE_POSTFIX = '_ssh_key.rsa.pub'
_CREATEKEYPAIR_SCRIPT = 'createSSHKeyFilePair.sh'
_ADDKNOWNHOST_SCRIPT = 'addKnownSSHHost.sh'
_ADDAUTHORIZEDKEYSBITWISESSH_SCRIPT = 'addAuthorizedBitwiseSSHKey.bat'

# directories on jenkins-master
# This is the location of the jenkins configuration files on the jenkins-master.
_JENKINS_HOME_JENKINS_MASTER_CONTAINER = '/var/jenkins_home'
# This is the location of the html-share volume on the jenkins master.
_HTML_SHARE_JENKINS_MASTER = _JENKINS_HOME_JENKINS_MASTER_CONTAINER + '/html'

# directories on jenkins-slave-linux
_JENKINS_HOME_JENKINS_SLAVE_CONTAINER = '/home/jenkins'

# directories on ccb-web-server
_HTML_SHARE_WEB_SERVER_CONTAINER = '/var/www/html'


def clearDirectory(directory):
    """
    This functions deletes the given directory and all its content and recreates it.
    """
    if(os.path.isdir(directory)):
        shutil.rmtree(directory)
    os.makedirs(directory)


def configureFile(sourceFile, destFile, replacementDictionary):
    """
    Searches in sourceFile for the keys in replacementDictionary, replaces them
    with the values and writes the result to destFile.
    """
    # Open target file
    configFile = io.open(destFile, 'w')

    # Read the lines from the template, substitute the values, and write to the new config file
    for line in io.open(sourceFile, 'r'):
        for key, value in replacementDictionary.items():
            line = line.replace(key, value)
        configFile.write(line)

    # Close target file
    configFile.close()


def main():
    # read configuration
    configFile = sys.argv[1]
    configValues = _readConfigFile(configFile)

    # Get some passwords at the beginning, to prevent interuptions in the middle when the user may
    # be doing something else because of long execution times.
    # Get the password for the windows slave, because we need it to update the bitwise ssh server.
    jenkinsSlaveMachineWindowsPassword = _getMissingPassword(
        configValues,
        'BuildSlaveWindowsMachinePassword',
        "Enter the password for the windows account of user " +
        configValues['BuildSlaveWindowsMachineUser'] +
        ' on ' + configValues['BuildSlaveWindowsMachine'] + ': '
        )
    # Get the password for the jenkins admin user.
    jenkinsAdminPassword = _getMissingPassword(
        configValues,
        'JenkinsAdminUserPassword',
        "Enter the password for the jenkins account of user " +
        configValues['JenkinsAdminUser'] + ': '
        )


    # prepare environment
    print('----- Cleanup existing container')

    _clearDocker()
    clearDirectory(configValues['HostJenkinsMasterShare'])
    # we do not clear this to preserve the accumulated web content.
    _guaranteeDirectoryExists(configValues['HostHTMLShare'])
    _createDockerNetwork(_DOCKER_NETWORK_NAME)

    # build container
    _buildAndStartJenkinsMaster(configValues)
    # The document server must be started before the jenkins slave is started because mounting
    # the shared volume here sets the owner of the share to root an only the jenkins container
    # can set it to jenkins.
    _buildAndStartWebServer(configValues)
    _buildAndStartJenkinsLinuxSlave()

    # setup ssh accesses used by jenkins-master
    _createRSAKeyFilePairOnContainer(
        _JENINS_MASTER_CONTAINER,
        _JENKINS_HOME_JENKINS_MASTER_CONTAINER)
    _grantContainerSSHAccessToRepository(
        _JENINS_MASTER_CONTAINER,
        _JENKINS_HOME_JENKINS_MASTER_CONTAINER,
        configValues)
    _grantJenkinsMasterSSHAccessToJenkinsLinuxSlave(configValues)
    _grantJenkinsMasterSSHAccessToJenkinsWindowsSlave(
        configValues,
        jenkinsSlaveMachineWindowsPassword)
    _grantJenkinsMasterSSHAccessToWebServer(configValues)
    # setup ssh accesses used by jenkins-slave-linux
    _createRSAKeyFilePairOnContainer(
        _FULL_LINUX_JENKINS_SLAVE_NAME,
        _JENKINS_HOME_JENKINS_SLAVE_CONTAINER)
    _grantContainerSSHAccessToRepository(
        _FULL_LINUX_JENKINS_SLAVE_NAME,
        _JENKINS_HOME_JENKINS_SLAVE_CONTAINER, configValues)

    _configureJenkinsMaster(configValues, configFile, jenkinsAdminPassword)

    print('Successfully startet jenkins master, build slaves and the documentation server.')


def devMessage(text):
    print('--------------- ' + str(text))


def _readConfigFile(configFile):
    print('----- Read configuration file ' + configFile)
    with open(configFile) as file:
        data = json.load(file)
    pprint.pprint(data)
    return data

def _getMissingPassword(configValues, configKeyPassword, promptMessage):
    password = configValues[configKeyPassword]
    if not password:
        password = getpass.getpass(promptMessage)
    return password

def _clearDocker():
    _stubbornlyRemoveContainer(_WEBSERVER_CONTAINER)
    _stubbornlyRemoveContainer(_JENINS_MASTER_CONTAINER)
    _stubbornlyRemoveContainer(_FULL_LINUX_JENKINS_SLAVE_NAME)

    _removeDockerNetwork(_DOCKER_NETWORK_NAME)


def _stubbornlyRemoveContainer(container):
    """
    Removes a given docker container even if it is running.
    If the container does not exist, the function does nothing.
    """
    runningContainer = _getRunningDockerContainer()

    if container in runningContainer:
        _stopDockerContainer(container)

    allContainer = _getAllDockerContainer()
    if container in allContainer:
        _removeContainer(container)


def _getRunningDockerContainer():
    return _run_commandToGetList("docker ps --format '{{.Names}}'")


def _getAllDockerContainer():
    return _run_commandToGetList("docker ps -a --format '{{.Names}}'")


def _run_commandToGetList(command):
    """
    The function assumes that the ouput of comand is a list with one element per line.
    It returns that list as a python list.
    """
    output = _run_command(command)
    return output.splitlines()


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


def _stopDockerContainer(container):
    _run_command('docker stop ' + container)


def _startDockerContainer(container):
    _run_command('docker start ' + container)


def _removeContainer(container):
    """
    This removes a given docker container and will fail if the container is running.
    """
    _run_command('docker rm -f ' + container)


def _removeDockerNetwork(network):
    networkLines = _run_commandToGetList('docker network ls')
    networks = []
    for line in networkLines:
        columns = line.split()
        networks.append(columns[1])

    if network in networks:
        _run_command('docker network rm ' + _DOCKER_NETWORK_NAME)


def _guaranteeDirectoryExists(directory):
    if not os.path.isdir(directory):
        os.makedirs(directory)


def _createDockerNetwork(network):
    _run_command('docker network create --subnet=172.19.0.0/16 ' + network)


def _buildAndStartJenkinsMaster(configValues):
    print("----- Build and start the docker MASTER container " + _JENINS_MASTER_CONTAINER)

    # Create the jenkins base image. This is required to customize the jenkins version.
    jenkinsBaseImage = 'jenkins-image-' + _JENKINS_VERSION
    _buildDockerImage(
        jenkinsBaseImage,
        _scriptDir + '/DockerfileJenkinsBase/Dockerfile',
        _scriptDir + '/DockerfileJenkinsBase',
        ['JENKINS_VERSION=' + _JENKINS_VERSION, 'JENKINS_SHA=' + _JENKINS_SHA256])

    # Create the container image
    containerImage = _JENINS_MASTER_CONTAINER + '-image'
    _buildDockerImage(
        containerImage,
        _scriptDir + '/DockerfileJenkinsMaster',
        _scriptDir,
        ['JENKINS_BASE_IMAGE=' + jenkinsBaseImage])

    # Start the container
    # --env JAVA_OPTS="-Djenkins.install.runSetupWizard=false"
    # The jenkins master and its slaves communicate over the bridge network.
    # This means the master and the slaves must be on the same host.
    # This should later be upgraded to a swarm.

    # When the user already has a jenkins configuration
    # we add an option that prevents the first startup wizard from popping up.
    noSetupWizardOption = ''
    if not configValues['UseUnconfiguredJenkinsMaster']:
        noSetupWizardOption = '--env JAVA_OPTS="-Djenkins.install.runSetupWizard=false" '

    command = (
        'docker run '
        '--detach '
        # This makes the jenkins home directory accessible on the host. This eases debugging.
        '--volume ' + configValues['HostJenkinsMasterShare'] + ':' + _JENKINS_HOME_JENKINS_MASTER_CONTAINER + ' '
        + noSetupWizardOption +
        # The jenkins webinterface is available under this port.
        '--publish 8080:8080 '
        # Only needed for hnlp slaves. We leave it here in case we need hnlp slave later.
        #'--publish 50000:50000 '
        '--name ' + _JENINS_MASTER_CONTAINER + ' '
        '--net ' + _DOCKER_NETWORK_NAME + ' '
        '--ip ' + _JENINS_MASTER_CONTAINERIP + ' '
        + containerImage
    )
    _run_command(command, print_output=True)

    # add global gitconfig after mounting the workspace volume, otherwise is gets deleted.
    _run_commandInContainer(
        _JENINS_MASTER_CONTAINER,
        'git config --global user.email not@valid.org')
    _run_commandInContainer(
        _JENINS_MASTER_CONTAINER,
        'git config --global user.name jenkins')


def _buildDockerImage(imageName, dockerFile, buildContextDirectory, buildArgs):
    buildArgsString = ''
    for arg in buildArgs:
        buildArgsString += ' --build-arg ' + arg

    command = (
        'docker build' + buildArgsString + ' -t ' + imageName +
        ' -f ' + dockerFile + ' ' + buildContextDirectory
    )
    _run_command(command, True)


def _run_commandInContainer(container, command, user=None):
    userOption = ''
    if user:
        userOption = '--user ' + user + ':' + user + ' '
    command = 'docker exec ' + userOption + container + ' ' + command
    print(command)
    return _run_command(command)


def _buildAndStartWebServer(configValues):
    print("----- Build and start the web-server container " + _WEBSERVER_CONTAINER)

    containerImage = _WEBSERVER_CONTAINER + '-image'
    _buildDockerImage(containerImage, _scriptDir + '/DockerfileCcbWebServer', _scriptDir, [])

    command = (
        'docker run '
        '--detach '
        '--publish 80:80 '      # The web-page is reached under port 80
        '--volume ' + configValues['HostHTMLShare'] + ':' + _HTML_SHARE_WEB_SERVER_CONTAINER + ' '
        '--name ' + _WEBSERVER_CONTAINER + ' '
        '--net ' + _DOCKER_NETWORK_NAME + ' '
        '--ip ' + _WEBSERVER_CONTAINERIP + ' '
        + containerImage
    )
    _run_command(command, print_output=True)

    # copy the doxyserach.cgi to the html share
    _run_commandInContainer(
        _WEBSERVER_CONTAINER,
        'rm -fr ' + _HTML_SHARE_WEB_SERVER_CONTAINER + '/cgi-bin',
        'root')
    _run_commandInContainer(
        _WEBSERVER_CONTAINER,
        'mkdir ' + _HTML_SHARE_WEB_SERVER_CONTAINER + '/cgi-bin',
        'root')
    _run_commandInContainer(
        _WEBSERVER_CONTAINER,
        'mkdir ' + _HTML_SHARE_WEB_SERVER_CONTAINER + '/cgi-bin/doxysearch.db',
        'root')
    _run_commandInContainer(
        _WEBSERVER_CONTAINER,
        'cp -r -f /usr/local/bin/doxysearch.cgi ' + _HTML_SHARE_WEB_SERVER_CONTAINER + '/cgi-bin',
        'root')


def _buildAndStartJenkinsLinuxSlave():
    # Start the container.
    print("----- Build and start the docker SLAVE container " + _FULL_LINUX_JENKINS_SLAVE_NAME)

    containerImage = _LINUX_SLAVE_BASE_NAME + '-image'
    _buildDockerImage(containerImage, _scriptDir + '/DockerfileJenkinsSlaveLinux', _scriptDir, [])

    command = (
        'docker run '
        '--detach '
        '--name ' + _FULL_LINUX_JENKINS_SLAVE_NAME + ' '
        '--net ' + _DOCKER_NETWORK_NAME + ' '
        '--ip ' + _JENKINS_LINUX_SLAVE_CONTAINER_IP + ' '
        + containerImage
    )
    _run_command(command, print_output=True)


def _createRSAKeyFilePairOnContainer(containerName, containerHomeDirectory):
    print(
        '----- Create SSH key file pair for container ' + containerName +
        ' in directory ' + containerHomeDirectory)

    # copy the scripts that does the job to the container
    _run_command(
        'docker cp ' + _scriptDir + '/' + _CREATEKEYPAIR_SCRIPT +
        ' ' + containerName + ':' + containerHomeDirectory + '/' + _CREATEKEYPAIR_SCRIPT)

    _run_command(
        'docker cp ' + _scriptDir + '/' + _ADDKNOWNHOST_SCRIPT +
        ' ' + containerName + ':' + containerHomeDirectory + '/' + _ADDKNOWNHOST_SCRIPT)

    # This will create the key-pair on the container.
    # We need to do this in the container or ssh will not accept the private key file.
    _run_commandInContainer(
        containerName,
        '/bin/bash ' + containerHomeDirectory + '/' + _CREATEKEYPAIR_SCRIPT + ' ' + containerName,
        'jenkins')


def _grantContainerSSHAccessToRepository(containerName, containerHomeDirectory, configValues):

    repositoryMachine = configValues['RepositoryMachineName']
    repositoryMachineUser = configValues['RepositoryMachineUser']
    repositoryMachineSSHDir = configValues['RepositoryMachineSSHDir']
    tempDirHost = configValues['HostTempDir']

    print(
        '----- Grant container ' + containerName +
        ' SSH access to the repository machine ' + repositoryMachine)
    # COPY AND REGISTER THE PUBLIC KEY WITH repositoryMachine
    # The connection is used to access the git repository
    # This requires access to the datenbunker.
    publicKeyFile = containerName + _PUBLIC_KEY_FILE_POSTFIX
    _guaranteeDirectoryExists(tempDirHost)
    fullTempPublicKeyFile = tempDirHost + '/' + publicKeyFile
    if os.path.isfile(fullTempPublicKeyFile):
        os.remove(fullTempPublicKeyFile) # delete previously copied key-files

    # Copy the public key from the jenkins jome directory to the
    # jenkins-workspace directory on the host
    _run_command((
        'docker cp {0}:{1}/{2} {3}'
        ).format(containerName, containerHomeDirectory, publicKeyFile, tempDirHost))

    # Then copy it to the repository machine
    _run_command((
        'scp {}/{} {}@{}.local:{}'
        ).format(
            tempDirHost,
            publicKeyFile,
            repositoryMachineUser,
            repositoryMachine,
            repositoryMachineSSHDir))

    # add the key file to authorized_keys
    authorizedKeysFile = repositoryMachineSSHDir + '/authorized_keys'
    # Remove previously appended public keys from the given container and append the
    # new public key to the authorized_keys file.
    # - print file without lines containing machine name string, then append new key to end of file
    command = (
        'ssh {0}@{1} "'
        'cat {2} | grep -v {3} >> {4}/keys_temp &&'
        'mv -f {4}/keys_temp {2} &&'
        'cat {4}/{5} >> {2}"'
    )
    command = command.format(
        repositoryMachineUser,
        repositoryMachine,
        authorizedKeysFile,
        containerName,
        repositoryMachineSSHDir,
        publicKeyFile)
    _run_command(command)

    # Add the repository machine as known host to prevent the authentication request on the first
    # connect
    _run_commandInContainer(
        containerName,
        '/bin/bash '+ containerHomeDirectory +'/' + _ADDKNOWNHOST_SCRIPT + ' ' +  repositoryMachine,
        'jenkins')


def _grantJenkinsMasterSSHAccessToJenkinsLinuxSlave(configValues):
    print('----- Grant '+_JENINS_MASTER_CONTAINER+' ssh access to '+_FULL_LINUX_JENKINS_SLAVE_NAME)
    publicKeyFile = _JENINS_MASTER_CONTAINER + _PUBLIC_KEY_FILE_POSTFIX

    # COPY AND REGISTER THE PUBLIC KEY WITH THE SLAVE
    # Jenkins handles linux slaves with an ssh connection.
    _run_command(
        'docker cp {0}/{1} {2}:{3}/.ssh/authorized_keys'.format(
            configValues['HostJenkinsMasterShare'],
            publicKeyFile,
            _FULL_LINUX_JENKINS_SLAVE_NAME,
            _JENKINS_HOME_JENKINS_SLAVE_CONTAINER))
    # Add slave as known host to prevent the authentication request on the first connect
    _addRemoteToKnownSSHHostsOfJenkinsMaster(_JENKINS_LINUX_SLAVE_CONTAINER_IP)


def _grantJenkinsMasterSSHAccessToJenkinsWindowsSlave(configValues, jenkinsSlaveMachineWindowsPassword):

    jenkinsWorkspaceHost = configValues['HostJenkinsMasterShare']
    jenkinsSlaveMachineWindows = configValues['BuildSlaveWindowsMachine']
    jenkinsSlaveMachineWindowsUser = configValues['BuildSlaveWindowsMachineUser']

    print((
        "----- Grant {0} ssh access to {1}"
        ).format(_JENINS_MASTER_CONTAINER, jenkinsSlaveMachineWindows))

    # configure the script for adding an authorized key to the bitwise ssh server on the
    # windows machine
    authorizedKeysScript = 'updateAuthorizedKeysBitvise.bat'
    fullAuthorizedKeysScript = _scriptDir + '/' + authorizedKeysScript
    publicKeyFile = jenkinsWorkspaceHost + '/' + _JENINS_MASTER_CONTAINER + _PUBLIC_KEY_FILE_POSTFIX
    publicKey = _readFileContent(publicKeyFile)
    publicKey = publicKey.replace('\n', '').replace('\r', '')  # remove the line end from the key
    configureFile(fullAuthorizedKeysScript + '.in', fullAuthorizedKeysScript, {
        '@PUBLIC_KEY@' : publicKey,
        '@JENKINS_MASTER_CONTAINER@' : _JENINS_MASTER_CONTAINER,
        '@SLAVE_MACHINE_USER@' : jenkinsSlaveMachineWindowsUser,
    })

    # copy the script for to the windows slave machine
    sshDir = 'C:/Users/' + jenkinsSlaveMachineWindowsUser + '/.ssh'
    copyScriptCommand = 'scp {0} {1}@{2}:{3}'.format(
        fullAuthorizedKeysScript,
        jenkinsSlaveMachineWindowsUser,
        jenkinsSlaveMachineWindows,
        sshDir)
    _run_command(copyScriptCommand)

    # call the script
    fullScriptPathOnSlave = sshDir + '/' + authorizedKeysScript
    callScriptCommand = (
        'ssh {0}@{1} "{2} {3}"'
    ).format(
        jenkinsSlaveMachineWindowsUser,
        jenkinsSlaveMachineWindows,
        fullScriptPathOnSlave,
        jenkinsSlaveMachineWindowsPassword,
    )
    try:
        _run_command(callScriptCommand)
    except Exception as err:
        print(
            "Error: Updating the authorized ssh keys on "
            + jenkinsSlaveMachineWindows + " failed. Was the password correct?")
        raise err

    # clean up the generated scripts because of the included password
    os.remove(fullAuthorizedKeysScript)
    fullScriptPathOnSlaveBackslash = (
        'C:\\\\Users\\\\' + jenkinsSlaveMachineWindowsUser + '\\\\' + authorizedKeysScript)

    # Add the slave to the known hosts
    _addRemoteToKnownSSHHostsOfJenkinsMaster(jenkinsSlaveMachineWindows)


def _readFileContent(filename):
    with open(filename) as f:
        return f.read()


def _addRemoteToKnownSSHHostsOfJenkinsMaster(remoteMachine):
    """
    remoteMachine can be an IP or machine name.
    """
    runScriptCommand = (
        '/bin/bash ' + _JENKINS_HOME_JENKINS_MASTER_CONTAINER +
        '/' + _ADDKNOWNHOST_SCRIPT + ' ' + remoteMachine)
    _run_commandInContainer(
        _JENINS_MASTER_CONTAINER,
        runScriptCommand,
        'jenkins')


def _grantJenkinsMasterSSHAccessToWebServer(configValues):

    jenkinsWorkspaceHost = configValues['HostJenkinsMasterShare']

    authorizedKeysFile = '/root/.ssh/authorized_keys'
    publicKeyFile = _JENINS_MASTER_CONTAINER + _PUBLIC_KEY_FILE_POSTFIX

    _run_command('docker cp {0}/{1} {2}:{3}'.format(
        jenkinsWorkspaceHost,
        publicKeyFile,
        _WEBSERVER_CONTAINER,
        authorizedKeysFile))
    _run_commandInContainer(_WEBSERVER_CONTAINER, 'chown root:root ' + authorizedKeysFile)
    _run_commandInContainer(_WEBSERVER_CONTAINER, 'chmod 600 ' + authorizedKeysFile)
    _run_commandInContainer(_WEBSERVER_CONTAINER, 'service ssh start')

    # Add doc-server as known host to prevent the authentication request on the first connect
    _addRemoteToKnownSSHHostsOfJenkinsMaster(_WEBSERVER_CONTAINERIP)


def _configureJenkinsMaster(configValues, configFile, jenkinsAdminPassword):
    if not configValues['UseUnconfiguredJenkinsMaster']:
        print("----- Configure the jenkins master server.")

        _setGeneralJenkinsOptions(configValues)
        _setJenkinsUsers(configValues, configFile)
        _setJenkinsJobs(configValues, configFile)

        # restart jenkins to make sure it as the desired configuration
        # this is required because setting the slaves requires jenkins to be
        # up and running.
        _stopDockerContainer(_JENINS_MASTER_CONTAINER)
        _startDockerContainer(_JENINS_MASTER_CONTAINER)
        _waitForJenkinsMasterToComeOnline(configValues, jenkinsAdminPassword)

        _setJenkinsSlaves(configValues, jenkinsAdminPassword)


    else:
        print(
            "Jenkins will be run without the default conifiguration," +
            " because no user files were given.")


def _setGeneralJenkinsOptions(configValues):
    """
    Configure the general options by copying the .xml config files from the JenkinsConfig
    directory to the jenkins master home directory.
    """
    jenkinsWorkspaceHost = configValues['HostJenkinsMasterShare']
    distutils.dir_util.copy_tree(_scriptDir + '/JenkinsConfig', jenkinsWorkspaceHost)


def _setJenkinsUsers(configValues, configFile):
    """
    Copy user config xml files to user/<username>/config.xml
    """
    _copyJenkinsConfigFiles(configValues, configFile, 'users', 'JenkinsAccountConfigFiles')


def _setJenkinsJobs(configValues, configFile):
    """
    copy job config xml files to jobs/<jobname>/config.xml
    """
    _copyJenkinsConfigFiles(configValues, configFile, 'jobs', 'JenkinsJobConfigFiles')


def _copyJenkinsConfigFiles(configValues, configFile, configDir, filesConfigKey):
    """
    Copies the config.xml files that are mentioned in a map under filesConfigKey
    in the script config file to named directories under the given config dir
    to the jenkins-master home directory.
    """
    jenkinsWorkspaceHost = configValues['HostJenkinsMasterShare']
    configFileDir = os.path.dirname(configFile)
    jobsConfigDir = jenkinsWorkspaceHost + '/' + configDir
    for job, jobConfigFile in configValues[filesConfigKey].items():
        if configFileDir:
            sourceConfigFile = configFileDir + '/' + jobConfigFile
        else:
            sourceConfigFile = jobConfigFile
        jobConfigDir = jobsConfigDir + '/' + job
        os.makedirs(jobConfigDir)
        shutil.copyfile(sourceConfigFile, jobConfigDir + '/config.xml')


def _waitForJenkinsMasterToComeOnline(configValues, jenkinsPassword):
    """
    Returns when the jenkins instance is fully operable.

    We wait for the crumb request to work, because this is what we need next.
    """
    print("----- Wait for jenkins to come online")
    # We have to whait a little or we get python exceptions.
    # This is ugly, because it can still fail on slower machines.
    time.sleep(10)
    crumbText = "Jenkins-Crumb"
    url = 'http://localhost:8080/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,":",//crumb)'
    auth = (configValues['JenkinsAdminUser'], jenkinsPassword)

    text = ''
    while not crumbText in text:
        text = requests.get(url, auth=auth).text
        time.sleep(1)


def _setJenkinsSlaves(configValues, jenkinsAdminPassword):
    """
    Create config files for the slave nodes.
    All slave nodes are based on the ssh command execution start scheme from
    the command-launcher plugin.
    """
    print("----- Configure jenkins slave nodes")
    # create config file for the linux slave
    _configureNodeConfigFile(
        configValues,
        jenkinsAdminPassword,
        _FULL_LINUX_JENKINS_SLAVE_NAME,
        'A Debinan 8.9 build slave based on a docker container.',
        '/home/jenkins/workspaces',
        _JENKINS_LINUX_SLAVE_CONTAINER_IP,
        'jenkins',
        '~/bin',
        _getSlaveLabelsString('Debian-8.9', 4)
    )

    # create config file for the windows slave
    slaveWorkspace = 'C:/jenkins'
    _configureNodeConfigFile(
        configValues,
        jenkinsAdminPassword,
        _FULL_WINDOWS_JENKINS_SLAVE_NAME,
        'A Windows 10 build slave based on a virtual machine.',
        slaveWorkspace,
        configValues['BuildSlaveWindowsMachine'],
        configValues['BuildSlaveWindowsMachineUser'],
        slaveWorkspace,
        _getSlaveLabelsString('Windows-10', 4)
    )


def _getSlaveLabelsString(baseLabelName, maxIndex):
    labels = [baseLabelName]
    for i in range(maxIndex + 1):
        labels.append(baseLabelName + '-' + str(i))
    return ' '.join(labels)


def _configureNodeConfigFile(
        configValues,
        jenkinsAdminPassword,
        slaveName,
        description,
        slaveWorkspaceDir,
        slaveMachine,
        slaveMachineUser,
        slaveJarDir,
        slaveLabels):
    """
    Uses a template file to create a config.xml file for a jenkins node that the master
    controls via ssh.
    """
    nodesDir = _scriptDir + '/JenkinsConfig/nodes'
    nodeDir = nodesDir + '/' + slaveName
    clearDirectory(nodeDir)

    createdConfigFile = nodeDir + '/config.xml'
    configTemplateFile = _scriptDir + '/jenkinsSlaveNodeConfig.xml.in'
    startCommand = (
        'ssh {0}@{1} java -jar {2}/slave.jar'
        ).format(slaveMachineUser, slaveMachine, slaveJarDir)

    # create the config file in nodes
    configureFile(configTemplateFile, createdConfigFile, {
        '$SLAVE_NAME' : slaveName,
        '$DESCRIPTION' : description,
        '$WORKSPACE' : slaveWorkspaceDir,
        '$START_COMMAND' : startCommand,
        '$LABELS' : slaveLabels
    })

    # Approve the start commands via jenkins groovy script console
    jenkinsUser = configValues['JenkinsAdminUser']
    jenkinsCrumb = _getJenkinsCrumb(jenkinsUser, jenkinsAdminPassword)
    _approveJenkinsScript(jenkinsUser, jenkinsAdminPassword, jenkinsCrumb, startCommand)


def _getJenkinsCrumb(jenkinsUser, jenkinsPassword):
    url = 'http://localhost:8080/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,":",//crumb)'
    auth = (jenkinsUser, jenkinsPassword)
    request = requests.get(url, auth=auth)
    request.raise_for_status()
    return request.text


def _approveJenkinsScript(jenkinsUser, jenkinsPassword, jenkinsCrumb, approvedScriptText):
    """
    Runs a groovy script over the jenkins groovy console, that approves the commands
    that are used to start the slaves.
    """
    url = 'http://localhost:8080/scriptText'
    myAuth = ('Knitschi', '3utterBro+')
    crumbParts = jenkinsCrumb.split(':')
    crumbHeader = {crumbParts[0] : crumbParts[1]}
    groovyScript = (
        "def scriptApproval = Jenkins.instance.getExtensionList('org.jenkinsci.plugins.scriptsecurity.scripts.ScriptApproval')[0];" +
        "scriptApproval.approveScript(scriptApproval.hash('{0}', 'system-command'))"
        ).format(approvedScriptText)
    scriptData = {'script' : groovyScript}

    response = requests.post(url, auth=myAuth, headers=crumbHeader, data=scriptData)
    response.raise_for_status()


if __name__ == '__main__':
    sys.exit(main())
