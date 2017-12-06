 #!/usr/bin/env python3

 # This script removes and adds and starts all docker container of the CppCodeBase project infrastructure.
 # Curently the containers are:
 # jenkins-master
 # jenkins-slave-linux-0
 # ccb-web-server

import os
import sys
import socket
import distutils.dir_util
import subprocess
import shutil
import io

_scriptDir = os.path.dirname(os.path.realpath(__file__))


# Directories and Variables
# In the future there may be multiple slaves so the script provides the _linuxSlaveIndex to destinguish between them.
_linuxSlaveIndex = 0
_windowsSlaveIndex = 0

# docker entities names
# container
_webserverContainer = 'ccb-web-server'
_jenkinsMasterContainer = 'jenkins-master'
_linuxSlaveBaseName = 'jenkins-slave-linux'
_fullLinuxJenkinsSlaveName = _linuxSlaveBaseName + '-' + str(_linuxSlaveIndex)
_fullWindowsJenkinsSlaveName = 'jenkins-slave-windows-' + str(_windowsSlaveIndex)
# networks
_dockerNetworkName = 'CppCodeBaseNetwork'

# container ips
_webserverContainerIP = '172.19.0.2'
_jenkinsMasterContainerIP = '172.19.0.3'
_jenkinsLinuxSlaveContainerIP = '172.19.0.4'

# other machines and users
_repositoryMachine = 'datenbunker'                              # The name of the machine that holds the repositories.
_repositoryMachineIP = socket.gethostbyname( _repositoryMachine ) # This will get the current ip address of the repository machine.
_repositoryMachineRootUser = 'admin'                            # A user with administrative rights on the repository machine.

_jenkinsSlaveMachineWindows = 'buildknechtwin'                  # The name of the machine that runs the windows build slave.
_jenkinsSlaveMachineWindowsUser = 'Knitschi'                    # A user on the _jenkinsSlaveMachineWindows that can be used for ssh access.
_jenkinsSlaveMachineWindowsPassword = '3utterBro+'

# Files
_publicKeyFilePostfix = '_ssh_key.rsa.pub'
_createKeyPairScript = 'createSSHKeyFilePair.sh'
_addKnownHostScript = 'addKnownSSHHost.sh'
_addAuthorizedKeysBitwiseSSHScript = 'addAuthorizedBitwiseSSHKey.bat'

# shared directories on host
_jenkinsWorkspaceHost = '/home/knitschi/CppCodeBaseMachines/jenkins-master-workspace'
_htmlShareHost = '/home/knitschi/CppCodeBaseMachines/html'

# directories on jenkins-master
_jenkinsWorkspaceJenkinsMaster = '/var/jenkins_home'                    # This is the location of the jenkins configuration files on the jenkins-master. 
_htmlShareJenkinsMaster = _jenkinsWorkspaceJenkinsMaster + '/html'        # This is the location of the html-share volume on the jenkins master.

# directories on jenkins-slave
_jenkinsHomeJenkinsSlave = '/home/jenkins'

# directories on documentation-server
_htmlShareWebServer = '/var/www/html'

# directories on repository machine
_repositoryMachinePublicKeyDir = '/etc/config/ssh'


_linuxSlaveLabels = 'Debian-8.9 Debian-8.9-0 Debian-8.9-1 Debian-8.9-2 Debian-8.9-3 Debian-8.9-4'

def clearDirectory(directory):
    """
    This functions deletes the given directory and all its content and recreates it.
    """
    if(os.path.isdir(directory)):
        shutil.rmtree(directory)
    os.makedirs(directory)


def configureFile( sourceFile, destFile, replacementDictionary ):
    """
    Searches in sourceFile for the keys in replacementDictionary, replaces them
    with the values and writes the result to destFile.
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


def main():
    # prepare environment
    print('----- Cleanup existing container')
    _clearDocker()
    clearDirectory(_jenkinsWorkspaceHost)
    _guaranteeDirectoryExists(_htmlShareHost)   # we do not clear this to preserve the accumulated web content.
    _createDockerNetwork(_dockerNetworkName)
    _createJenkinsNodeConfigFiles()

    # build container
    _buildAndStartJenkinsMaster()
    # The document server must be started before the jenkins slave is started because mounting the shared volume here sets the
    # owner of the share to root an only the jenkins container can set it to jenkins.
    _buildAndStartWebServer()
    _buildAndStartJenkinsLinuxSlave()

    # setup ssh accesses used by jenkins-master
    _createRSAKeyFilePairOnContainer( _jenkinsMasterContainer, _jenkinsWorkspaceJenkinsMaster)
    _grantContainerSSHAccessToRepository( _jenkinsMasterContainer, _jenkinsWorkspaceJenkinsMaster)
    _grantJenkinsMasterSSHAccessToJenkinsLinuxSlave()
    _grantJenkinsMasterSSHAccessToJenkinsWindowsSlave()
    _grantJenkinsMasterSSHAccessToWebServer()
    # setup ssh accesses used by jenkins-slave-linux
    _createRSAKeyFilePairOnContainer( _fullLinuxJenkinsSlaveName, _jenkinsHomeJenkinsSlave)
    _grantContainerSSHAccessToRepository( _fullLinuxJenkinsSlaveName, _jenkinsHomeJenkinsSlave)

    _configureJenkinsMaster()

    print('Successfully startet jenkins master, build slaves and the documentation server.')


def devMessage(text):
    print('--------------- ' + str(text))


def _clearDocker():
    _stubbornlyRemoveContainer(_webserverContainer)
    _stubbornlyRemoveContainer(_jenkinsMasterContainer)
    _stubbornlyRemoveContainer(_fullLinuxJenkinsSlaveName)
    
    _removeDockerNetwork(_dockerNetworkName)


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
    return _runCommandToGetList("docker ps --format '{{.Names}}'")


def _getAllDockerContainer():
    return _runCommandToGetList("docker ps -a --format '{{.Names}}'")


def _runCommandToGetList(command):
    """
    The function assumes that the ouput of comand is a list with one element per line.
    It returns that list as a python list.
    """
    output = _runCommand(command)
    return output.splitlines()


def _runCommand(command, printOutput = False, printCommand = False):
    """
    Runs the given command and returns its standard output.
    The function throws if the command fails. In this case the output is always printed.
    """
    workingDir = os.getcwd()
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd = workingDir)
    # wait for process to finish and get output
    out, err = process.communicate()
    
    output = ''
    if printCommand:
        output = command + '\n'

    output += out.decode("utf-8")
    errOutput = err.decode("ISO-8859-1")
    retCode = process.returncode

    if printOutput:
        print(output)
        print(errOutput)

    if retCode != 0:
        if not printOutput:                         # always print the output in case of an error
            print(output)
            print(errOutput)
        raise Exception('Command "' + command +'" executed in directory "' + workingDir + '" failed.')

    return output


def _stopDockerContainer(container):
    _runCommand('docker stop ' + container)


def _startDockerContainer(container):
    _runCommand('docker start ' + container)


def _removeContainer(container):
    """
    This removes a given docker container and will fail if the container is running.
    """
    _runCommand('docker rm -f ' + container)


def _removeDockerNetwork(network):
    networkLines = _runCommandToGetList('docker network ls')
    networks = []
    for line in networkLines:
        columns = line.split()
        networks.append(columns[1])

    if network in networks:
        _runCommand('docker network rm ' + _dockerNetworkName)


def _guaranteeDirectoryExists(directory):
    if not os.path.isdir(directory):
        os.makedirs(directory)


def _createDockerNetwork(network):
    _runCommand('docker network create --subnet=172.19.0.0/16 ' + network)


def _createJenkinsNodeConfigFiles():

    # create config file for the windows slave
    _configureNodeConfigFile(
        _fullLinuxJenkinsSlaveName,
        'A Debinan 8.9 build slave based on a docker container.',
        '/home/jenkins/workspaces',
        _jenkinsLinuxSlaveContainerIP,
        _jenkinsSlaveMachineWindowsUser,
        '~/bin',
        _getSlaveLabelsString( 'Debian-8.9' , 4)
    )

    # create config file for the windows slave
    slaveWorkspace = 'C:\\jenkins'
    _configureNodeConfigFile(
        _fullWindowsJenkinsSlaveName,
        'A Windows 10 build slave based on a virtual machine.',
        slaveWorkspace,
        _jenkinsSlaveMachineWindows,
        _jenkinsSlaveMachineWindowsUser,
        slaveWorkspace,
        _getSlaveLabelsString( 'Windows-10' , 4)
    )


def _getSlaveLabelsString(baseLabelName, maxIndex):
    labels = [baseLabelName]
    for i in range(maxIndex + 1):
        labels.append(baseLabelName + '-' + str(i))
    return ' '.join(labels)


def _configureNodeConfigFile( slaveName, description, slaveWorkspaceDir, slaveMachine, slaveMachineUser, slaveJarDir, slaveLabels ):
    """
    Uses a template file to create a config.xml file for a jenkins node that the master
    controls via ssh.
    """
    nodesDir = _scriptDir + '/JenkinsConfig/nodes'
    nodeDir = nodesDir + '/' + slaveName
    clearDirectory(nodeDir)

    createdConfigFile = nodeDir + '/config.xml'
    configTemplateFile = _scriptDir + '/jenkinsSlaveNodeConfig.xml.in'

    configureFile( configTemplateFile, createdConfigFile, { 
        '$SLAVE_NAME' : slaveName,
        '$DESCRIPTION' : description,
        '$WORKSPACE' : slaveWorkspaceDir,
        '$USER' : slaveMachineUser,
        '$MACHINE' : slaveMachine,
        '$SLAVE_JAR_DIR' : slaveJarDir,
        '$LABELS' : slaveLabels
    } )


def _buildAndStartJenkinsMaster():
    print( "----- Build and start the docker MASTER container " + _jenkinsMasterContainer )

    # Create the container image
    containerImage = _jenkinsMasterContainer + '-image'
    _buildDockerImage( containerImage, _scriptDir + '/DockerfileJenkinsMaster' , _scriptDir )

    # Start the container
    # --env JAVA_OPTS="-Djenkins.install.runSetupWizard=false" 
    # The jenkins master and its slaves communicate over the bridge network. 
    # This means the master and the slaves must be on the same host. This should later be upgraded to a swarm.
    command = ( 
        'docker run '
        '--detach '
        '--volume ' + _jenkinsWorkspaceHost + ':' + _jenkinsWorkspaceJenkinsMaster + ' ' # This makes the jenkins home directory accessible on the host. This eases debugging. 
        '--env JAVA_OPTS="-Djenkins.install.runSetupWizard=false" '                      # This prevents the plugin install wizard from popping up on the first startup.
        '--publish 8080:8080 '                                                           # The jenkins webinterface is available under this port.
        '--publish 50000:50000 '                                                         # Who uses this?
        '--name ' + _jenkinsMasterContainer + ' '
        '--net ' + _dockerNetworkName + ' '
        '--ip ' + _jenkinsMasterContainerIP + ' '
        + containerImage
    )
    _runCommand( command, True)

    # add global gitconfig after mounting the workspace volume, otherwise is gets deleted.
    _runCommandInContainer(_jenkinsMasterContainer, 'git config --global user.email not@valid.org')
    _runCommandInContainer(_jenkinsMasterContainer, 'git config --global user.name jenkins')


def _buildDockerImage( imageName, dockerFile, buildContextDirectory):
    command = 'docker build -t ' + imageName + ' -f ' + dockerFile + ' ' + buildContextDirectory
    _runCommand( command, True)

def _runCommandInContainer(container, command, user = None):
    userOption = ''
    if user:
        userOption = '--user ' + user + ':' + user + ' '
    command = 'docker exec ' + userOption + container + ' ' + command
    print(command)
    return _runCommand(command)


def _buildAndStartWebServer():
    print( "----- Build and start the web-server container " + _webserverContainer)
    
    containerImage = _webserverContainer + '-image'
    _buildDockerImage( containerImage, _scriptDir + '/DockerfileCcbWebServer', _scriptDir )

    command = (
        'docker run '
        '--detach '
        '--publish 80:80 '      # The web-page is reached under port 80
        '--volume ' + _htmlShareHost + ':' + _htmlShareWebServer + ' '
        '--name ' + _webserverContainer + ' '
        '--net ' + _dockerNetworkName + ' '
        '--ip ' + _webserverContainerIP + ' '
        + containerImage
    )
    _runCommand( command, True)

    # copy the doxyserach.cgi to the html share
    _runCommandInContainer( _webserverContainer, 'rm -fr ' + _htmlShareWebServer + '/cgi-bin', 'root')
    _runCommandInContainer( _webserverContainer, 'mkdir ' + _htmlShareWebServer + '/cgi-bin', 'root')
    _runCommandInContainer( _webserverContainer, 'mkdir ' + _htmlShareWebServer + '/cgi-bin/doxysearch.db', 'root')
    _runCommandInContainer( _webserverContainer, 'cp -r -f /usr/local/bin/doxysearch.cgi ' + _htmlShareWebServer + '/cgi-bin', 'root')


def _buildAndStartJenkinsLinuxSlave():
    # Start the container.
    print("----- Build and start the docker SLAVE container " + _fullLinuxJenkinsSlaveName)

    containerImage = _linuxSlaveBaseName + '-image'
    _buildDockerImage( containerImage, _scriptDir + '/DockerfileJenkinsSlaveLinux', _scriptDir )

    command = (
        'docker run '
        '--detach '
        '--name ' + _fullLinuxJenkinsSlaveName + ' '
        '--net ' + _dockerNetworkName + ' '
        '--ip ' + _jenkinsLinuxSlaveContainerIP + ' '
        + containerImage
    )
    _runCommand( command, True)


def _createRSAKeyFilePairOnContainer(containerName, containerHomeDirectory):
    print('----- Create SSH key file pair for container ' + containerName + ' in directory ' + containerHomeDirectory )
    
    # copy the scripts that does the job to the container
    _runCommand('docker cp ' + _scriptDir + '/' + _createKeyPairScript + ' ' + containerName + ':' + containerHomeDirectory + '/' + _createKeyPairScript)
    _runCommand('docker cp ' + _scriptDir + '/' + _addKnownHostScript + ' ' + containerName + ':' + containerHomeDirectory + '/' + _addKnownHostScript)

    # This will create the key-pair on the container. We need to do this in the container or ssh will not accept the private key file.
    _runCommandInContainer( containerName, '/bin/bash ' + containerHomeDirectory + '/' + _createKeyPairScript + ' ' + containerName, 'jenkins') 


def _grantContainerSSHAccessToRepository( containerName, containerHomeDirectory):
    print('----- Grant container ' + containerName + ' SSH access to the repository machine ' + _repositoryMachine)
    # COPY AND REGISTER THE PUBLIC KEY WITH _repositoryMachine
    # The connection is used to access the git repository
    # This requires access to the datenbunker.
    publicKeyFile = containerName + _publicKeyFilePostfix
    tempDirHost= '~/temp'
    _guaranteeDirectoryExists(tempDirHost)
    fullTempPublicKeyFile = tempDirHost + '/' + publicKeyFile
    if os.path.isfile(fullTempPublicKeyFile):
        os.remove(fullTempPublicKeyFile) # delete previously copied key-files
    
    # Copy the public key from the jenkins jome directory to the jenkins-workspace directory on the host
    _runCommand('docker cp ' + containerName + ':' + containerHomeDirectory + '/' + publicKeyFile + ' ' + tempDirHost)
    
    # Then copy it to the repository machine
    _runCommand('scp {}/{} {}@{}.local:{}'.format( tempDirHost, publicKeyFile, _repositoryMachineRootUser, _repositoryMachine, _repositoryMachinePublicKeyDir)  )

    # add the key file to authorized_keys
    authorizedKeysFile = _repositoryMachinePublicKeyDir + '/authorized_keys' 
    # Remove previously appended public keys from the given container and append the new public key to the authorized_keys file.
    # - print file without lines containing machine name string, then append new key to end of file
    command = (
        'ssh {0}@{1} "'
        'cat {2} | grep -v {3} >> {4}/keys_temp &&'
        'mv -f {4}/keys_temp {2} &&'
        'cat {4}/{5} >> {2}"'
    )
    command = command.format(_repositoryMachineRootUser, _repositoryMachine, authorizedKeysFile, containerName, _repositoryMachinePublicKeyDir, publicKeyFile)

    devMessage(command)
    _runCommand(command)
    
    # Add datenbunker as known host to prevent the authentication request on the first connect
    _runCommandInContainer( containerName, '/bin/bash ' + containerHomeDirectory + '/' + _addKnownHostScript + ' ' +  _repositoryMachineIP, 'jenkins') 


def _grantJenkinsMasterSSHAccessToJenkinsLinuxSlave():
    print('----- Grant ' + _jenkinsMasterContainer + ' ssh access to ' + _fullLinuxJenkinsSlaveName)
    publicKeyFile = _jenkinsMasterContainer + _publicKeyFilePostfix
    
    # COPY AND REGISTER THE PUBLIC KEY WITH THE SLAVE 
    # Jenkins handles linux slaves with an ssh connection.
    _runCommand('docker cp {0}/{1} {2}:{3}/.ssh/authorized_keys'.format( _jenkinsWorkspaceHost, publicKeyFile, _fullLinuxJenkinsSlaveName, _jenkinsHomeJenkinsSlave ))
    # Add slave as known host to prevent the authentication request on the first connect
    _addRemoteToKnownSSHHostsOfJenkinsMaster( _jenkinsLinuxSlaveContainerIP )


def _grantJenkinsMasterSSHAccessToJenkinsWindowsSlave():
    print("----- Grant {0} ssh access to {1}".format( _jenkinsMasterContainer, _jenkinsSlaveMachineWindows) )
    
    # configure the script for adding an authorized key to the bitwise ssh server on the windows machine
    authorizedKeysScript = 'updateAuthorizedKeysBitvise.bat'
    fullAuthorizedKeysScript = _scriptDir + '/' + authorizedKeysScript
    publicKeyFile = _jenkinsWorkspaceHost + '/' + _jenkinsMasterContainer + _publicKeyFilePostfix
    publicKey = _readFileContent(publicKeyFile)
    publicKey = publicKey.replace('\n','').replace('\r', '')  # remove the line end from the key
    configureFile( fullAuthorizedKeysScript + '.in', fullAuthorizedKeysScript, {
        '@PUBLIC_KEY@' : publicKey,
        '@JENKINS_MASTER_CONTAINER@' : _jenkinsMasterContainer,
        '@SLAVE_MACHINE_USER@' : _jenkinsSlaveMachineWindowsUser,
        '@SLAVE_MACHINE_USER_PASSWORD@' : _jenkinsSlaveMachineWindowsPassword
    })

    # copy the script for to the windows slave machine
    userDir = 'C:/Users/' + _jenkinsSlaveMachineWindowsUser
    copyScriptCommand = 'scp {0} {1}@{2}:{3}'.format(
        fullAuthorizedKeysScript,
        _jenkinsSlaveMachineWindowsUser,
        _jenkinsSlaveMachineWindows,
        userDir)
    _runCommand(copyScriptCommand)

    # call the script
    fullScriptPathOnSlave = userDir + '/' + authorizedKeysScript
    callScriptCommand = (
        'ssh {0}@{1} "{2}"'
    ).format(
        _jenkinsSlaveMachineWindowsUser,
        _jenkinsSlaveMachineWindows,
        fullScriptPathOnSlave,
    )
    devMessage(callScriptCommand)
    _runCommand(callScriptCommand)

    # clean up the generated scripts because of the included password
    os.remove(fullAuthorizedKeysScript)
    fullScriptPathOnSlaveBackslash = 'C:\\\\Users\\\\' + _jenkinsSlaveMachineWindowsUser + '\\\\' + authorizedKeysScript
    deleteScriptOnSlaveCommand = 'ssh {0}@{1} "del {2}"'.format(
        _jenkinsSlaveMachineWindowsUser,
        _jenkinsSlaveMachineWindows,
        fullScriptPathOnSlaveBackslash,
    )
    _runCommand(deleteScriptOnSlaveCommand)

    # Add the slave to the known hosts
    _addRemoteToKnownSSHHostsOfJenkinsMaster( _jenkinsSlaveMachineWindows )


def _readFileContent(filename):
    with open(filename) as f:
        return f.read()


def _addRemoteToKnownSSHHostsOfJenkinsMaster( remoteMachine ):
    """
    remoteMachine can be an IP or machine name.
    """
    _runCommandInContainer( _jenkinsMasterContainer, '/bin/bash ' + _jenkinsWorkspaceJenkinsMaster + '/' + _addKnownHostScript + ' ' +  remoteMachine, 'jenkins')


def _grantJenkinsMasterSSHAccessToWebServer():
    authorizedKeysFile = '/root/.ssh/authorized_keys'
    publicKeyFile = _jenkinsMasterContainer + _publicKeyFilePostfix

    _runCommand( 'docker cp {0}/{1} {2}:{3}'.format(_jenkinsWorkspaceHost, publicKeyFile, _webserverContainer, authorizedKeysFile) )
    _runCommandInContainer( _webserverContainer, 'chown root:root ' + authorizedKeysFile )
    _runCommandInContainer( _webserverContainer, 'chmod 600 ' + authorizedKeysFile )
    _runCommandInContainer( _webserverContainer, 'service ssh start' )
    
    # Add doc-server as known host to prevent the authentication request on the first connect
    _addRemoteToKnownSSHHostsOfJenkinsMaster( _webserverContainerIP )


def _configureJenkinsMaster():
    # ------ COPY JENKINS CONFIGURATION TO MASTER --------
    print("---- Copy jenkins config.xml files to jenkins master.")
    
    # copy the content of JenkinsConfig to the jenkins workspace on the host
    distutils.dir_util.copy_tree( _scriptDir + '/JenkinsConfig', _jenkinsWorkspaceHost )
    
    # restart jenkins to make sure the config.xml files get loaded.
    _stopDockerContainer( _jenkinsMasterContainer)
    _startDockerContainer( _jenkinsMasterContainer)


if __name__ == '__main__':
    sys.exit(main())
