#!/usr/bin/env python3
"""
This script removes and adds and starts all docker container of the CMakeProjectFramework infrastructure.

Arguments:
1. - The path to a configuration json file.
(An empty file can be generated with the createEmptyconfig_files.py script)

\todo Setting up the windows slaves needs to be automated. Can we use a windows container technology that does not conflict with
the VMWare virtual machines? 

"""

import os
import posixpath
from pathlib import PureWindowsPath, PurePosixPath, PurePath
import stat
import sys
import distutils.dir_util
import subprocess
import shutil
import io
import json
import pprint
import time
import requests
import paramiko

from . import cpfmachines_version
from . import config_data

_SCRIPT_DIR = PurePath(os.path.dirname(os.path.realpath(__file__)))

# Constants
# The version of the jenkins CI server that is installed on the jenkins-master machine.
_JENKINS_VERSION = '2.89.1'
# The sha256 checksum of the jenkins.war package of the given jenkins version.
_JENKINS_SHA256 = 'f9f363959042fce1615ada81ae812e08d79075218c398ed28e68e1302c4b272f'
_JENKINS_BASE_IMAGE = 'jenkins-image-' + _JENKINS_VERSION

# docker network
_DOCKER_NETWORK_NAME = 'CPFNetwork'

# Files
_PUBLIC_KEY_FILE_POSTFIX = '_ssh_key.rsa.pub'
_CREATEKEYPAIR_SCRIPT = PurePath('createSSHKeyFilePair.sh')
_ADDKNOWNHOST_SCRIPT = PurePath('addKnownSSHHost.sh')
_ADDAUTHORIZEDKEYSBITWISESSH_SCRIPT = PurePath('addAuthorizedBitwiseSSHKey.bat')

# directories on jenkins-master
# This is the location of the jenkins configuration files on the jenkins-master.
_JENKINS_HOME_JENKINS_MASTER_CONTAINER = PurePosixPath('/var/jenkins_home')
# This is the location of the html-share volume on the jenkins master.
_HTML_SHARE_JENKINS_MASTER = _JENKINS_HOME_JENKINS_MASTER_CONTAINER.joinpath('html')

# directories on jenkins-slave-linux
_JENKINS_HOME_JENKINS_SLAVE_CONTAINER =  PurePosixPath('/home/jenkins')

# directories on cpf-web-server
_HTML_SHARE_WEB_SERVER_CONTAINER =  PurePosixPath('/var/www/html')


def configure_file(source_file, dest_file, replacement_dictionary):
    """
    Searches in source_file for the keys in replacement_dictionary, replaces them
    with the values and writes the result to dest_file.
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


def main(config_file):
    """
    Entry point of the script.
    """

    # read configuration file
    print('----- Read configuration file ' + config_file)
    config_file = PurePath(config_file)
    config_dict = config_data.read_json_file(config_file)
    config = config_data.ConfigData(config_dict)


    print('----- Establish ssh connections to host machines')
    config.establish_host_machine_connections()

    # prepare environment
    print('----- Cleanup existing docker container and networks')
    _clear_docker(config)
    _clear_host_directories(config)
    # we do not clear this to preserve the accumulated web content.
    _guarantee_directory_exists(config, config.web_server_host_config.machine_id, config.web_server_host_config.host_html_share_dir)
    _create_docker_networks(config)

    # build container
    print("----- Build jenkins base image on host " + config.jenkins_master_host_config.machine_id)
    _build_jenkins_base(config)

    print("----- Build and start container {0} on host {1}".format(config.jenkins_master_host_config.container_conf.container_name, config.jenkins_master_host_config.machine_id))
    _build_and_start_jenkins_master(config)

    # The document server must be started before the jenkins slave is started because mounting
    # the shared volume here sets the owner of the share to root an only the jenkins container
    # can set it to jenkins. Do we still use the document share to copy files?
    print("----- Build and start the web-server container " + config.web_server_host_config.container_conf.container_name)
    _build_and_start_web_server(config)
    print("----- Build and start the docker SLAVE containers")
    _build_and_start_jenkins_linux_slaves(config)

    # setup ssh accesses used by jenkins-master
    print(
    '----- Create SSH key file pair for container ' + config.jenkins_master_host_config.container_conf.container_name +
    ' in directory ' + str(_JENKINS_HOME_JENKINS_MASTER_CONTAINER))
    _create_rsa_key_file_pair_on_container(
        config,
        config.jenkins_master_host_config.container_conf,
        _JENKINS_HOME_JENKINS_MASTER_CONTAINER)

    _grant_container_ssh_access_to_repository(
        config,
        config.jenkins_master_host_config.container_conf,
        _JENKINS_HOME_JENKINS_MASTER_CONTAINER)
    print('----- Grant '+ config.jenkins_master_host_config.container_conf.container_name +' ssh access to linux slaves')
    _grant_jenkins_master_ssh_access_to_jenkins_linux_slaves(config)
    _grant_jenkins_master_ssh_access_to_jenkins_windows_slaves(config)
    _grant_jenkins_master_ssh_access_to_web_server(config)

    # setup ssh accesses used by the jenkins slaves
    _create_rsa_key_file_pairs_on_slave_container(config)
    _grant_linux_slaves_access_to_repository(config)
    # \todo Windows slaves need repository access as well. Did we do this manually?

    _configure_jenkins_master(config, config_file)

    print('Successfully startet jenkins master, build slaves and the documentation server.')


def dev_message(text):
    """
    Print function emphasizes the printed string with some dashes.
    It is intended to be used for debugging during development.
    """
    print('--------------- ' + str(text))


def _clear_docker(config):
    """
    Removes docker containers and networks from previous runs.
    Takes a config_data.ConfigData object as argument.
    """
    container_dict = config.get_container_machine_dictionary()
    for container in container_dict:
        _stubbornly_remove_container(config, container)

    container_machines = set(container_dict.values())
    for machine_id in container_machines:
        _remove_docker_network(config, machine_id, _DOCKER_NETWORK_NAME)


def _stubbornly_remove_container(config, container):
    """
    Removes a given docker container even if it is running.
    If the container does not exist, the function does nothing.
    """
    connection = config.get_container_host_machine_connection(container)
    if _container_exists(connection, container):
        if _container_is_running(connection, container):
            _stop_docker_container(connection, container)
        _remove_container(connection, container)


def _container_exists(connection, container):
    """
    Returns true if the container exists on the host.
    """
    all_container = _get_all_docker_container(connection)
    return container in all_container


def _get_all_docker_container(connection):
    return connection.run_command("docker ps -a --format '{{.Names}}'")


def _container_is_running(connection, container):
    """
    Returns true if the container is running on its host.
    """
    running_container = _get_running_docker_container(connection)
    return container in running_container


def _get_running_docker_container(connection):
    return connection.run_command("docker ps --format '{{.Names}}'")

def _stop_docker_container(connection, container):
    connection.run_command('docker stop ' + container)


def _start_docker_container(connection, container):
    connection.run_command('docker start ' + container)


def _remove_container(connection, container):
    """
    This removes a given docker container and will fail if the container is running.
    """
    connection.run_command('docker rm -f ' + container)


def _remove_docker_network(config, machine_id, network):
    connection = config.get_host_machine_connection(machine_id)
    network_lines = connection.run_command('docker network ls')
    networks = []
    for line in network_lines:
        columns = line.split()
        networks.append(columns[1])

    if network in networks:
        connection.run_command('docker network rm ' + network)


def _clear_host_directories(config):
    # the master share directory
    _clear_rdirectory(config, config.jenkins_master_host_config.machine_id, config.jenkins_master_host_config.jenkins_home_share)
    # all temporary directories
    for connection in config.host_machine_connections:
        if connection.temp_dir:
            _clear_rdirectory(config, connection.machine_id, connection.temp_dir)


def _clear_rdirectory(config, machine_id, directory):
    """
    This functions deletes the given directory and all its content and recreates it.
    It does it on the given machine.
    """
    connection = config.get_host_machine_connection(machine_id)
    with connection.ssh_client.open_sftp() as sftp_client:
        if _rexists(sftp_client, directory):
            _rrmtree(sftp_client, directory)
        _rmakedirs(sftp_client, directory)


def _rexists(sftp_client, path):
    """
    Returns true if the remote directory or file under path exists.
    """
    try:
        sftp_client.stat(str(path))
    except IOError as err:
        if err.errno == 2:
            return False
        raise
    else:
        return True


def _rrmtree(sftp_client, dir_path):
    """
    Removes the remote directory and its content.
    """
    for item in sftp_client.listdir_attr(str(dir_path)):
        rpath = dir_path.joinpath(item.filename)
        if stat.S_ISDIR(item.st_mode):
            _rrmtree(sftp_client, rpath)
        else:
            rpath = dir_path.joinpath(item.filename)
            sftp_client.remove(str(rpath))

    sftp_client.rmdir(str(dir_path))


def _rmakedirs(sftp_client, dir_path):
    """
    Creates a remote directory and all its parent directories.
    """
    # create a list with all sub-pathes, where the longer ones come first.
    pathes = [dir_path]
    pathes.extend(dir_path.parents) 
    # now create all sub-directories, starting with the shortest pathes
    for parent in reversed(pathes): 
        if not _rexists(sftp_client, parent):
            sftp_client.mkdir(str(parent))
    

def _guarantee_directory_exists(config, machine_id, dir_path):
    connection = config.get_host_machine_connection(machine_id)
    with connection.ssh_client.open_sftp() as sftp_client:
        if not _rexists(sftp_client, dir_path):
            _rmakedirs(sftp_client, dir_path)


def _create_docker_networks(config):
    container_dict = config.get_container_machine_dictionary()
    container_machines = set(container_dict.values())
    for machine_id in container_machines:
        _create_docker_network(config, machine_id, _DOCKER_NETWORK_NAME)


def _create_docker_network(config, machine_id, network):
    connection = config.get_host_machine_connection(machine_id)
    connection.run_command("docker network create --driver bridge --subnet={0} {1}".format(config.get_docker_subnet(), network))


def _build_jenkins_base(config):
    """
    This builds the base image of the jenkins-master container.
    """
    connection = _get_jenkins_master_host_connection(config)

    # crate the build-context on the host
    source_dir = _SCRIPT_DIR.joinpath('../JenkinsciDocker')
    docker_file = 'Dockerfile'
    files = [
        docker_file,
        'tini_pub.gpg',
        'init.groovy',
        'jenkins-support',
        'jenkins.sh',
        'plugins.sh',
        'install-plugins.sh',
    ]
    context_dir = _get_context_dir(connection, _JENKINS_BASE_IMAGE)
    _create_build_context_dir(config, connection, source_dir, context_dir, files)

    # Create the jenkins base image. This is required to customize the jenkins version.
    _build_docker_image(
        connection,
        _JENKINS_BASE_IMAGE,
        context_dir.joinpath(docker_file),
        context_dir,
        ['JENKINS_VERSION=' + _JENKINS_VERSION, 'JENKINS_SHA=' + _JENKINS_SHA256])


def _get_jenkins_master_host_connection(config):
    return config.get_host_machine_connection(config.jenkins_master_host_config.machine_id)

def _get_context_dir(connection, image_name):
    return connection.temp_dir.joinpath(image_name)


def _create_build_context_dir(config, connection, source_dir, context_dir, text_files, binary_files=[]):
    """
    context_dir is the directory on the host that is used as a build context for the container.
    source_dir is the absolute directory on the machine executing the script that contains the files
    required for building the container.
    """
    with connection.ssh_client.open_sftp() as sftp_client:

        source_dir = PurePath(source_dir)

        # copy text files to the host
        for file_path in text_files:
            source_path = source_dir.joinpath(file_path)
            target_path = context_dir.joinpath(file_path)
            # Copy the file.
            _copy_textfile_from_local_to_linux(connection, sftp_client, source_path, target_path)

        # copy binary files to the host
        for file_path in binary_files:
            source_path = source_dir.joinpath(file_path)
            target_path = context_dir.joinpath(file_path)
            # Copy the file.
            _copy_file_from_local_to_remote(connection, sftp_client, source_path, target_path)


def _copy_textfile_from_local_to_linux(connection, sftp_client, source_path, target_path):
    """
    This function ensures that the file-endings of the text-file are set to linux
    convention after the copy.
    """
    _copy_file_from_local_to_remote(connection, sftp_client, source_path, target_path)
    # Remove \r from file from windows line endings.
    # This may be necessary when the machine that executes this script
    # is a windows machine.
    temp_file = target_path.parent.joinpath('temp.txt')
    format_line_endings_command = "tr -d '\r' < '{0}' > '{1}' && mv {1} {0}".format(str(target_path), str(temp_file))
    connection.run_command(format_line_endings_command)


def _copy_file_from_local_to_remote(connection, sftp_client, source_path, target_path):
    """
    Copies a file to a host machine defined by connection, without changing it.
    """
    # make sure a directory for the target file exists
    _rmakedirs(sftp_client, target_path.parent)
    sftp_client.put( str(source_path), str(target_path) )


def _build_docker_image(connection, image_name, docker_file, build_context_directory, build_args):
    build_args_string = ''
    for arg in build_args:
        build_args_string += ' --build-arg ' + arg

    command = (
        'docker build' + build_args_string + ' -t ' + image_name +
        ' -f ' + str(docker_file) + ' ' + str(build_context_directory)
    )
    connection.run_command(command, print_output=True, print_command=True)


def _build_and_start_jenkins_master(config):

    connection = _get_jenkins_master_host_connection(config)
    container_name = config.jenkins_master_host_config.container_conf.container_name
    container_image = config.jenkins_master_host_config.container_conf.container_image_name

    # create a directory on the host that contains all files that are needed for the container build
    docker_file = 'DockerfileJenkinsMaster'
    files = [
        docker_file,
        'installGcc.sh',
        'buildGit.sh',
        'buildCMake.sh',
    ]
    context_dir = _get_context_dir(connection, container_name)
    _create_build_context_dir(config, connection, _SCRIPT_DIR, context_dir, files)

    # Create the container image
    _build_docker_image(
        connection,
        container_image,
        context_dir.joinpath(docker_file),
        context_dir,
        ['JENKINS_BASE_IMAGE=' + _JENKINS_BASE_IMAGE])

    # Start the container
    # --env JAVA_OPTS="-Djenkins.install.runSetupWizard=false"
    # The jenkins master and its slaves communicate over the bridge network.
    # This means the master and the slaves must be on the same host.
    # This should later be upgraded to a swarm.

    # When the user already has a jenkins configuration
    # we add an option that prevents the first startup wizard from popping up.
    no_setup_wizard_option = ''
    if not config.jenkins_config.use_unconfigured_jenkins:
        no_setup_wizard_option = '--env JAVA_OPTS="-Djenkins.install.runSetupWizard=false" '

    command = (
        'docker run '
        '--detach '
        # This makes the jenkins home directory accessible on the host. This eases debugging.
        '--volume ' + str(config.jenkins_master_host_config.jenkins_home_share) + ':' + str(_JENKINS_HOME_JENKINS_MASTER_CONTAINER) + ' '
        + no_setup_wizard_option +
        # The jenkins webinterface is available under this port.
        '--publish 8080:8080 '
        # Only needed for hnlp slaves. We leave it here in case we need hnlp slave later.
        #'--publish 50000:50000 '
        '--name ' + container_name + ' '
        '--net ' + _DOCKER_NETWORK_NAME + ' '
        '--ip ' + config.jenkins_master_host_config.container_conf.container_ip + ' '
        + container_image
    )
    connection.run_command(command, print_command=True)

    # add global gitconfig after mounting the workspace volume, otherwise is gets deleted.
    commands = [
        'git config --global user.email not@valid.org',
        'git config --global user.name jenkins'
    ]
    _run_commands_in_container(
        connection,
        config.jenkins_master_host_config.container_conf,
        commands
        )


def _run_command_in_container(connection, container_config, command, user=None, print_command=True):
    """
    The user option can be used to run the command for a different user then
    the containers default user.
    """
    user_option = ''
    if not user:
        user = container_config.container_user
    user_option = '--user ' + user + ':' + user + ' '
    command = 'docker exec ' + user_option + container_config.container_name + ' ' + command
    output = connection.run_command(command, print_command)
    return output


def _run_commands_in_container(host_connection, container_config, commands, user=None):
    for command in commands:
        _run_command_in_container(
            host_connection,
            container_config,
            command,
            user
        )


def _build_and_start_web_server(config):
    connection = config.get_host_machine_connection(config.web_server_host_config.machine_id)
    container_name = config.web_server_host_config.container_conf.container_name
    container_image = config.web_server_host_config.container_conf.container_image_name
    
    # create build context
    docker_file = 'DockerfileCPFWebServer'
    files = [
        docker_file,
        'installClangTools.sh',
        'installGcc.sh',
        'buildDoxygen.sh',
        'ssh_config',
        'serve-cgi-bin.conf',
        'supervisord.conf',
    ]
    context_dir = _get_context_dir(connection, container_image)
    _create_build_context_dir(config, connection, _SCRIPT_DIR, context_dir, files)

    # build container image
    _build_docker_image(
        connection,
        container_image,
        context_dir.joinpath(docker_file),
        context_dir, 
        []
        )

    # start container
    command = (
        'docker run '
        '--detach '
        '--publish 80:80 '      # The web-page is reached under port 80
        '--publish ' + str(config.web_server_host_config.container_conf.mapped_ssh_host_port) + ':22 ' # publish the port of the ssh server
        '--volume ' + str(config.web_server_host_config.host_html_share_dir) + ':' + str(_HTML_SHARE_WEB_SERVER_CONTAINER) + ' '
        '--name ' + container_name + ' '
        '--net ' + _DOCKER_NETWORK_NAME + ' '
        '--ip ' + config.web_server_host_config.container_conf.container_ip + ' '
        + container_image
    )
    connection.run_command(command, print_command=True)

    # copy the doxyserach.cgi to the html share
    cgi_bin_dir = _HTML_SHARE_WEB_SERVER_CONTAINER.joinpath('cgi-bin')
    commands = [
        'rm -fr ' + str(cgi_bin_dir),
        'mkdir ' + str(cgi_bin_dir),
        'mkdir ' + str(cgi_bin_dir) + '/doxysearch.db',
        'cp -r -f /usr/local/bin/doxysearch.cgi ' + str(cgi_bin_dir),
    ]
    _run_commands_in_container(
        connection,
        config.web_server_host_config.container_conf,
        commands
        )


def _build_and_start_jenkins_linux_slaves(config):
    for slave_config in config.jenkins_slave_configs:
        if config.is_linux_machine(slave_config.machine_id):
            _build_and_start_jenkins_linux_slave(config, slave_config.container_conf, slave_config.machine_id)


def _build_and_start_jenkins_linux_slave(config, container_conf, machine_id):
    
    connection = config.get_host_machine_connection(machine_id)
    container_image = container_conf.container_image_name

    if not _docker_container_image_exists(connection, container_image):
        # create build context
        docker_file = 'DockerfileJenkinsSlaveLinux'
        text_files = [
            docker_file,
            'installClangTools.sh',
            'installGcc.sh',
            'buildQt.sh',
            'buildGit.sh',
            'buildCMake.sh',
            'buildDoxygen.sh',
            'installCTags.sh',
            'installAbiComplianceChecker.sh',
            'ssh_config',
        ]
        binary_files = [
            'slave.jar',
        ]
        context_dir = _get_context_dir(connection, container_image)
        _create_build_context_dir(config, connection, _SCRIPT_DIR, context_dir, text_files, binary_files)

        # Build the container.
        _build_docker_image(
            connection,
            container_image,
            context_dir.joinpath(docker_file),
            context_dir,
            []
            )

    # Start the container.
    command = (
        'docker run '
        '--detach '
        '--name ' + container_conf.container_name + ' '
        '--net ' + _DOCKER_NETWORK_NAME + ' '
        '--ip ' + container_conf.container_ip + ' '
        '--publish ' + str(container_conf.mapped_ssh_host_port) + ':22 '
        + container_image
    )
    connection.run_command(command, print_command=True)


def _docker_container_image_exists(connection, image_name):
    images = connection.run_command('docker images')
    return image_name in images


def _create_rsa_key_file_pair_on_container(config, container_conf, container_home_directory):
    connection = config.get_container_host_machine_connection(container_conf.container_name)

    # copy the scripts that does the job to the container
    with connection.ssh_client.open_sftp() as sftp_client:
        _copy_textfile_to_container(connection, sftp_client, container_conf, _SCRIPT_DIR.joinpath(_CREATEKEYPAIR_SCRIPT), container_home_directory.joinpath(_CREATEKEYPAIR_SCRIPT) )

    # This will create the key-pair on the container.
    # We need to do this in the container or ssh will not accept the private key file.
    _run_command_in_container(
        connection,
        container_conf,
        '/bin/bash ' + str(container_home_directory.joinpath(_CREATEKEYPAIR_SCRIPT)) + ' ' + container_conf.container_name
        )
   

def _copy_textfile_to_container(connection, sftp_client, container_conf, source_path, target_path):
    """
    We first copy the file to the hosts context directory and then to the container.
    """
    context_dir = _get_context_dir(connection, container_conf.container_image_name)
    host_file = context_dir.joinpath(source_path.name)
    _copy_textfile_from_local_to_linux(connection, sftp_client, source_path, host_file)
    _copy_file_from_host_to_container(connection, container_conf, host_file, target_path)


def _copy_file_from_host_to_container(host_connection, container_conf, source_file, target_file):
    _run_command_in_container(
        host_connection,
        container_conf,
        'mkdir -p {0}'.format(target_file.parent),
        print_command=False
    )
    host_connection.run_command("docker cp {0} {1}:{2}".format(source_file, container_conf.container_name, target_file))


def _grant_container_ssh_access_to_repository(config, container_conf, container_home_directory):

    repository_machine_id = config.repository_host_config.machine_id
    repository_connection = config.get_host_machine_connection(config.repository_host_config.machine_id)
    repository_machine_ssh_dir = config.repository_host_config.ssh_dir

    container_name = container_conf.container_name
    container_host_connection = config.get_container_host_machine_connection(container_name)
    temp_dir_chost = container_host_connection.temp_dir

    print('----- Grant container ' + container_name + ' SSH access to the repository machine ' + repository_machine_id)

    # COPY AND REGISTER THE PUBLIC KEY WITH repositoryMachine
    # The connection is used to access the git repository
    # This requires access to the datenbunker.
    with container_host_connection.ssh_client.open_sftp() as sftp_client:
        public_key_file = _get_public_key_filename(container_name)

        _guarantee_directory_exists(config, container_host_connection.machine_id, temp_dir_chost)
        
        # delete previously copied key-files
        full_temp_public_key_file = temp_dir_chost.joinpath(public_key_file)
        if _rexists(sftp_client, full_temp_public_key_file):
            sftp_client.remove(full_temp_public_key_file)

        # Copy the public key from the jenkins home directory to the
        # jenkins-workspace directory on the host
        container_host_connection.run_command('docker cp {0}:{1}/{2} {3}'.format(container_name, container_home_directory, public_key_file, temp_dir_chost))

        # Then copy it to the repository machine
        with repository_connection.ssh_client.open_sftp() as repo_sftp_client:
            _rtorcopy(sftp_client, repo_sftp_client, temp_dir_chost.joinpath(public_key_file) , repository_machine_ssh_dir.joinpath(public_key_file))

        # add the key file to authorized_keys
        authorized_keys_file = repository_machine_ssh_dir.joinpath('authorized_keys')
        # Remove previously appended public keys from the given container and append the
        # new public key to the authorized_keys file.
        # - print file without lines containing machine name string, then append new key to end of file
        command = (
            'cat {0} | grep -v {1} >> {2}/keys_temp &&'
            'mv -f {2}/keys_temp {0} &&'
            'cat {2}/{3} >> {0}'
        ).format(
            authorized_keys_file,
            container_name,
            repository_machine_ssh_dir,
            public_key_file)
        repository_connection.run_command(command)

        # Add the repository machine as known host to prevent the authentication request on the first
        _accept_remote_container_host_key(
            container_host_connection, 
            container_conf, 
            repository_connection, 
            22,
            repository_connection.user_name
        )


def _get_public_key_filename(container):
    return container + _PUBLIC_KEY_FILE_POSTFIX


def _rtorcopy(source_sftp_client, target_sftp_client, source_file, target_file):
    """
    Copy a file from one remote machine to another.
    """
    local_temp_file = _SCRIPT_DIR.joinpath(source_file.name)
    source_sftp_client.get(str(source_file), str(local_temp_file))
    target_sftp_client.put(str(local_temp_file), str(target_file))
    os.remove(local_temp_file)


def _grant_jenkins_master_ssh_access_to_jenkins_linux_slaves(config):
    """
    Creates an authorized-keys file on all jenkins slave containers
    that contains the public key of the master.
    """
    master_host_connection = _get_jenkins_master_host_connection(config)
    master_container = config.jenkins_master_host_config.container_conf.container_name
    public_key_file_master_host = master_host_connection.temp_dir.joinpath(
        _get_public_key_filename(master_container)
        )

    for slave_config in config.jenkins_slave_configs:
        if config.is_linux_machine(slave_config.machine_id):
            slave_connection = config.get_host_machine_connection(slave_config.machine_id)
            authorized_keys_file = _JENKINS_HOME_JENKINS_SLAVE_CONTAINER.joinpath('.ssh/authorized_keys')
            # add the masters public key to the authorized keys file of the slave
            _rtocontainercopy(master_host_connection, slave_connection, slave_config.container_conf, public_key_file_master_host, authorized_keys_file)
            # authenticate the slave ssh host with the master
            _accept_remote_container_host_key(
                master_host_connection, 
                config.jenkins_master_host_config.container_conf, 
                slave_connection, 
                slave_config.container_conf.mapped_ssh_host_port, 
                slave_config.container_conf.container_user
                )



def _rtocontainercopy(source_host_connection, target_host_connection, container_conf, source_file, target_file):
    """
    Copies the source_file from a host machine to the target target path target_file on a container.
    """
    with source_host_connection.ssh_client.open_sftp() as source_sftp_client:
        with target_host_connection.ssh_client.open_sftp() as target_sftp_client:
            temp_path_container_host = target_host_connection.temp_dir.joinpath(source_file.name)
            _rtorcopy(source_sftp_client, target_sftp_client, source_file, temp_path_container_host)
            _copy_file_from_host_to_container(target_host_connection, container_conf, temp_path_container_host, target_file)


def _container_to_container_copy(source_host_connection, source_container_conf, target_host_connection, target_container_conf, source_file, target_file):
    """
    Copies a file from one container to another.
    """
    # copy from source container to source host
    temp_path_source_host = source_host_connection.temp_dir.joinpath(source_file.name)
    source_host_connection.run_command('docker cp {0}:{1} {2}'.format(source_container_conf.container_name, source_file, temp_path_source_host))

    # copy from source host to target container
    _rtocontainercopy(source_host_connection, target_host_connection, target_container_conf, temp_path_source_host, target_file)


def _accept_remote_container_host_key(client_container_host_connection, client_container_config, host_host_connection, ssh_port, host_container_user):
    """
    Opens a ssh connection from the client container to the host container and thereby accepting the hosts ssh key.
    """
    _run_command_in_container(
        client_container_host_connection,
        client_container_config,
        'ssh -oStrictHostKeyChecking=no -p {0} {1}@{2} "echo dummy"'.format(ssh_port, host_container_user, host_host_connection.host_name)
    )

def _grant_jenkins_master_ssh_access_to_jenkins_windows_slaves(config):
    for slave_config in config.jenkins_slave_configs:
        if config.is_windows_machine(slave_config.machine_id):
            slave_connection = config.get_host_machine_connection(slave_config.machine_id)
            _grant_jenkins_master_ssh_access_to_jenkins_windows_slave(config, slave_connection)


def _grant_jenkins_master_ssh_access_to_jenkins_windows_slave(config, slave_host_connection ):

    master_container = config.jenkins_master_host_config.container_conf.container_name
    print(("----- Grant {0} ssh access to {1}").format(master_container, slave_host_connection.host_name))

    # configure the script for adding an authorized key to the bitwise ssh server on the
    # windows machine
    authorized_keys_script = 'updateAuthorizedKeysBitvise.bat'
    full_authorized_keys_script = _SCRIPT_DIR.joinpath(authorized_keys_script)

    master_connection = _get_jenkins_master_host_connection(config)
    public_key_file_master = _JENKINS_HOME_JENKINS_MASTER_CONTAINER.joinpath('.ssh/' + _get_public_key_filename(master_container) )
    public_key = _run_command_in_container(
        master_connection,
        config.jenkins_master_host_config.container_conf,
        'cat {0}'.format(public_key_file_master)
    )[0]

    configure_file(str(full_authorized_keys_script) + '.in', full_authorized_keys_script, {
        '@PUBLIC_KEY@' : public_key,
        '@JENKINS_MASTER_CONTAINER@' : master_container,
        '@SLAVE_MACHINE_USER@' : slave_host_connection.user_name,
    })

    # copy the script to the windows slave machine
    ssh_dir = PureWindowsPath('C:/Users/' + slave_host_connection.user_name + '/.ssh')
    full_script_path_on_slave = ssh_dir.joinpath(full_authorized_keys_script.name)
    with slave_host_connection.ssh_client.open_sftp() as sftp_client:
        sftp_client.put(str(full_authorized_keys_script), str(full_script_path_on_slave))

    # call the script
    try:
        call_script_command = '{0} {1}'.format(full_script_path_on_slave, slave_host_connection.user_password)
        slave_host_connection.run_command(call_script_command, print_command=True)
    except Exception as err:
        print(
            "Error: Updating the authorized ssh keys on "
            + slave_host_connection.host_name + " failed. Was the password correct?")
        raise err

    # clean up the generated script because of the included password
    os.remove(full_authorized_keys_script)

    # Wait a little until the bitvise ssh server is ready to accept the key file.
    # This can possibly fail on slower machines.
    time.sleep(1)

    # Add the slave to the known hosts
    try:
        _accept_remote_container_host_key(
            master_connection, 
            config.jenkins_master_host_config.container_conf, 
            slave_host_connection, 
            22, 
            slave_host_connection.user_name
            )
    except Exception as err:
        # This is not really clean but I can not think of a better solution now.
        print("When this call fails, it is possible that the waiting time before using the ssh connection to the Bitvise SSH server is too short.")
        raise err

def _read_file_content(filename):
    with open(filename) as open_file:
        return open_file.read()


def _grant_jenkins_master_ssh_access_to_web_server(config):

    master_container_config = config.jenkins_master_host_config.container_conf
    master_container = master_container_config.container_name
    master_public_key_file = _JENKINS_HOME_JENKINS_MASTER_CONTAINER.joinpath('.ssh/' + _get_public_key_filename(master_container))
    master_host_connection = _get_jenkins_master_host_connection(config)
    
    authorized_keys_file = PurePosixPath('/root/.ssh/authorized_keys')
    webserver_host_connection = config.get_host_machine_connection(config.web_server_host_config.machine_id)
    webserver_container_config = config.web_server_host_config.container_conf

    # set the authorized keys file in the webserver container
    _container_to_container_copy(
        master_host_connection, 
        master_container_config, 
        webserver_host_connection, 
        webserver_container_config, 
        master_public_key_file, 
        authorized_keys_file
    )
    
    # we need to change the file owner from jenkins to root
    commands = [
        'chown root:root ' + str(authorized_keys_file),
        'chmod 600 ' + str(authorized_keys_file),
        'service ssh start',
    ]
    _run_commands_in_container(
        webserver_host_connection,
        webserver_container_config,
        commands
    )

    # Add doc-server as known host to prevent the authentication request on the first connect
    _accept_remote_container_host_key(
        master_host_connection, 
        master_container_config, 
        webserver_host_connection, 
        webserver_container_config.mapped_ssh_host_port, 
        webserver_container_config.container_user
    )


def _create_rsa_key_file_pairs_on_slave_container(config):
    for slave_config in config.jenkins_slave_configs:
        if config.is_linux_machine(slave_config.machine_id):
            _create_rsa_key_file_pair_on_container(
                config,
                slave_config.container_conf,
                PurePosixPath('/home/jenkins')
            )


def _grant_linux_slaves_access_to_repository(config):
    for slave_config in config.jenkins_slave_configs:
        if config.is_linux_machine(slave_config.machine_id):
            _grant_container_ssh_access_to_repository(
                config,
                slave_config.container_conf,
                PurePosixPath('/home/jenkins')
            )


def _configure_jenkins_master(config, config_file):
    if not config.jenkins_config.use_unconfigured_jenkins:
        print("----- Configure the jenkins master server.")

        _configure_general_jenkins_options(config)
        _configure_jenkins_users(config, config_file)
        _configure_jenkins_jobs(config, config_file)
        slaveStartCommands = _configure_jenkins_slaves(config)
        config.jenkins_config.approved_system_commands.extend(slaveStartCommands)

        # restart jenkins to make sure it as the desired configuration
        # this is required because approveing the slaves scripts requires jenkins to be
        # up and running.
        _restart_jenkins(config)

        # Approve system commands
        _approve_jenkins_system_commands(config)

        # Approve script signatures
        _approve_jenkins_script_signatures(config)

    else:
        print(
            "Jenkins will be run without the default configuration," +
            " because no user files were given.")


def _configure_general_jenkins_options(config):
    """
    Configure the general options by copying the .xml config files from the JenkinsConfig
    directory to the jenkins master home directory.
    """
    _copy_local_textfile_tree_to_container(
        _SCRIPT_DIR.joinpath('JenkinsConfig'), 
        _get_jenkins_master_host_connection(config), 
        config.jenkins_master_host_config.container_conf, 
        _JENKINS_HOME_JENKINS_MASTER_CONTAINER
    )


def _copy_local_textfile_tree_to_container(local_source_dir, container_host_connection, container_config, container_target_dir):
    """
    Copy the contents of a local directory to a container directory.
    """
    dir_content = _get_dir_content(local_source_dir)
    with container_host_connection.ssh_client.open_sftp() as sftp_client:
        for item in dir_content:
            source_path = local_source_dir.joinpath(item)
            if os.path.isfile(source_path):
                target_path = container_target_dir.joinpath(item)
                _copy_textfile_to_container(container_host_connection, sftp_client, container_config, source_path, target_path)
            

def _get_dir_content(directory):
    """
    Returns a list of all files and directories in a directory with pathes relative to the given directory.
    """
    items = []
    for dirpath, dirs, files in os.walk(directory):
        relpath = PurePath(dirpath).relative_to(directory)
        for dir in dirs:
            items.append(relpath.joinpath(dir))
        for file in files:
            items.append(relpath.joinpath(file))
    return items


def _configure_jenkins_users(config, config_file):
    """
    Copy user config xml files to user/<username>/config.xml
    """
    _copy_jenkins_config_files(config, config_file, 'users', config.jenkins_config.account_config_files )


def _configure_jenkins_jobs(config, config_file):
    """
    copy job config xml files to jobs/<jobname>/config.xml
    """
    _copy_jenkins_config_files(config, config_file, 'jobs', config.jenkins_config.job_config_files)


def _copy_jenkins_config_files(config, config_file, config_dir, config_items):
    """
    Copies the config.xml files that are mentioned in a map under filesConfigKey
    in the script config file to named directories under the given config dir
    to the jenkins-master home directory.
    """
    master_connection = _get_jenkins_master_host_connection(config)
    with master_connection.ssh_client.open_sftp() as sftp_client:
        config_file_dir = config_file.parent
        jobs_config_dir = _JENKINS_HOME_JENKINS_MASTER_CONTAINER.joinpath(config_dir)
        for config_item in config_items:
            if config_file_dir:
                sourceconfig_file = config_file_dir.joinpath(config_item.xml_file)
            else:
                sourceconfig_file = config_item.xml_file
            job_config_dir = jobs_config_dir.joinpath(config_item.name)
            job_config_file = PurePosixPath('config.xml')
            _copy_textfile_to_container(
                master_connection,
                sftp_client,
                config.jenkins_master_host_config.container_conf,
                sourceconfig_file,
                job_config_dir.joinpath(job_config_file)
            )


def _restart_jenkins(config):
    master_connection = _get_jenkins_master_host_connection(config)
    master_container = config.jenkins_master_host_config.container_conf.container_name
    _stop_docker_container(master_connection, master_container)
    _start_docker_container(master_connection, master_container)
    _wait_for_jenkins_master_to_come_online(config)


def _wait_for_jenkins_master_to_come_online(config):
    """
    Returns when the jenkins instance is fully operable.

    We wait for the crumb request to work, because this is what we need next.
    """
    print("----- Wait for jenkins to come online")
    # We have to wait a little or we get python exceptions.
    # This is ugly, because it can still fail on slower machines.
    time.sleep(10)
    master_connection = _get_jenkins_master_host_connection(config)
    crumb_text = "Jenkins-Crumb"
    url = 'http://{0}:8080/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,":",//crumb)'.format(master_connection.host_name)
    auth = (config.jenkins_config.admin_user, config.jenkins_config.admin_user_password)

    text = ''
    max_time = 30
    waited_time = 0
    time_delta = 1
    while crumb_text not in text:
        text = requests.get(url, auth=auth).text
        waited_time += time_delta
        time.sleep(time_delta)
        if waited_time > max_time:
            break


def _configure_jenkins_slaves(config):
    """
    Create config files for the slave nodes.
    All slave nodes are based on the ssh command execution start scheme from
    the command-launcher plugin.
    """
    print("----- Configure jenkins slave nodes")

    start_commands = []

    for slave_config in config.jenkins_slave_configs:
        slave_host_connection = config.get_host_machine_connection(slave_config.machine_id)
        if config.is_linux_machine(slave_config.machine_id):
            # create config file for the linux slave
            linux_slave_start_command = _get_slave_start_command(
                slave_host_connection,
                slave_config.container_conf.container_user,
                slave_config.container_conf.mapped_ssh_host_port,
                '/home/jenkins/bin'
            )
            _configure_node_config_file(
                config,
                slave_config.slave_name,
                'A Debian 8.9 build slave based on a docker container.',
                '/home/{0}/workspaces'.format(slave_config.container_conf.container_user),
                linux_slave_start_command,
                _get_slave_labels_string('Debian-8.9', 10),
                slave_config.executors
            )
            start_commands.append(linux_slave_start_command)

        elif config.is_windows_machine(slave_config.machine_id):
            # create config file for the windows slave
            slave_workspace = 'C:/jenkins'
            windows_slave_start_command = _get_slave_start_command(
                slave_host_connection,
                slave_host_connection.user_name,
                22,
                slave_workspace
            )
            _configure_node_config_file(
                config,
                slave_config.slave_name,
                'A Windows 10 build slave based on a virtual machine.',
                slave_workspace,
                windows_slave_start_command,
                _get_slave_labels_string('Windows-10', 10),
                slave_config.executors
            )
            start_commands.append(windows_slave_start_command)

        else:
            raise Exception('Function misses case for operating system of slave ' + slave_config.machine_id)

    return start_commands


def _get_slave_start_command(host_connection, slave_user, ssh_port, slave_jar_dir):
    """
    defines the command that is used to start the slaves via ssh.
    """
    start_command = (
        'ssh {0}@{1} -p {2} java -jar {3}/slave.jar'
        ).format(slave_user , host_connection.host_name, ssh_port, slave_jar_dir)
    return start_command


def _get_slave_labels_string(base_label_name, max_index):
    labels = []
    # We add multiple labels with indexes, because the jenkins pipeline model
    # requires a label for each node-name and node-names need to be different
    # for nodes that are run in parallel.
    for i in range(max_index + 1):
        # The version must be in the label, to make sure that we can change
        # the nodes and still build old versions of a package no the old nodes.
        labels.append(base_label_name + '-' + cpfmachines_version.CPFMACHINES_VERSION + '-' + str(i))
    return ' '.join(labels)


def _configure_node_config_file(
        config,
        slave_name,
        description,
        slave_workspace_dir,
        start_command,
        slave_labels,
        executors):
    """
    Uses a template file to create a config.xml file for a jenkins node that the master
    controls via ssh.
    """
    
    temp_dir = _SCRIPT_DIR.joinpath('temp')
    _clear_dir(temp_dir)

    createdconfig_file = temp_dir.joinpath('config.xml')
    config_template_file = _SCRIPT_DIR.joinpath('jenkinsSlaveNodeConfig.xml.in')

    # create a local config file
    configure_file(config_template_file, createdconfig_file, {
        '$SLAVE_NAME' : slave_name,
        '$DESCRIPTION' : description,
        '$WORKSPACE' : slave_workspace_dir,
        '$START_COMMAND' : start_command,
        '$LABELS' : slave_labels,
        '$EXECUTORS' : str(executors),
    })

    # copy the file to the master container
    master_connection = _get_jenkins_master_host_connection(config)
    with master_connection.ssh_client.open_sftp() as sftp_client:
        nodes_dir = _JENKINS_HOME_JENKINS_MASTER_CONTAINER.joinpath('nodes')
        node_dir = nodes_dir.joinpath(slave_name)
        target_file = node_dir.joinpath(createdconfig_file.name)
        _copy_textfile_to_container(
            master_connection,
            sftp_client,
            config.jenkins_master_host_config.container_conf,
            createdconfig_file,
            target_file
        )

    _clear_dir(temp_dir)


def _clear_dir(directory):
    """
    After calling this function the directory will exist and be empty.
    """
    if os.path.isdir(directory):
        shutil.rmtree(directory)
    os.makedirs(directory)


def _approve_jenkins_system_commands(config):
    """
    Approve system commands that are required by the jenkins configuration.
    """
    print("----- Approve system-commands")
    pprint.pprint(config.jenkins_config.approved_system_commands)

    master_connection = _get_jenkins_master_host_connection(config)
    jenkins_user = config.jenkins_config.admin_user
    jenkins_admin_password = config.jenkins_config.admin_user_password
    jenkins_crumb = _get_jenkins_crumb(master_connection.host_name, jenkins_user, jenkins_admin_password)

    for command in config.jenkins_config.approved_system_commands:
        _approve_jenkins_system_command(
            master_connection.host_name,
            jenkins_user,
            jenkins_admin_password,
            jenkins_crumb,
            command
        )


def _get_jenkins_crumb(master_host, jenkins_user, jenkins_password):
    url = 'http://{0}:8080/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,":",//crumb)'.format(master_host)
    auth = (jenkins_user, jenkins_password)
    request = requests.get(url, auth=auth)
    request.raise_for_status()
    return request.text


def _approve_jenkins_system_command(master_host, jenkins_user, jenkins_password, jenkins_crumb, approved_script_text):
    """
    Runs a groovy script over the jenkins groovy console, that approves system-command
    scipts.
    """

    groovy_script = (
        "def scriptApproval = Jenkins.instance.getExtensionList('org.jenkinsci.plugins.scriptsecurity.scripts.ScriptApproval')[0];" +
        "scriptApproval.approveScript(scriptApproval.hash('{0}', 'system-command'))"
        ).format(approved_script_text)
    _run_jenkins_groovy_script(master_host, jenkins_user, jenkins_password, jenkins_crumb, groovy_script)


def _run_jenkins_groovy_script(master_host, jenkins_user, jenkins_password, jenkins_crumb, script):
    """
    Runs the given script in the jenkins script console.
    """
    url = 'http://{0}:8080/scriptText'.format(master_host)
    auth = (jenkins_user, jenkins_password)
    crumb_parts = jenkins_crumb.split(':')
    crumb_header = {crumb_parts[0] : crumb_parts[1]}
    script_data = {'script' : script}

    response = requests.post(url, auth=auth, headers=crumb_header, data=script_data)
    response.raise_for_status()


def _approve_jenkins_script_signatures(config):
    """
    Approve script signatures that are required by the pipeline scripts.
    """
    print("----- Approve script signatures")
    pprint.pprint(config.jenkins_config.approved_script_signatures)

    master_connection = _get_jenkins_master_host_connection(config)
    jenkins_user = config.jenkins_config.admin_user
    jenkins_admin_password = config.jenkins_config.admin_user_password
    jenkins_crumb = _get_jenkins_crumb(master_connection.host_name, jenkins_user, jenkins_admin_password)

    for script_signature in config.jenkins_config.approved_script_signatures:
        _approve_jenkins_script_signature(
            master_connection.host_name, 
            jenkins_user, 
            jenkins_admin_password, 
            jenkins_crumb, 
            script_signature
        )


def _approve_jenkins_script_signature(master_host, jenkins_user, jenkins_password, jenkins_crumb, approved_script_text):
    """
    Runs a groovy script over the jenkins groovy console, that approves the commands
    that are used to start the slaves.
    """
    groovy_script = (
        "def signature = '{0}';" +
        "org.jenkinsci.plugins.scriptsecurity.scripts.ScriptApproval.get().approveSignature(signature)"
    ).format(approved_script_text)
    _run_jenkins_groovy_script(master_host, jenkins_user, jenkins_password, jenkins_crumb, groovy_script)



if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
