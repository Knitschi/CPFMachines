#!/usr/bin/env python3

# This script removes and adds and starts all docker container of the CppCodeBase project
# infrastructure.
# Arguments:
# 1. - The path to a configuration json file.
# (An empty file can be generated with the createEmptyconfig_files.py script)


import os
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

from . import cppcodebasemachines_version
from . import config_data

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

# Constants
# The version of the jenkins CI server that is installed on the jenkins-master machine.
_JENKINS_VERSION = '2.89.1'
# The sha256 checksum of the jenkins.war package of the given jenkins version.
_JENKINS_SHA256 = 'f9f363959042fce1615ada81ae812e08d79075218c398ed28e68e1302c4b272f'

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


def clear_directory(directory):
    """
    This functions deletes the given directory and all its content and recreates it.
    """
    if os.path.isdir(directory):
        shutil.rmtree(directory)
    os.makedirs(directory)


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

    config_dict = config_data.read_config_file(config_file)
    config = config_data.ConfigData(config_dict)




    # prepare environment
    print('----- Cleanup existing container')
    _clear_docker(config)
    """
    clear_directory(config_values['HostJenkinsMasterShare'])
    # we do not clear this to preserve the accumulated web content.
    _guarantee_directory_exists(config_values['HostHTMLShare'])
    _create_docker_network(_DOCKER_NETWORK_NAME)

    # build container
    _build_and_start_jenkins_master(config_values)
    # The document server must be started before the jenkins slave is started because mounting
    # the shared volume here sets the owner of the share to root an only the jenkins container
    # can set it to jenkins.
    _build_and_start_web_server(config_values)
    _build_and_start_jenkins_linux_slave()

    # setup ssh accesses used by jenkins-master
    _create_rsa_key_file_pair_on_container(
        _JENINS_MASTER_CONTAINER,
        _JENKINS_HOME_JENKINS_MASTER_CONTAINER)
    _grant_container_ssh_access_to_repository(
        _JENINS_MASTER_CONTAINER,
        _JENKINS_HOME_JENKINS_MASTER_CONTAINER,
        config_values)
    _grant_jenkins_master_ssh_access_to_jenkins_linux_slave(config_values)
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


def _clear_docker(ssh_connections, slave_configs, master_config):
    
    _stubbornly_remove_container(ssh_connections[master_config.machine_id].ssh_client, _WEBSERVER_CONTAINER)
    _stubbornly_remove_container(ssh_connections[master_config.machine_id].ssh_client, _JENINS_MASTER_CONTAINER)

    linux_slave_machine_ids = config_file_utils.get_linux_jenkins_slaves(ssh_connections, slave_configs)
    for machine_id in linux_slave_machine_ids:
        _stubbornly_remove_container(ssh_connections[machine_id].ssh_client, _FULL_LINUX_JENKINS_SLAVE_NAME)

    _remove_docker_network(_DOCKER_NETWORK_NAME)


def _stubbornly_remove_container(ssh_client, container):
    """
    Removes a given docker container even if it is running.
    If the container does not exist, the function does nothing.
    """
    running_container = _get_running_docker_container()

    if container in running_container:
        _stop_docker_container(container)

    all_container = _get_all_docker_container()
    if container in all_container:
        _remove_container(container)


def _get_running_docker_container():
    return _run_command_to_get_list("docker ps --format '{{.Names}}'")


def _get_all_docker_container():
    return _run_command_to_get_list("docker ps -a --format '{{.Names}}'")


def _run_command_to_get_list(command):
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
            line_string = nline.decode("ISO-8859-1")
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


def _stop_docker_container(container):
    _run_command('docker stop ' + container)


def _start_docker_container(container):
    _run_command('docker start ' + container)


def _remove_container(container):
    """
    This removes a given docker container and will fail if the container is running.
    """
    _run_command('docker rm -f ' + container)


def _remove_docker_network(network):
    network_lines = _run_command_to_get_list('docker network ls')
    networks = []
    for line in network_lines:
        columns = line.split()
        networks.append(columns[1])

    if network in networks:
        _run_command('docker network rm ' + _DOCKER_NETWORK_NAME)


def _guarantee_directory_exists(directory):
    if not os.path.isdir(directory):
        os.makedirs(directory)


def _create_docker_network(network):
    _run_command('docker network create --driver bridge --subnet=172.19.0.0/16 ' + network)


def _build_and_start_jenkins_master(config_values):
    print("----- Build and startping  the docker MASTER container " + _JENINS_MASTER_CONTAINER)

    # Create the jenkins base image. This is required to customize the jenkins version.
    jenkins_base_image = 'jenkins-image-' + _JENKINS_VERSION
    _build_docker_image(
        jenkins_base_image,
        _SCRIPT_DIR + '/../JenkinsciDocker/Dockerfile',
        _SCRIPT_DIR + '/../JenkinsciDocker',
        ['JENKINS_VERSION=' + _JENKINS_VERSION, 'JENKINS_SHA=' + _JENKINS_SHA256])

    # Create the container image
    container_image = _JENINS_MASTER_CONTAINER + '-image'
    _build_docker_image(
        container_image,
        _SCRIPT_DIR + '/DockerfileJenkinsMaster',
        _SCRIPT_DIR,
        ['JENKINS_BASE_IMAGE=' + jenkins_base_image])

    # Start the container
    # --env JAVA_OPTS="-Djenkins.install.runSetupWizard=false"
    # The jenkins master and its slaves communicate over the bridge network.
    # This means the master and the slaves must be on the same host.
    # This should later be upgraded to a swarm.

    # When the user already has a jenkins configuration
    # we add an option that prevents the first startup wizard from popping up.
    no_setup_wizard_option = ''
    if not config_values['UseUnconfiguredJenkinsMaster']:
        no_setup_wizard_option = '--env JAVA_OPTS="-Djenkins.install.runSetupWizard=false" '

    command = (
        'docker run '
        '--detach '
        # This makes the jenkins home directory accessible on the host. This eases debugging.
        '--volume ' + config_values['HostJenkinsMasterShare'] + ':' + _JENKINS_HOME_JENKINS_MASTER_CONTAINER + ' '
        + no_setup_wizard_option +
        # The jenkins webinterface is available under this port.
        '--publish 8080:8080 '
        # Only needed for hnlp slaves. We leave it here in case we need hnlp slave later.
        #'--publish 50000:50000 '
        '--name ' + _JENINS_MASTER_CONTAINER + ' '
        '--net ' + _DOCKER_NETWORK_NAME + ' '
        '--ip ' + _JENINS_MASTER_CONTAINERIP + ' '
        + container_image 
    )
    _run_command(command, print_command=True)

    # add global gitconfig after mounting the workspace volume, otherwise is gets deleted.
    _run_command_in_container(
        _JENINS_MASTER_CONTAINER,
        'git config --global user.email not@valid.org')
    _run_command_in_container(
        _JENINS_MASTER_CONTAINER,
        'git config --global user.name jenkins')


def _build_docker_image(image_name, docker_file, build_context_directory, build_args):
    build_args_string = ''
    for arg in build_args:
        build_args_string += ' --build-arg ' + arg

    command = (
        'docker build' + build_args_string + ' -t ' + image_name +
        ' -f ' + docker_file + ' ' + build_context_directory
    )
    _run_command(command, True)


def _run_command_in_container(container, command, user=None):
    user_option = ''
    if user:
        user_option = '--user ' + user + ':' + user + ' '
    command = 'docker exec ' + user_option + container + ' ' + command
    print(command)
    return _run_command(command)


def _build_and_start_web_server(config_values):
    print("----- Build and start the web-server container " + _WEBSERVER_CONTAINER)

    container_image = _WEBSERVER_CONTAINER + '-image'
    _build_docker_image(container_image, _SCRIPT_DIR + '/DockerfileCcbWebServer', _SCRIPT_DIR, [])

    command = (
        'docker run '
        '--detach '
        '--publish 80:80 '      # The web-page is reached under port 80
        '--volume ' + config_values['HostHTMLShare'] + ':' + _HTML_SHARE_WEB_SERVER_CONTAINER + ' '
        '--name ' + _WEBSERVER_CONTAINER + ' '
        '--net ' + _DOCKER_NETWORK_NAME + ' '
        '--ip ' + _WEBSERVER_CONTAINERIP + ' '
        + container_image
    )
    _run_command(command, print_command=True)

    # copy the doxyserach.cgi to the html share
    _run_command_in_container(
        _WEBSERVER_CONTAINER,
        'rm -fr ' + _HTML_SHARE_WEB_SERVER_CONTAINER + '/cgi-bin',
        'root')
    _run_command_in_container(
        _WEBSERVER_CONTAINER,
        'mkdir ' + _HTML_SHARE_WEB_SERVER_CONTAINER + '/cgi-bin',
        'root')
    _run_command_in_container(
        _WEBSERVER_CONTAINER,
        'mkdir ' + _HTML_SHARE_WEB_SERVER_CONTAINER + '/cgi-bin/doxysearch.db',
        'root')
    _run_command_in_container(
        _WEBSERVER_CONTAINER,
        'cp -r -f /usr/local/bin/doxysearch.cgi ' + _HTML_SHARE_WEB_SERVER_CONTAINER + '/cgi-bin',
        'root')


def _build_and_start_jenkins_linux_slave():
    # Start the container.
    print("----- Build and start the docker SLAVE container " + _FULL_LINUX_JENKINS_SLAVE_NAME)

    container_image = _LINUX_SLAVE_BASE_NAME + '-image'
    _build_docker_image(
        container_image, _SCRIPT_DIR + '/DockerfileJenkinsSlaveLinux',
        _SCRIPT_DIR, [])

    command = (
        'docker run '
        '--detach '
        '--name ' + _FULL_LINUX_JENKINS_SLAVE_NAME + ' '
        '--net ' + _DOCKER_NETWORK_NAME + ' '
        '--ip ' + _JENKINS_LINUX_SLAVE_CONTAINER_IP + ' '
        + container_image
    )
    _run_command(command, print_command=True)


def _create_rsa_key_file_pair_on_container(container_name, container_home_directory):
    print(
        '----- Create SSH key file pair for container ' + container_name +
        ' in directory ' + container_home_directory)

    # copy the scripts that does the job to the container
    _run_command(
        'docker cp ' + _SCRIPT_DIR + '/' + _CREATEKEYPAIR_SCRIPT +
        ' ' + container_name + ':' + container_home_directory + '/' + _CREATEKEYPAIR_SCRIPT)

    _run_command(
        'docker cp ' + _SCRIPT_DIR + '/' + _ADDKNOWNHOST_SCRIPT +
        ' ' + container_name + ':' + container_home_directory + '/' + _ADDKNOWNHOST_SCRIPT)

    # This will create the key-pair on the container.
    # We need to do this in the container or ssh will not accept the private key file.
    _run_command_in_container(
        container_name,
        '/bin/bash ' + container_home_directory + '/' + _CREATEKEYPAIR_SCRIPT + ' '+ container_name,
        'jenkins')


def _grant_container_ssh_access_to_repository(container_name, container_home_directory, config_values):

    repository_machine = config_values['RepositoryMachineName']
    repository_machine_user = config_values['RepositoryMachineUser']
    repository_machine_ssh_dir = config_values['RepositoryMachineSSHDir']
    temp_dir_host = config_values['HostTempDir']

    print(
        '----- Grant container ' + container_name +
        ' SSH access to the repository machine ' + repository_machine)
    # COPY AND REGISTER THE PUBLIC KEY WITH repositoryMachine
    # The connection is used to access the git repository
    # This requires access to the datenbunker.
    public_key_file = container_name + _PUBLIC_KEY_FILE_POSTFIX
    _guarantee_directory_exists(temp_dir_host)
    full_temp_public_key_file = temp_dir_host + '/' + public_key_file
    if os.path.isfile(full_temp_public_key_file):
        os.remove(full_temp_public_key_file) # delete previously copied key-files

    # Copy the public key from the jenkins jome directory to the
    # jenkins-workspace directory on the host
    _run_command((
        'docker cp {0}:{1}/{2} {3}'
        ).format(container_name, container_home_directory, public_key_file, temp_dir_host))

    # Then copy it to the repository machine
    _run_command((
        'scp {}/{} {}@{}:{}'
        ).format(
            temp_dir_host,
            public_key_file,
            repository_machine_user,
            repository_machine,
            repository_machine_ssh_dir))

    # add the key file to authorized_keys
    authorized_keys_file = repository_machine_ssh_dir + '/authorized_keys'
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
        repository_machine_user,
        repository_machine,
        authorized_keys_file,
        container_name,
        repository_machine_ssh_dir,
        public_key_file)
    _run_command(command)

    # Add the repository machine as known host to prevent the authentication request on the first
    # connect
    _run_command_in_container(
        container_name,
        '/bin/bash '+ container_home_directory +'/' + _ADDKNOWNHOST_SCRIPT + ' ' + repository_machine,
        'jenkins')


def _grant_jenkins_master_ssh_access_to_jenkins_linux_slave(config_values):
    print('----- Grant '+_JENINS_MASTER_CONTAINER+' ssh access to '+_FULL_LINUX_JENKINS_SLAVE_NAME)
    public_key_file = _JENINS_MASTER_CONTAINER + _PUBLIC_KEY_FILE_POSTFIX

    # COPY AND REGISTER THE PUBLIC KEY WITH THE SLAVE
    # Jenkins handles linux slaves with an ssh connection.
    _run_command(
        'docker cp {0}/{1} {2}:{3}/.ssh/authorized_keys'.format(
            config_values['HostJenkinsMasterShare'],
            public_key_file,
            _FULL_LINUX_JENKINS_SLAVE_NAME,
            _JENKINS_HOME_JENKINS_SLAVE_CONTAINER))
    # Add slave as known host to prevent the authentication request on the first connect
    _add_remote_to_known_ssh_hosts_of_jenkins_master(_JENKINS_LINUX_SLAVE_CONTAINER_IP)


def _grant_jenkins_master_ssh_access_to_jenkins_windows_slave(config_values, jenkins_slave_machine_windows_password):

    jenkins_workspace_host = config_values['HostJenkinsMasterShare']
    jenkins_slave_machine_windows = config_values['BuildSlaveWindowsMachine']
    jenkins_slave_machine_windows_user = config_values['BuildSlaveWindowsMachineUser']

    print((
        "----- Grant {0} ssh access to {1}"
        ).format(_JENINS_MASTER_CONTAINER, jenkins_slave_machine_windows))

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


def _add_remote_to_known_ssh_hosts_of_jenkins_master(remote_machine):
    """
    remoteMachine can be an IP or machine name.
    """
    runScriptCommand = (
        '/bin/bash ' + _JENKINS_HOME_JENKINS_MASTER_CONTAINER +
        '/' + _ADDKNOWNHOST_SCRIPT + ' ' + remote_machine)
    _run_command_in_container(
        _JENINS_MASTER_CONTAINER,
        runScriptCommand,
        'jenkins')


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


def _get_slave_start_command(slave_machine, slave_machine_user, slave_jar_dir):
    """
    defines the command that is used to start the slaves via ssh.
    """
    start_command = (
        'ssh {0}@{1} java -jar {2}/slave.jar'
        ).format(slave_machine_user, slave_machine, slave_jar_dir)
    return start_command


def _get_slave_labels_string(base_label_name, max_index):
    labels = []
    # We add multiple labels with indexes, because the jenkins pipeline model
    # requires a label for each node-name and node-names need to be different
    # for nodes that are run in parallel.
    for i in range(max_index + 1):
        # The version must be in the label, to make sure that we can change
        # the nodes and still build old versions of a package no the old nodes.
        labels.append(base_label_name + '-' + cppcodebasemachines_version.CPPCODEBASEMACHINES_VERSION + '-' + str(i))
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
    clear_directory(node_dir)

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
