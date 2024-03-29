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
import sys
import subprocess
import shutil
import io
import json
import pprint
import time
import paramiko
import socket
import getpass

# Add the script path to the python path
_SCRIPT_DIR = PurePath(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(str(_SCRIPT_DIR))

import cpfmachines_version
import config_data

from jenkins_remote_access import JenkinsRESTAccessor
from connections import ConnectionsHolder

import dockerutil
import fileutil



# Constants
# The version of the jenkins CI server that is installed on the jenkins-master machine.
_JENKINS_VERSION = '2.319.2'
# The sha256 checksum of the jenkins.war package of the given jenkins version.
# https://repo.jenkins-ci.org/public/org/jenkins-ci/main/jenkins-war/
# This is currently manually computed with "cmake -E sha256sum jenkins.war"
_JENKINS_SHA256 = '020c8db10469e20e22e68c81e7e83bf35ccb6a435b712c4b643851949e75a553'
_JENKINS_BASE_IMAGE = 'jenkins-image-' + _JENKINS_VERSION

# Files
_PUBLIC_KEY_FILE_POSTFIX = '_ssh_key.rsa.pub'
_CREATEKEYPAIR_SCRIPT = PurePath('createSSHKeyFilePair.sh')
_ADDKNOWNHOST_SCRIPT = PurePath('addKnownSSHHost.sh')
_ADDAUTHORIZEDKEYSBITWISESSH_SCRIPT = PurePath('addAuthorizedBitwiseSSHKey.bat')
_GIT_CREDENTIALS_STORE = PurePosixPath('.jenkins-git-credentials')


# directories on jenkins-slave-linux
_JENKINS_HOME_JENKINS_SLAVE_CONTAINER =  PurePosixPath('/home/jenkins')

# The address of the official CPFJenkinsjob repository.
# Is it good enough to have this hardcoded here?
_JENKINSJOB_REPOSITORY = 'https://github.com/Knitschi/CPFMachines.git'
_CPF_JOB_TEMPLATE_FILE = _SCRIPT_DIR.joinpath('config.xml.in')



def configure_file(source_file, dest_file, replacement_dictionary):
    """
    Searches in source_file for the keys in replacement_dictionary, replaces them
    with the values and writes the result to dest_file.
    """
    # Open target file
    config_file = io.open(str(dest_file), 'w')

    # Read the lines from the template, substitute the values, and write to the new config file
    for line in io.open(str(source_file), 'r'):
        for key, value in replacement_dictionary.items():
            line = line.replace(key, str(value))
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
    _get_https_repository_passwords(config)

    print('----- Establish ssh connections to host machines')
    connections = ConnectionsHolder(config.host_machine_infos)

    # Create the object that does the work.
    controller = MachinesController(config, connections)

    # prepare environment
    print('----- Cleanup existing docker container and shared directories')
    controller.prepare_host_environment()

    # build container
    print("----- Build jenkins base image on host " + config.jenkins_master_host_config.machine_id)
    controller.build_jenkins_base()
    print("----- Build and start container {0} on host {1}".format(config.jenkins_master_host_config.container_conf.container_name, config.jenkins_master_host_config.machine_id))
    controller.build_and_start_jenkins_master()
    print("----- Build and start the web-server containers")
    controller.build_and_start_web_servers()
    print("----- Build and start the docker SLAVE containers")
    controller.build_and_start_jenkins_linux_slaves()

    # setup ssh accesses
    print( '----- Setup access_rights' )
    controller.setup_access_rights()

    # configure jenkins
    if not config.jenkins_config.use_unconfigured_jenkins:
        print("----- Configure the jenkins master server.")
        controller.configure_jenkins_master(config_file)

    print()
    print('----- Successfully startet jenkins master, build slaves and the documentation server.')

    _print_access_summary(config)


###############################################################################################################

class MachinesController:
    """
    This class contains the implementation of the operations that must be done to setup
    all involved machines.
    """
    def __init__(self, config, connections):
        self.config = config
        self.connections = connections


    def prepare_host_environment(self):
        """
        Removes docker containers and networks from previous runs.
        Takes a config_data.ConfigData object as argument.
        """
        self._remove_all_container()
        self._clear_directories()


    def build_jenkins_base(self):
        """
        This builds the base image of the jenkins-master container.
        """
        connection = self._get_jenkins_master_host_connection()

        # crate the build-context on the host
        source_dir = _SCRIPT_DIR.joinpath('../JenkinsciDocker')
        docker_file = '17/debian/bullseye/hotspot/Dockerfile'
        files = [
            docker_file,
            'tini_pub.gpg',
            'tini-shim.sh',
            #'init.groovy',
            'jenkins-support',
            'jenkins.sh',
            #'plugins.sh',
            'install-plugins.sh',
            'git_lfs_pub.gpg',
            'jenkins-plugin-cli.sh',
        ]

        # Create the jenkins base image. This is required to customize the jenkins version.
        dockerutil.build_docker_image(
            connection,
            _JENKINS_BASE_IMAGE,
            source_dir,
            docker_file,
            ['JENKINS_VERSION=' + _JENKINS_VERSION, 'JENKINS_SHA=' + _JENKINS_SHA256, 'TARGETARCH=amd64'],
            files
        )


    def build_and_start_jenkins_master(self):

        connection = self._get_jenkins_master_host_connection()
        container_config = self.config.jenkins_master_host_config.container_conf
        container_image = container_config.container_image_name

        # create a directory on the host that contains all files that are needed for the container build
        docker_file = 'DockerfileJenkinsMaster'
        files = [
            docker_file,
            'installGcc.sh',
            'buildGit.sh',
            'buildCMake.sh',
        ]

        # Create the container image
        dockerutil.build_docker_image(
            connection,
            container_image,
            _SCRIPT_DIR,
            docker_file,
            ['JENKINS_BASE_IMAGE=' + _JENKINS_BASE_IMAGE],
            files
        )

        resolved_hosts = self._get_slave_machine_host_names()
        resolved_hosts.update(self._get_web_server_host_names())
        resolved_hosts.update(self._get_accessible_repository_host_names())
        dockerutil.docker_run_detached(connection, container_config, resolved_hosts=resolved_hosts)

        # Add global gitconfig after mounting the workspace volume, otherwise is gets deleted.
        # Note that the slaves do this in the dockerfile
        #commands = [
        #    'git config --global user.email not@valid.org',
        #    'git config --global user.name jenkins',
        #    'git config --global '
        #]
        #dockerutil.run_commands_in_container(
        #    connection,
        #    self.config.jenkins_master_host_config.container_conf,
        #    commands
        #    )

    def _get_slave_machine_host_names(self):
        host_names = []
        for slave_config in self.config.jenkins_slave_configs:
            connection = self.connections.get_connection(slave_config.machine_id)
            host_names.append(connection.info.host_name)
        return set(host_names)

    def _get_web_server_host_names(self):
        host_names = set()
        for cpf_job_config in self.config.jenkins_config.cpf_job_configs:
            if cpf_job_config.webserver_config.machine_id:
                connection = self.connections.get_connection(cpf_job_config.webserver_config.machine_id)
                host_names.add(connection.info.host_name)
        return host_names


    def _get_accessible_repository_host_names(self):
        """
        Returns the hostnames of the repository machines to which ssh accesses are established.
        These are the ones the use fresh ssh key files.
        """
        host_names = set()
        for repo_host_config in self.config.ssh_repository_host_accesses:
            connection = self.connections.get_connection(repo_host_config.machine_id)
            host_names.add(connection.info.host_name)
        return host_names


    def build_and_start_web_servers(self):

        for cpf_job_config in self.config.jenkins_config.cpf_job_configs:

            machine_id = cpf_job_config.webserver_config.machine_id
            if not machine_id:
                continue

            connection = self.connections.get_connection(machine_id)
            container_config = cpf_job_config.webserver_config.container_conf
            container_image = container_config.container_image_name
                
            print("----- Build and start the web-server container {0} on host {1}".format(container_config.container_name, machine_id))

            # create build context
            docker_file = 'DockerfileCPFWebServer'
            files = [
                docker_file,
                'ssh_config',
                '000-default.conf',
                'apache2_envvars',
                'apache2.conf',
                'supervisord.conf',
                'web-server-post-receive.in'
            ]

            # build container image
            dockerutil.build_docker_image(
                connection,
                container_image,
                _SCRIPT_DIR,
                docker_file, 
                [],
                files
                )

            # start container
            dockerutil.docker_run_detached(connection, container_config)

            # copy the doxyserach.cgi to the html share
            """
            html_share_container = next(iter(container_config.host_volumes.values()))
            cgi_bin_dir = html_share_container.joinpath('cgi-bin')
            commands = [
                'rm -fr ' + str(cgi_bin_dir),
                'mkdir ' + str(cgi_bin_dir),
                'mkdir ' + str(cgi_bin_dir) + '/doxysearch.db',
                'cp -r -f /usr/local/bin/doxysearch.cgi ' + str(cgi_bin_dir),
            ]
            dockerutil.run_commands_in_container(
                connection,
                container_config,
                commands
                )
            """


    def build_and_start_jenkins_linux_slaves(self):
        for slave_config in self.config.jenkins_slave_configs:
            if self.config.is_linux_machine(slave_config.machine_id):
                self._build_and_start_jenkins_linux_slave(slave_config.container_conf, slave_config.machine_id)


    def setup_access_rights(self):
        # setup ssh accesses of the jenkins-master
        connection = self._get_jenkins_master_host_connection()
        _create_rsa_key_file_pair_on_container(
            connection,
            self.config.jenkins_master_host_config.container_conf,
            config_data.JENKINS_HOME_JENKINS_MASTER_CONTAINER)

        self._grant_container_access_to_repositories(
            self.config.jenkins_master_host_config.container_conf,
            config_data.JENKINS_HOME_JENKINS_MASTER_CONTAINER)

        self._grant_jenkins_master_ssh_access_to_jenkins_linux_slaves()
        self._grant_jenkins_master_ssh_access_to_jenkins_windows_slaves()
        #self._grant_jenkins_master_ssh_access_to_web_servers()
        
        # setup ssh accesses used by the jenkins slaves
        self._create_rsa_key_file_pairs_on_slave_container()
        self._grant_linux_slaves_access_to_repositories()
        self._grant_linux_slaves_access_to_web_servers()    # They need access to push the build-results to the web-servers.
        # \todo Windows slaves need repository access as well.
        # We currently do this manually until we have a container solution
        # for windows as well.


    def configure_jenkins_master(self, config_file):
        self._configure_general_jenkins_options()
        self._configure_jenkins_users(config_file)
        self._configure_jenkins_jobs(config_file)
        slaveStartCommands = self._configure_jenkins_slaves()
        self.config.jenkins_config.approved_system_commands.extend(slaveStartCommands)

        # restart jenkins to make sure it as the desired configuration
        # this is required because approveing the slaves scripts requires jenkins to be
        # up and running.
        self._restart_jenkins()

        # Create object that helps with configuring jenkins over its web interface.
        master_connection = self._get_jenkins_master_host_connection()
        jenkins_accessor = JenkinsRESTAccessor(
            'http://{0}:8080'.format(master_connection.info.host_name),
            self.config.jenkins_config.admin_user,
            self.config.jenkins_config.admin_user_password
        )

        # Approve system commands
        jenkins_accessor.wait_until_online(90)

        print("----- Approve system-commands")
        pprint.pprint(self.config.jenkins_config.approved_system_commands)
        jenkins_accessor.approve_system_commands(self.config.jenkins_config.approved_system_commands)
        # Approve script signatures
        print("----- Approve script signatures")
        pprint.pprint(self.config.jenkins_config.approved_script_signatures)
        jenkins_accessor.approve_script_signatures(self.config.jenkins_config.approved_script_signatures)


    def _remove_all_container(self):
        """
        Stop and remove all containers of the CPF infrastructure.
        """
        for container in self.config.get_all_container():
            self._stubbornly_remove_container(container)


    def _stubbornly_remove_container(self, container):
        """
        Removes a given docker container even if it is running.
        If the container does not exist, the function does nothing.
        """
        connection = self._get_container_host_connection(container)
        if dockerutil.container_exists(connection, container):
            if dockerutil.container_is_running(connection, container):
                dockerutil.stop_docker_container(connection, container)
            dockerutil.remove_container(connection, container)

    def _get_container_host_connection(self, container):
        machine_id = self.config.get_container_host(container)
        return self.connections.get_connection(machine_id)


    def _clear_directories(self):
        # the master share directory
        jenkins_master_host_info = self.config.get_host_info(self.config.jenkins_master_host_config.machine_id)
        self._clear_directory_on_host(jenkins_master_host_info, self.config.jenkins_master_host_config.jenkins_home_share)

        # all temporary directories
        for host_info in self.config.host_machine_infos:
            self._clear_directory_on_host(host_info, host_info.temp_dir)


    def _clear_directory_on_host(self, host_config, directory):
        try:
            connection = self.connections.get_connection(host_config.machine_id)
            fileutil.clear_rdirectory(connection.sftp_client, directory)
        except IOError as err:
            print("Failed to clear the remote directory {0} on host {1}!".format(directory, host_config.host_name))
            raise


    def _get_jenkins_master_host_connection(self):
        return self.connections.get_connection(self.config.jenkins_master_host_config.machine_id)


    def _build_and_start_jenkins_linux_slave(self, container_conf, machine_id):
        
        connection = self.connections.get_connection(machine_id)
        container_image = container_conf.container_image_name

        # create build context
        docker_file = 'DockerfileJenkinsSlaveLinux'
        text_files = [
            docker_file,
            'ssh_config',
            'buildPython.sh',
            'buildCMake.sh'
        ]
        binary_files = [
            'agent.jar',
        ]

        # Build the container.
        dockerutil.build_docker_image(
            connection,
            container_image,
            _SCRIPT_DIR,
            docker_file,
            [],
            text_files,
            binary_files
            )

        # Start the container.
        resolved_hosts = self._get_accessible_repository_host_names()
        resolved_hosts.update(self._get_web_server_host_names()) # slaves may need to copy files from the webserver
        dockerutil.docker_run_detached(connection, container_conf, resolved_hosts=resolved_hosts)


    def _create_rsa_key_file_pairs_on_slave_container(self):
        for slave_config in self.config.jenkins_slave_configs:
            if self.config.is_linux_machine(slave_config.machine_id):
                connection = self.connections.get_connection(slave_config.machine_id)
                _create_rsa_key_file_pair_on_container(
                    connection,
                    slave_config.container_conf,
                    PurePosixPath('/home/jenkins')
                )


    def _grant_container_access_to_repositories(self, container_conf, container_home_directory):

        # Handle repository host for which we can access the .ssh directory and add new public key files
        # directly.
        for repository_host_config in self.config.ssh_repository_host_accesses:
            self._register_public_key_file_with_ssh_server(container_conf, container_home_directory, repository_host_config, False)

        # Handle repository accesses for https hosts.
        for repository_host_config in self.config.https_repository_accesses:
            self._grant_container_access_to_https_repositories(container_conf, container_home_directory, repository_host_config)
        
    
    def _register_public_key_file_with_ssh_server(self, ssh_client_container_config, ssh_client_container_home_directory, ssh_host_config, host_is_container):
        """
        This function assumes that the ssh client container has a public key file in its ssh_client_container_home_directory.
        It copies that file to the ssh_server and adds the public key into the authorized keys file.
        It also adds the ssh_server to the known hosts file on the client machine.
        The server can be a container or a normal machine in the network.
        """

        ssh_server_machine_id = ssh_host_config.machine_id
        ssh_server_host_connection = self.connections.get_connection(ssh_server_machine_id)
        repository_machine_ssh_dir = ssh_host_config.ssh_dir

        container_name = ssh_client_container_config.container_name
        container_host_connection = self._get_container_host_connection(container_name)

        # COPY AND REGISTER THE PUBLIC KEY WITH repositoryMachine
        public_key_file = _get_public_key_filename(container_name)
        source_file = ssh_client_container_home_directory.joinpath(public_key_file)
        target_file = repository_machine_ssh_dir.joinpath(public_key_file)

        ssh_port = 22
        if host_is_container:
            print('----- Grant container ' + container_name + ' SSH access to container ' + ssh_host_config.container_conf.container_name + ' on machine ' + ssh_server_machine_id)
            ssh_port = ssh_host_config.container_ssh_port
            dockerutil.container_to_container_copy(container_host_connection, ssh_client_container_config, ssh_server_host_connection, ssh_host_config.container_conf, source_file, target_file)
        else:
            print('----- Grant container ' + container_name + ' SSH access to machine ' + ssh_server_machine_id)
            dockerutil.containertorcopy(container_host_connection, ssh_client_container_config, ssh_server_host_connection, source_file, target_file)

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

        if host_is_container:
            dockerutil.run_command_in_container(ssh_server_host_connection, ssh_host_config.container_conf, command)
        else:
            ssh_server_host_connection.run_command(command)

        # Add the repository machine as known host to prevent the authentication request on the first run
        _accept_remote_container_host_key(
            container_host_connection, 
            ssh_client_container_config, 
            ssh_server_host_connection.info.host_name, 
            ssh_port,
            ssh_server_host_connection.info.user_name
        )


    def _grant_container_access_to_https_repositories(self, container_conf, container_home_directory, https_repository_host_config):
        """
        This function adds the credentials of the given https based repository accesses to the git credential store of that container.
        """
        container_name = container_conf.container_name
        container_host_connection = self._get_container_host_connection(container_name)

        # Add the credentials for the repository to the jenkins-git-credentials file.
        credential_file = container_home_directory.joinpath(_GIT_CREDENTIALS_STORE)
        command = 'echo https://{0}:{1}@{2} >> {3}'.format(
            https_repository_host_config.user_name,
            https_repository_host_config.user_password,
            https_repository_host_config.host_name,
            credential_file
        )
        dockerutil.run_command_in_container(
            container_host_connection,
            container_conf,
            command
        )


    def _grant_jenkins_master_ssh_access_to_jenkins_linux_slaves(self):
        """
        Creates an authorized-keys file on all jenkins slave containers
        that contains the public key of the master.
        """
        master_host_connection = self._get_jenkins_master_host_connection()
        master_conf = self.config.jenkins_master_host_config.container_conf
        master_container = master_conf.container_name
        public_key_file_master_host = master_host_connection.info.temp_dir.joinpath(
            _get_public_key_filename(master_container)
            )

        for slave_config in self.config.jenkins_slave_configs:
            if self.config.is_linux_machine(slave_config.machine_id):
                slave_connection = self.connections.get_connection(slave_config.machine_id)
                authorized_keys_file = _JENKINS_HOME_JENKINS_SLAVE_CONTAINER.joinpath('.ssh/authorized_keys')
                # add the masters public key to the authorized keys file of the slave
                dockerutil.rtocontainercopy(master_host_connection, slave_connection, slave_config.container_conf, public_key_file_master_host, authorized_keys_file)

                # authenticate the slave ssh host with the master
                # we rely her on the fact that the slave container only have one published port
                # which is the ssh port
                if not len(slave_config.container_conf.published_ports.keys()) == 1:
                    raise Exception('Function assumes only one published port for slave containers')
                _accept_remote_container_host_key(
                    master_host_connection, 
                    master_conf, 
                    slave_connection.info.host_name, 
                    next(iter(slave_config.container_conf.published_ports.keys())),
                    slave_config.container_conf.container_user
                    )


    def _grant_jenkins_master_ssh_access_to_jenkins_windows_slaves(self):
        for slave_config in self.config.jenkins_slave_configs:
            if self.config.is_windows_machine(slave_config.machine_id):
                slave_connection = self.connections.get_connection(slave_config.machine_id)
                self._grant_jenkins_master_ssh_access_to_jenkins_windows_slave(slave_connection)


    def _grant_jenkins_master_ssh_access_to_jenkins_windows_slave(self, slave_host_connection ):

        master_config = self.config.jenkins_master_host_config.container_conf
        master_container = master_config.container_name
        print(("----- Grant {0} ssh access to {1}").format(master_container, slave_host_connection.info.host_name))

        # configure the script for adding an authorized key to the bitwise ssh server on the
        # windows machine
        authorized_keys_script = 'updateAuthorizedKeys.bat'
        full_authorized_keys_script = _SCRIPT_DIR.joinpath(authorized_keys_script)

        master_connection = self._get_jenkins_master_host_connection()
        public_key_file_master = config_data.JENKINS_HOME_JENKINS_MASTER_CONTAINER.joinpath('.ssh/' + _get_public_key_filename(master_container) )
        public_key = dockerutil.run_command_in_container(
            master_connection,
            master_config,
            'cat {0}'.format(public_key_file_master)
        )[0]

        configure_file(str(full_authorized_keys_script) + '.in', full_authorized_keys_script, {
            '@PUBLIC_KEY@' : public_key,
            '@JENKINS_MASTER_CONTAINER@' : master_container,
            '@SLAVE_MACHINE_USER@' : slave_host_connection.info.user_name,
        })

        # copy the script to the windows slave machine
        ssh_dir = PureWindowsPath('C:/Users/' + slave_host_connection.info.user_name + '/.ssh')
        full_script_path_on_slave = ssh_dir.joinpath(full_authorized_keys_script.name)
        slave_host_connection.sftp_client.put(str(full_authorized_keys_script), str(full_script_path_on_slave))

        # call the script
        try:
            call_script_command = '{0} {1}'.format(full_script_path_on_slave, slave_host_connection.info.user_password)
            slave_host_connection.run_command(call_script_command, print_command=True)
        except Exception as err:
            print(
                "Error: Updating the authorized ssh keys on "
                + slave_host_connection.info.host_name + " failed. Was the password correct?")
            raise err

        # clean up the generated script because of the included password
        os.remove(str(full_authorized_keys_script))

        # Wait a little until the bitvise ssh server is ready to accept the key file.
        # This can possibly fail on slower machines.
        time.sleep(1)

        # Add the slave to the known hosts
        try:
            _accept_remote_container_host_key(
                master_connection, 
                master_config, 
                slave_host_connection.info.host_name, 
                22, 
                slave_host_connection.info.user_name
                )
        except Exception as err:
            # This is not really clean but I can not think of a better solution now.
            print("When this call fails, it is possible that the waiting time before using the ssh connection to the Bitvise SSH server is too short.")
            raise err


    def _grant_jenkins_master_ssh_access_to_web_servers(self):

        master_container_config = self.config.jenkins_master_host_config.container_conf
        master_container = master_container_config.container_name
        master_public_key_file = config_data.JENKINS_HOME_JENKINS_MASTER_CONTAINER.joinpath('.ssh/' + _get_public_key_filename(master_container))
        master_host_connection = self._get_jenkins_master_host_connection()
        
        for cpf_job_config in self.config.jenkins_config.cpf_job_configs:

            if not cpf_job_config.webserver_config.machine_id:
                continue

            webserver_host_connection = self.connections.get_connection(cpf_job_config.webserver_config.machine_id)
            webserver_container_config = cpf_job_config.webserver_config.container_conf
            webserver_authorized_keys_file = cpf_job_config.webserver_config.ssh_dir.joinpath('authorized_keys')

            # set the authorized keys file in the webserver container
            dockerutil.container_to_container_copy(
                master_host_connection, 
                master_container_config, 
                webserver_host_connection, 
                webserver_container_config, 
                master_public_key_file, 
                webserver_authorized_keys_file
            )
            
            # we need to change the file owner from jenkins to root
            commands = [
                #'chown root:root ' + str(webserver_authorized_keys_file),
                'chmod 600 ' + str(webserver_authorized_keys_file),
                'service ssh start',
            ]
            dockerutil.run_commands_in_container(
                webserver_host_connection,
                webserver_container_config,
                commands
            )

            # Add doc-server as known host to prevent the authentication request on the first connect
            _accept_remote_container_host_key(
                master_host_connection, 
                master_container_config, 
                webserver_host_connection.info.host_name, 
                cpf_job_config.webserver_config.container_ssh_port, 
                webserver_container_config.container_user
            )


    def _grant_linux_slaves_access_to_repositories(self):
        for slave_config in self.config.jenkins_slave_configs:
            if self.config.is_linux_machine(slave_config.machine_id):
                self._grant_container_access_to_repositories(
                    slave_config.container_conf,
                    PurePosixPath('/home/jenkins')
                )


    def _grant_linux_slaves_access_to_web_servers(self):
        for slave_config in self.config.jenkins_slave_configs:
            if self.config.is_linux_machine(slave_config.machine_id):
                self._grant_linux_slave_access_to_web_servers(slave_config.container_conf)

    
    def _grant_linux_slave_access_to_web_servers(self, slave_container_config):
        
        for cpf_job_config in self.config.jenkins_config.cpf_job_configs:

            # Ignore jobs that have no extra-webserver assigned.
            machine_id = cpf_job_config.webserver_config.machine_id
            if not machine_id:
                continue

            self._register_public_key_file_with_ssh_server(slave_container_config, PurePosixPath('/home/jenkins'), cpf_job_config.webserver_config, True)


    def _configure_general_jenkins_options(self):
        """
        Configure the general options by copying the .xml config files from the JenkinsConfig
        directory to the jenkins master home directory.
        """
        connection = self._get_jenkins_master_host_connection()
        dockerutil.copy_local_textfile_tree_to_container(
            _SCRIPT_DIR.joinpath('JenkinsConfig'),
            connection,
            self.config.jenkins_master_host_config.container_conf,
            config_data.JENKINS_HOME_JENKINS_MASTER_CONTAINER
        )


    def _configure_jenkins_users(self, config_file):
        """
        Copy user config xml files to user/<username>/config.xml
        """
        self._copy_jenkins_config_files(config_file, 'users', self.config.jenkins_config.account_config_files)


    def _configure_jenkins_jobs(self, config_file):
        """
        copy job config xml files to jobs/<jobname>/config.xml
        """
        temp_dir = self._configure_cpf_job_files(config_file)
        self._copy_jenkins_config_files(config_file, 'jobs', self.config.jenkins_config.job_config_files)
        shutil.rmtree(str(temp_dir))


    def _configure_cpf_job_files(self, config_file):
        """
        This function creates the .xml config files for the CPF pipeline jobs.
        """
        # create the job .xml files that are used by jenkins.
        temp_dir = PurePath('temp')
        abs_temp_dir = _SCRIPT_DIR.joinpath(PurePath('../..').joinpath(temp_dir))
        
        # clean up the temporary files
        if os.path.isdir(str(abs_temp_dir)):
            shutil.rmtree(str(abs_temp_dir))
        os.makedirs(str(abs_temp_dir))

        job_dict = {}
        for cpf_job_config in self.config.jenkins_config.cpf_job_configs:
            job_name = get_job_name(cpf_job_config.base_job_name)
            xml_file = job_name + '.xml'
            # The config requires a path relative to the config file.
            xml_file_path = temp_dir.joinpath(xml_file)
            abs_xml_file_path = abs_temp_dir.joinpath(xml_file)
            # create the job config file
            self._configure_job_config_file(cpf_job_config, abs_xml_file_path)

            # add the generated config file to the list of config file items
            self.config.jenkins_config.job_config_files.append(config_data.ConfigItem(job_name, xml_file_path))

        # Extend the config values with the scripts that need to
        # be approved to run the jenkinsfile.
        approved_script_signatures = [
            'new groovy.json.JsonSlurperClassic',
            'method groovy.json.JsonSlurperClassic parseText java.lang.String',
            'staticMethod org.codehaus.groovy.runtime.DefaultGroovyMethods matches java.lang.String java.util.regex.Pattern',
            'new java.lang.Exception java.lang.String',
            'method java.lang.String join java.lang.CharSequence java.lang.CharSequence[]'
        ]
        self.config.jenkins_config.approved_script_signatures.extend(approved_script_signatures)

        return abs_temp_dir
        

    def _configure_job_config_file(self, cpf_job_config, created_config_file):
        """
        Fills in the blanks in the config file and copies it to the given job
        directory.
        """
        # TODO this should be a version tag of CPFMachines once automatic versioning for CPFJenkinsjob works.
        # For now we leave it at the master so we always get the latest version.
        tag_or_branch = 'master'

        jobConfigVariableMap = {
            '@JOB_NAME@' : get_job_name(cpf_job_config.base_job_name),
            '@JENKINSFILE_TAG_OR_BRANCH@' : tag_or_branch,
            '@DEFAULT_BRANCH@' : cpf_job_config.default_branch,
            '@PACKAGE_MANAGER@' : cpf_job_config.package_manager,
            '@CONAN_REMOTE@' : cpf_job_config.conan_remote,
            '@CI_REPOSITORY@' : cpf_job_config.ci_repository,
            '@BUILD_RESULT_REPOSITORY_MASTER@' : cpf_job_config.result_repository,
            '@BUILD_RESULT_REPOSITORY_SUBDIRECTORY@' : cpf_job_config.result_repository_project_subdirectory,
            '@CPFMACHINES_REPOSITORY@' : _JENKINSJOB_REPOSITORY,
            '@CPFCMake_DIR@' : cpf_job_config.CPFCMake_DIR,
            '@CPFBuildscripts_DIR@' : cpf_job_config.CPFBuildscripts_DIR,
            '@CIBuildConfigurations_DIR@' : cpf_job_config.CIBuildConfigurations_DIR,
        }

        # If the job comes with a web-server we add the content repository on the webserver to job-config.
        if cpf_job_config.webserver_config.machine_id:
            info = self.connections.get_connection(cpf_job_config.webserver_config.machine_id).info
            port = cpf_job_config.webserver_config.container_ssh_port
            jobConfigVariableMap['@BUILD_RESULT_REPOSITORY_WEB_SERVER@'] = 'ssh://jenkins@{0}:{1}/home/jenkins/WebContentRepository'.format(info.host_name, port)
        else:
            jobConfigVariableMap['@BUILD_RESULT_REPOSITORY_WEB_SERVER@'] = ''

        configure_file(_CPF_JOB_TEMPLATE_FILE, created_config_file, jobConfigVariableMap)


    def _copy_jenkins_config_files(self, config_file, config_dir, config_items):
        """
        Copies the config.xml files that are mentioned in a map under filesConfigKey
        in the script config file to named directories under the given config dir
        to the jenkins-master home directory.
        """
        master_connection = self._get_jenkins_master_host_connection()

        config_file_dir = config_file.parent
        jobs_config_dir = config_data.JENKINS_HOME_JENKINS_MASTER_CONTAINER.joinpath(config_dir)
        for config_item in config_items:
            if config_file_dir:
                sourceconfig_file = config_file_dir.joinpath(config_item.xml_file)
            else:
                sourceconfig_file = config_item.xml_file
            job_config_dir = jobs_config_dir.joinpath(config_item.name)
            job_config_file = PurePosixPath('config.xml')
            dockerutil.copy_textfile_to_container(
                master_connection,
                self.config.jenkins_master_host_config.container_conf,
                sourceconfig_file,
                job_config_dir.joinpath(job_config_file)
            )


    def _restart_jenkins(self):
        master_connection = self._get_jenkins_master_host_connection()
        master_container = self.config.jenkins_master_host_config.container_conf.container_name
        dockerutil.stop_docker_container(master_connection, master_container)
        dockerutil.start_docker_container(master_connection, master_container)


    def _configure_jenkins_slaves(self):
        """
        Create config files for the slave nodes.
        All slave nodes are based on the ssh command execution start scheme from
        the command-launcher plugin.
        """
        print("----- Configure jenkins slave nodes")

        start_commands = []

        for slave_config in self.config.jenkins_slave_configs:
            slave_host_connection = self.connections.get_connection(slave_config.machine_id)
            if self.config.is_linux_machine(slave_config.machine_id):
                
                # we rely her on the fact that the slave container only have one published port
                # which is the ssh port
                if not len(slave_config.container_conf.published_ports.keys()) == 1:
                    raise Exception('Function assumes only one published port for slave containers')
                
                # create config file for the linux slave
                linux_slave_start_command = _get_slave_start_command(
                    slave_host_connection,
                    slave_config.container_conf.container_user,
                    next(iter(slave_config.container_conf.published_ports.keys())),
                    '/home/jenkins/bin'
                )
                self._configure_node_config_file(
                    slave_config.slave_name,
                    'An Ubuntu 20 build machine.',
                    '/home/{0}/workspaces'.format(slave_config.container_conf.container_user),
                    linux_slave_start_command,
                    _get_slave_labels_string('Ubuntu-20.04', 10),
                    slave_config.executors
                )
                start_commands.append(linux_slave_start_command)

            elif self.config.is_windows_machine(slave_config.machine_id):
                # create config file for the windows slave
                slave_workspace = 'C:/jenkins'
                windows_slave_start_command = _get_slave_start_command(
                    slave_host_connection,
                    slave_host_connection.info.user_name,
                    22,
                    slave_workspace
                )
                self._configure_node_config_file(
                    slave_config.slave_name,
                    'A Windows 10 build machine.',
                    slave_workspace,
                    windows_slave_start_command,
                    _get_slave_labels_string('Windows-10', 10),
                    slave_config.executors
                )
                start_commands.append(windows_slave_start_command)

            else:
                raise Exception('Function misses case for operating system of slave ' + slave_config.machine_id)

        return start_commands


    def _configure_node_config_file(
            self,
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
        fileutil.clear_dir(temp_dir)

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
        master_connection = self._get_jenkins_master_host_connection()
        nodes_dir = config_data.JENKINS_HOME_JENKINS_MASTER_CONTAINER.joinpath('nodes')
        node_dir = nodes_dir.joinpath(slave_name)
        target_file = node_dir.joinpath(createdconfig_file.name)
        dockerutil.copy_textfile_to_container(
            master_connection,
            self.config.jenkins_master_host_config.container_conf,
            createdconfig_file,
            target_file
        )

        fileutil.clear_dir(temp_dir)


###############################################################################################################

def dev_message(text):
    """
    Print function emphasizes the printed string with some dashes.
    It is intended to be used for debugging during development.
    """
    print('--------------- ' + str(text))


def _get_https_repository_passwords(config):
    """
    Prompts the user to enter the passwords for the https repositories if none are provided in
    the config file.
    """
    for https_config in config.https_repository_accesses:
        if not https_config.user_password:
            prompt_message = "Please enter the password for https repository user {0} on host {1}.".format(https_config.user_name, https_config.host_name)
            https_config.user_password = getpass.getpass(prompt_message)


def _create_rsa_key_file_pair_on_container(connection, container_conf, container_home_directory):
    # copy the scripts that does the job to the container
    dockerutil.copy_textfile_to_container(
        connection,
        container_conf,
        _SCRIPT_DIR.joinpath(_CREATEKEYPAIR_SCRIPT),
        container_home_directory.joinpath(_CREATEKEYPAIR_SCRIPT)
    )

    # This will create the key-pair on the container.
    # We need to do this in the container or ssh will not accept the private key file.
    dockerutil.run_command_in_container(
        connection,
        container_conf,
        '/bin/bash ' + str(container_home_directory.joinpath(_CREATEKEYPAIR_SCRIPT)) + ' ' + container_conf.container_name
        )

def _get_public_key_filename(container):
    return container + _PUBLIC_KEY_FILE_POSTFIX

def _accept_remote_container_host_key(client_container_host_connection, client_container_config, host_host_name, ssh_port, host_container_user):
    """
    Opens a ssh connection from the client container to the host container and thereby accepting the hosts ssh key.
    """
    #dockerutil.run_command_in_container(
    #    client_container_host_connection,
    #    client_container_config,
    #    'ssh -oStrictHostKeyChecking=no -p {0} {1}@{2} "echo dummy"'.format(ssh_port, host_container_user, host_host_name)
    #)
    _add_known_ssh_host(client_container_host_connection, client_container_config, host_host_name, ssh_port)



def _add_known_ssh_host(client_container_host_connection, client_container_config, ssh_host_name, ssh_port):
    """
    Uses the ssh-keyscan command to add the public key of an ssh server to the known_hosts file of the
    given container.
    """
    known_hosts_file = PurePosixPath('~/.ssh/known_hosts')
    dockerutil.run_command_in_container(
        client_container_host_connection,
        client_container_config,
        'ssh-keyscan -p {0} {1} >> {2}'.format(ssh_port, ssh_host_name, known_hosts_file)
    )


def _get_slave_start_command(host_connection, slave_user, ssh_port, slave_jar_dir):
    """
    defines the command that is used to start the slaves via ssh.
    """
    start_command = (
        'ssh {0}@{1} -p {2} java -jar {3}/agent.jar'
        ).format(slave_user , host_connection.info.host_name, ssh_port, slave_jar_dir)
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


def get_job_name(job_base_name):
    """
    Add the version to the base name.
    """
    return job_base_name + '-' + cpfmachines_version.CPFMACHINES_VERSION


def _print_access_summary(config):
    """
    Prints information under which hostnames and ports ssh-server
    and webpages can be accessed.
    """
    
    jenkins_mater_host_info = config.get_host_info(config.jenkins_master_host_config.machine_id)
    
    print()
    print('##### Summary of web-pages and ssh accesses #####')
    print()
    print('Jenkins web-interface:')
    print('http://{0}:8080'.format(jenkins_mater_host_info.host_name))
    print()
    print('Project web-pages:')
    for cpf_job_config in config.jenkins_config.cpf_job_configs:
        if cpf_job_config.webserver_config.machine_id:
            host_info = config.get_host_info(cpf_job_config.webserver_config.machine_id)
            mapped_port = cpf_job_config.webserver_config.container_web_port
            print('{0} -> http://{1}:{2}/LastBuild/sphinx/html'.format(cpf_job_config.base_job_name, host_info.host_name, mapped_port))
    print()
    print('SSH accesses build-slaves:')
    for slave_config in config.jenkins_slave_configs:
        machine_id = slave_config.machine_id
        host_info = config.get_host_info(machine_id)
        if config.is_linux_machine(machine_id):
            ssh_port = next(iter(slave_config.container_conf.published_ports.keys()))
            print('{0} -> \"ssh -p{1} {2}@{3}\"'.format(
                slave_config.container_conf.container_name,
                ssh_port,
                slave_config.container_conf.container_user,
                host_info.host_name
            ))
        elif config.is_windows_machine(machine_id):
            print('{0} -> \"ssh {1}@{2}\"'.format(
                machine_id,
                host_info.user_name,
                host_info.host_name
            ))
        else:
            raise Exception("Function needs to be extended for new os type")
    print()
    print('SSH accesses web-server:')
    for cpf_job_config in config.jenkins_config.cpf_job_configs:
        if cpf_job_config.webserver_config.machine_id:
            container_conf = cpf_job_config.webserver_config.container_conf
            host_info = config.get_host_info(cpf_job_config.webserver_config.machine_id)
            print('{0} -> \"ssh -p{1} {2}@{3}\"'.format(
                container_conf.container_name,
                cpf_job_config.webserver_config.container_ssh_port,
                container_conf.container_user,
                host_info.host_name
            ))



if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
