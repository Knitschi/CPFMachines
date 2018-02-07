#!/usr/bin/env python3

# This script removes and adds and starts all docker container of the CMakeProjectFramework infrastructure.
#
# Arguments:
# 1. - The path to a configuration json file.
# (An empty file can be generated with the createEmptyconfig_files.py script)


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
    Entry point of the scrpit.
    """
    # read configuration file
    print('----- Read configuration file ' + config_file)
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
    """
    _grant_jenkins_master_ssh_access_to_jenkins_windows_slave(
        config_values,
        jenkins_slave_machine_windows_password)
    _grant_jenkins_master_ssh_access_to_web_server(config_values)

    # setup ssh accesses used by jenkins-slave-linux
    _create_rsa_key_file_pair_on_container(
        _FULL_LINUX_JENKINS_SLAVE_NAME,
        _JENKINS_HOME_JENKINS_SLAVE_CONTAINER)
    _grant_container_ssh_access_to_repository(
        _FULL_LINUX_JENKINS_SLAVE_NAME,
        _JENKINS_HOME_JENKINS_SLAVE_CONTAINER, config_values)

    _configure_jenkins_master(config_values, config_file, jenkins_admin_password)
    """

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
    _clear_directory(config, config.jenkins_master_host_config.machine_id, config.jenkins_master_host_config.jenkins_home_share)
    # all temporary directories
    for connection in config.host_machine_connections:
        if connection.temp_dir:
            _clear_directory(config, connection.machine_id, connection.temp_dir)


def _clear_directory(config, machine_id, directory):
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
    connection = config.get_host_machine_connection(config.jenkins_master_host_config.machine_id)

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


def _get_context_dir(connection, image_name):
    return connection.temp_dir.joinpath(image_name)


def _create_build_context_dir(config, connection, source_dir, context_dir, files):
    """
    context_dir is the directory on the host that is used as a build context for the container.
    source_dir is the absolute directory on the machine executing the script that contains the files
    required for building the container.
    """
    with connection.ssh_client.open_sftp() as sftp_client:

        source_dir = PurePath(source_dir)

        # copy files to the host
        for file_path in files:
            source_path = source_dir.joinpath(file_path)
            target_path = context_dir.joinpath(file_path)
            # Copy the file.
            _copy_textfile_from_local_to_linux(connection, sftp_client, source_path, target_path)


def _copy_textfile_from_local_to_linux(connection, sftp_client, source_path, target_path):
    """
    This function ensures that the file-endings of the text-file are set to linux
    convention after the copy.
    """
    # make sure a directory for the target file exists
    _rmakedirs(sftp_client, target_path.parent)
    sftp_client.put( str(source_path), str(target_path) )
    # Remove \r from file from windows line endings.
    # This may be necessary when the machine that executes this script
    # is a windows machine.
    temp_file = target_path.parent.joinpath('temp.txt')
    format_line_endings_command = "tr -d '\r' < '{0}' > '{1}' && mv {1} {0}".format(str(target_path), str(temp_file))
    connection.run_command(format_line_endings_command)


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

    connection = config.get_host_machine_connection(config.jenkins_master_host_config.machine_id)
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
    _run_command_in_container(
        connection,
        container_name,
        'git config --global user.email not@valid.org')
    _run_command_in_container(
        connection,
        container_name,
        'git config --global user.name jenkins')


def _run_command_in_container(connection, container, command, user=None):
    user_option = ''
    if user:
        user_option = '--user ' + user + ':' + user + ' '
    command = 'docker exec ' + user_option + container + ' ' + command
    return connection.run_command(command, print_command=True)


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
    _run_command_in_container(
        connection,
        container_name,
        'rm -fr ' + str(cgi_bin_dir),
        'root')
    _run_command_in_container(
        connection,
        container_name,
        'mkdir ' + str(cgi_bin_dir),
        'root')
    _run_command_in_container(
        connection,
        container_name,
        'mkdir ' + str(cgi_bin_dir) + '/doxysearch.db',
        'root')
    _run_command_in_container(
        connection,
        container_name,
        'cp -r -f /usr/local/bin/doxysearch.cgi ' + str(cgi_bin_dir),
        'root')


def _build_and_start_jenkins_linux_slaves(config):
    for slave_config in config.jenkins_slave_configs:
        if slave_config.container_conf.container_name:
            _build_and_start_jenkins_linux_slave(config, slave_config.container_conf, slave_config.machine_id)


def _build_and_start_jenkins_linux_slave(config, container_conf, machine_id):
    
    connection = config.get_host_machine_connection(machine_id)
    container_image = container_conf.container_image_name

    if not _docker_container_image_exists(connection, container_image):
        # create build context
        docker_file = 'DockerfileJenkinsSlaveLinux'
        files = [
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
            'slave.jar',
        ]
        context_dir = _get_context_dir(connection, container_image)
        _create_build_context_dir(config, connection, _SCRIPT_DIR, context_dir, files)

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
        _copy_file_to_container(connection, sftp_client, container_conf, _SCRIPT_DIR, container_home_directory, _CREATEKEYPAIR_SCRIPT)

    # This will create the key-pair on the container.
    # We need to do this in the container or ssh will not accept the private key file.
    _run_command_in_container(
        connection,
        container_conf.container_name,
        '/bin/bash ' + str(container_home_directory.joinpath(_CREATEKEYPAIR_SCRIPT)) + ' ' + container_conf.container_name,
        'jenkins')


def _copy_file_to_container(connection, sftp_client, container_conf, source_path, container_path, file_name):
    """
    We first copy the file to the hosts context directory and then to the container.
    """
    local_file = source_path.joinpath(file_name)
    context_dir = _get_context_dir(connection, container_conf.container_image_name)
    host_file = context_dir.joinpath(file_name)
    container_file = container_path.joinpath(file_name)

    _copy_textfile_from_local_to_linux(connection, sftp_client, local_file, host_file)
    _copy_file_from_host_to_container(connection, container_conf, host_file, container_file)
    

def _copy_file_from_host_to_container(host_connection, container_conf, source_file, target_file):
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
        _copy_file_to_container(container_host_connection, sftp_client, container_conf, _SCRIPT_DIR, container_home_directory, _ADDKNOWNHOST_SCRIPT)
        _run_command_in_container(
            container_host_connection,
            container_name,
            '/bin/bash '+ str(container_home_directory.joinpath(_ADDKNOWNHOST_SCRIPT)) + ' ' + repository_connection.host_name + ' 22',
            'jenkins')

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
    master_host_connection = config.get_host_machine_connection(config.jenkins_master_host_config.machine_id)
    public_key_file_master_host = master_host_connection.temp_dir.joinpath(
        _get_public_key_filename(config.jenkins_master_host_config.container_conf.container_name)
        )

    for slave_config in config.jenkins_slave_configs:
        if config.is_linux_machine(slave_config.machine_id):
            slave_connection = config.get_host_machine_connection(slave_config.machine_id)
            authorized_keys_file = _JENKINS_HOME_JENKINS_SLAVE_CONTAINER.joinpath('.ssh/authorized_keys')
            
            rtocontainercopy(master_host_connection, slave_connection, slave_config.container_conf, public_key_file_master_host, authorized_keys_file)

            # Add slave as known host to prevent the authentication request on the first connect
            _add_remote_to_known_ssh_hosts_of_jenkins_master(config, slave_connection.host_name, slave_config.container_conf.mapped_ssh_host_port)


def rtocontainercopy(source_host_connection, target_host_connection, container_conf, source_file, target_file):
    """
    Copies the source_file from a host machine to the target target path target_file on a container.
    """
    with source_host_connection.ssh_client.open_sftp() as source_sftp_client:
        with target_host_connection.ssh_client.open_sftp() as target_sftp_client:
            temp_path_container_host = target_host_connection.temp_dir.joinpath(source_file.name)
            _rtorcopy(source_sftp_client, target_sftp_client, source_file, temp_path_container_host)
            _copy_file_from_host_to_container(target_host_connection, container_conf, temp_path_container_host, target_file)


def _add_remote_to_known_ssh_hosts_of_jenkins_master(config, remote_host, port):
    """
    remoteMachine can be an IP or machine name.
    """
    connection = config.get_host_machine_connection(config.jenkins_master_host_config.machine_id)
    runScriptCommand = ('/bin/bash ' + str(_JENKINS_HOME_JENKINS_MASTER_CONTAINER.joinpath(_ADDKNOWNHOST_SCRIPT)) + ' ' + remote_host + ' ' + str(port))
    
    _run_command_in_container(
        connection,
        config.jenkins_master_host_config.container_conf.container_name,
        runScriptCommand,
        'jenkins')


def _grant_jenkins_master_ssh_access_to_jenkins_windows_slave(config_values, jenkins_slave_machine_windows_password):

    jenkins_workspace_host = config_values['HostJenkinsMasterShare']
    jenkins_slave_machine_windows = config_values['BuildSlaveWindowsMachine']
    jenkins_slave_machine_windows_user = config_values['BuildSlaveWindowsMachineUser']

    print(("----- Grant {0} ssh access to {1}").format(_JENINS_MASTER_CONTAINER, jenkins_slave_machine_windows))

    # configure the script for adding an authorized key to the bitwise ssh server on the
    # windows machine
    authorized_keys_script = 'updateAuthorizedKeysBitvise.bat'
    full_authorized_keys_script = _SCRIPT_DIR + '/' + authorized_keys_script
    public_key_file = jenkins_workspace_host +'/'+_JENINS_MASTER_CONTAINER+ _PUBLIC_KEY_FILE_POSTFIX
    public_key = _read_file_content(public_key_file)
    public_key = public_key.replace('\n', '').replace('\r', '')  # remove the line end from the key
    configure_file(full_authorized_keys_script + '.in', full_authorized_keys_script, {
        '@PUBLIC_KEY@' : public_key,
        '@JENKINS_MASTER_CONTAINER@' : _JENINS_MASTER_CONTAINER,
        '@SLAVE_MACHINE_USER@' : jenkins_slave_machine_windows_user,
    })

    # copy the script for to the windows slave machine
    ssh_dir = 'C:/Users/' + jenkins_slave_machine_windows_user + '/.ssh'
    copy_script_command = 'scp {0} {1}@{2}:{3}'.format(
        full_authorized_keys_script,
        jenkins_slave_machine_windows_user,
        jenkins_slave_machine_windows,
        ssh_dir)
    _run_command(copy_script_command)

    # call the script
    full_script_path_on_slave = ssh_dir + '/' + authorized_keys_script
    call_script_command = (
        'ssh {0}@{1} "{2} {3}"'
    ).format(
        jenkins_slave_machine_windows_user,
        jenkins_slave_machine_windows,
        full_script_path_on_slave,
        jenkins_slave_machine_windows_password,
    )
    try:
        _run_command(call_script_command, print_command=True, print_output=True)
    except Exception as err:
        print(
            "Error: Updating the authorized ssh keys on "
            + jenkins_slave_machine_windows + " failed. Was the password correct?")
        raise err

    # clean up the generated script because of the included password
    os.remove(full_authorized_keys_script)

    # Add the slave to the known hosts
    _add_remote_to_known_ssh_hosts_of_jenkins_master(jenkins_slave_machine_windows)


def _read_file_content(filename):
    with open(filename) as open_file:
        return open_file.read()


def _grant_jenkins_master_ssh_access_to_web_server(config_values):

    jenkins_workspace_host = config_values['HostJenkinsMasterShare']

    authorized_keys_file = '/root/.ssh/authorized_keys'
    public_key_file = _JENINS_MASTER_CONTAINER + _PUBLIC_KEY_FILE_POSTFIX

    _run_command('docker cp {0}/{1} {2}:{3}'.format(
        jenkins_workspace_host,
        public_key_file,
        _WEBSERVER_CONTAINER,
        authorized_keys_file))
    _run_command_in_container(_WEBSERVER_CONTAINER, 'chown root:root ' + authorized_keys_file)
    _run_command_in_container(_WEBSERVER_CONTAINER, 'chmod 600 ' + authorized_keys_file)
    _run_command_in_container(_WEBSERVER_CONTAINER, 'service ssh start')

    # Add doc-server as known host to prevent the authentication request on the first connect
    _add_remote_to_known_ssh_hosts_of_jenkins_master(_WEBSERVER_CONTAINERIP)


def _configure_jenkins_master(config_values, config_file, jenkins_admin_password):
    if not config_values['UseUnconfiguredJenkinsMaster']:
        print("----- Configure the jenkins master server.")

        _set_general_jenkins_options(config_values)
        _set_jenkins_users(config_values, config_file)
        _set_jenkins_jobs(config_values, config_file)
        slaveStartCommands = _set_jenkins_slaves(config_values)

        # restart jenkins to make sure it as the desired configuration
        # this is required because approveing the slaves scripts requires jenkins to be
        # up and running.
        _stop_docker_container(_JENINS_MASTER_CONTAINER)
        _start_docker_container(_JENINS_MASTER_CONTAINER)
        _wait_for_jenkins_master_to_come_online(config_values, jenkins_admin_password)

        # Approve system commands
        system_commands = config_values['JenkinsApprovedSystemCommands']
        system_commands.extend(slaveStartCommands)
        _approve_jenkins_system_commands(config_values, jenkins_admin_password, system_commands)

        # Approve script signatures
        script_signatures = config_values['JenkinsApprovedScriptSignatures']
        _approve_jenkins_script_signatures(config_values, jenkins_admin_password, script_signatures)

    else:
        print(
            "Jenkins will be run without the default conifiguration," +
            " because no user files were given.")


def _set_general_jenkins_options(config_values):
    """
    Configure the general options by copying the .xml config files from the JenkinsConfig
    directory to the jenkins master home directory.
    """
    jenkins_workspace_host = config_values['HostJenkinsMasterShare']
    distutils.dir_util.copy_tree(_SCRIPT_DIR + '/JenkinsConfig', jenkins_workspace_host)


def _set_jenkins_users(config_values, config_file):
    """
    Copy user config xml files to user/<username>/config.xml
    """
    _copy_jenkins_config_files(config_values, config_file, 'users', 'JenkinsAccountConfigFiles')


def _set_jenkins_jobs(config_values, config_file):
    """
    copy job config xml files to jobs/<jobname>/config.xml
    """
    _copy_jenkins_config_files(config_values, config_file, 'jobs', 'JenkinsJobConfigFiles')


def _copy_jenkins_config_files(config_values, config_file, config_dir, files_config_key):
    """
    Copies the config.xml files that are mentioned in a map under filesConfigKey
    in the script config file to named directories under the given config dir
    to the jenkins-master home directory.
    """
    jenkins_workspace_host = config_values['HostJenkinsMasterShare']
    config_file_dir = os.path.dirname(config_file)
    jobs_config_dir = jenkins_workspace_host + '/' + config_dir
    for job, jobconfig_file in config_values[files_config_key].items():
        if config_file_dir:
            sourceconfig_file = config_file_dir + '/' + jobconfig_file
        else:
            sourceconfig_file = jobconfig_file
        job_config_dir = jobs_config_dir + '/' + job
        os.makedirs(job_config_dir)
        shutil.copyfile(sourceconfig_file, job_config_dir + '/config.xml')


def _wait_for_jenkins_master_to_come_online(config_values, jenkins_password):
    """
    Returns when the jenkins instance is fully operable.

    We wait for the crumb request to work, because this is what we need next.
    """
    print("----- Wait for jenkins to come online")
    # We have to whait a little or we get python exceptions.
    # This is ugly, because it can still fail on slower machines.
    time.sleep(10)
    crumb_text = "Jenkins-Crumb"
    url = 'http://localhost:8080/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,":",//crumb)'
    auth = (config_values['JenkinsAdminUser'], jenkins_password)

    text = ''
    while crumb_text not in text:
        text = requests.get(url, auth=auth).text
        time.sleep(1)


def _set_jenkins_slaves(config_values):
    """
    Create config files for the slave nodes.
    All slave nodes are based on the ssh command execution start scheme from
    the command-launcher plugin.
    """
    print("----- Configure jenkins slave nodes")

    start_commands = []

    # create config file for the linux slave
    linux_slave_start_command = _get_slave_start_command(
        _JENKINS_LINUX_SLAVE_CONTAINER_IP,
        'jenkins',
        '~/bin')
    _configure_node_config_file(
        config_values,
        _FULL_LINUX_JENKINS_SLAVE_NAME,
        'A Debinan 8.9 build slave based on a docker container.',
        '/home/jenkins/workspaces',
        linux_slave_start_command,
        _get_slave_labels_string('Debian-8.9', 10)
    )
    start_commands.append(linux_slave_start_command)

    # create config file for the windows slave
    slave_workspace = 'C:/jenkins'
    windows_slave_start_command = _get_slave_start_command(
        config_values['BuildSlaveWindowsMachine'],
        config_values['BuildSlaveWindowsMachineUser'],
        slave_workspace)
    _configure_node_config_file(
        config_values,
        _FULL_WINDOWS_JENKINS_SLAVE_NAME,
        'A Windows 10 build slave based on a virtual machine.',
        slave_workspace,
        windows_slave_start_command,
        _get_slave_labels_string('Windows-10', 10)
    )
    start_commands.append(windows_slave_start_command)

    return start_commands


def _get_slave_start_command(slave_host_machine, slave_machine_user, slave_jar_dir):
    """
    defines the command that is used to start the slaves via ssh.
    """
    start_command = (
        'ssh {0}@{1} -p {2} java -jar {3}/slave.jar'
        ).format(slave_machine_user, slave_host_machine, mapped_ssh_port, slave_jar_dir)
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
        config_values,
        slave_name,
        description,
        slave_workspace_dir,
        start_command,
        slave_labels):
    """
    Uses a template file to create a config.xml file for a jenkins node that the master
    controls via ssh.
    """
    nodes_dir = config_values['HostJenkinsMasterShare'] + '/nodes'
    node_dir = nodes_dir + '/' + slave_name
    _clear_directory(node_dir)

    createdconfig_file = node_dir + '/config.xml'
    config_template_file = _SCRIPT_DIR + '/jenkinsSlaveNodeConfig.xml.in'

    # create the config file in nodes
    configure_file(config_template_file, createdconfig_file, {
        '$SLAVE_NAME' : slave_name,
        '$DESCRIPTION' : description,
        '$WORKSPACE' : slave_workspace_dir,
        '$START_COMMAND' : start_command,
        '$LABELS' : slave_labels
    })


def _approve_jenkins_system_commands(config_values, jenkins_admin_password, commands):
    """
    Approve system commands that are required by the jenkins configuration.
    """
    print("----- Approve system-commands")
    pprint.pprint(commands)

    jenkins_user = config_values['JenkinsAdminUser']
    jenkins_crumb = _get_jenkins_crumb(jenkins_user, jenkins_admin_password)

    for command in commands:
        _approve_jenkins_system_command(jenkins_user, jenkins_admin_password, jenkins_crumb, command)


def _get_jenkins_crumb(jenkins_user, jenkins_password):
    url = 'http://localhost:8080/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,":",//crumb)'
    auth = (jenkins_user, jenkins_password)
    request = requests.get(url, auth=auth)
    request.raise_for_status()
    return request.text


def _approve_jenkins_system_command(jenkins_user, jenkins_password, jenkins_crumb, approved_script_text):
    """
    Runs a groovy script over the jenkins groovy console, that approves system-command
    scipts.
    """

    groovy_script = (
        "def scriptApproval = Jenkins.instance.getExtensionList('org.jenkinsci.plugins.scriptsecurity.scripts.ScriptApproval')[0];" +
        "scriptApproval.approveScript(scriptApproval.hash('{0}', 'system-command'))"
        ).format(approved_script_text)
    _run_jenkins_groovy_script(jenkins_user, jenkins_password, jenkins_crumb, groovy_script)


def _run_jenkins_groovy_script(jenkins_user, jenkins_password, jenkins_crumb, script):
    """
    Runs the given script in the jenkins script console.
    """
    url = 'http://localhost:8080/scriptText'
    auth = (jenkins_user, jenkins_password)
    crumb_parts = jenkins_crumb.split(':')
    crumb_header = {crumb_parts[0] : crumb_parts[1]}
    script_data = {'script' : script}

    response = requests.post(url, auth=auth, headers=crumb_header, data=script_data)
    response.raise_for_status()


def _approve_jenkins_script_signatures(config_values, jenkins_admin_password, script_signatures):
    """
    Approve script signatures that are required by the pipeline scripts.
    """
    print("----- Approve script signatures")
    pprint.pprint(script_signatures)

    jenkins_user = config_values['JenkinsAdminUser']
    jenkins_crumb = _get_jenkins_crumb(jenkins_user, jenkins_admin_password)

    for script_signature in script_signatures:
        _approve_jenkins_script_signature(jenkins_user, jenkins_admin_password, jenkins_crumb, script_signature)


def _approve_jenkins_script_signature(jenkins_user, jenkins_password, jenkins_crumb, approved_script_text):
    """
    Runs a groovy script over the jenkins groovy console, that approves the commands
    that are used to start the slaves.
    """
    groovy_script = (
        "def signature = '{0}';" +
        "org.jenkinsci.plugins.scriptsecurity.scripts.ScriptApproval.get().approveSignature(signature)"
    ).format(approved_script_text)
    _run_jenkins_groovy_script(jenkins_user, jenkins_password, jenkins_crumb, groovy_script)



if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
