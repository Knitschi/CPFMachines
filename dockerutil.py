"""
Contains functions for basic remote container operations.
"""

import os

from .connections import ConnectionHolder
from . import fileutil

def container_exists(connection, container):
    """
    Returns true if the container exists on the host.
    """
    all_container = get_all_docker_container(connection)
    return container in all_container


def get_all_docker_container(connection):
    return connection.run_command("docker ps -a --format '{{.Names}}'")


def container_is_running(connection, container):
    """
    Returns true if the container is running on its host.
    """
    running_container = get_running_docker_container(connection)
    return container in running_container


def get_running_docker_container(connection):
    return connection.run_command("docker ps --format '{{.Names}}'")


def stop_docker_container(connection, container):
    connection.run_command('docker stop ' + container)


def start_docker_container(connection, container):
    connection.run_command('docker start ' + container)


def remove_container(connection, container):
    """
    This removes a given docker container and will fail if the container is running.
    """
    connection.run_command('docker rm -f ' + container)


def docker_container_image_exists(connection, image_name):
    images = connection.run_command('docker images')
    return image_name in images


def build_docker_image(connection, image_name, context_source_dir, docker_file, build_args, text_files, binary_files=[]):
    
    context_target_dir = connection.info.temp_dir.joinpath(image_name)
    fileutil.copy_local_files_to_host(connection, context_source_dir, context_target_dir, text_files, binary_files)
    
    build_args_string = ''
    for arg in build_args:
        build_args_string += ' --build-arg ' + arg

    command = (
        'docker build' + build_args_string + ' -t ' + image_name +
        ' -f ' + str(context_target_dir.joinpath(docker_file)) + ' ' + str(context_target_dir)
    )
    connection.run_command(command, print_output=True, print_command=True)


def docker_run_detached(host_connection, container_config):
    
    publish_port_args = ''
    for host_port, container_port in container_config.published_ports.items():
        publish_port_args += '--publish {0}:{1} '.format(host_port, container_port)

    volume_args = ''
    for host_dir, container_dir in container_config.host_volumes.items():
        volume_args += '--volume {0}:{1} '.format(host_dir, container_dir)

    env_args = ''
    for variable in container_config.envvar_definitions:
        env_args += '--env {0} '.format(variable)

    command = (
        'docker run '
        '--detach '
        '--name ' + container_config.container_name + ' ' +
        '--restart unless-stopped '
        + publish_port_args 
        + volume_args
        + env_args
        + container_config.container_image_name
    )
    host_connection.run_command(command, print_command=True)

def run_commands_in_container(host_connection, container_config, commands, user=None):
    for command in commands:
        run_command_in_container(
            host_connection,
            container_config,
            command,
            user
        )


def run_command_in_container(connection, container_config, command, user=None, print_command=True):
    """
    The user option can be used to run the command for a different user then
    the containers default user.
    """
    user_option = ''
    if not user:
        user = container_config.container_user
    user_option = '--user ' + user + ':' + user + ' '
    command = 'docker exec ' + user_option + container_config.container_name + ' ' + command
    output = connection.run_command(command, print_command=print_command)
    return output


def copy_textfile_to_container(connection, container_conf, source_path, target_path):
    """
    We first copy the file to host_temp_dir and then to the container.
    """
    host_file = connection.info.temp_dir.joinpath(source_path.name)
    fileutil.copy_textfile_from_local_to_linux(connection, source_path, host_file)
    copy_file_from_host_to_container(connection, container_conf, host_file, target_path)


def copy_file_from_host_to_container(host_connection, container_conf, source_file, target_file):
    run_command_in_container(
        host_connection,
        container_conf,
        'mkdir -p {0}'.format(target_file.parent),
        print_command=False
    )
    host_connection.run_command("docker cp {0} {1}:{2}".format(source_file, container_conf.container_name, target_file))


def container_to_container_copy(source_host_connection, source_container_conf, target_host_connection, target_container_conf, source_file, target_file):
    """
    Copies a file from one container to another.
    """
    # copy from source container to source host
    temp_path_source_host = source_host_connection.info.temp_dir.joinpath(source_file.name)
    source_host_connection.run_command('docker cp {0}:{1} {2}'.format(source_container_conf.container_name, source_file, temp_path_source_host))

    # copy from source host to target container
    rtocontainercopy(source_host_connection, target_host_connection, target_container_conf, temp_path_source_host, target_file)


def copy_local_textfile_tree_to_container(local_source_dir, container_host_connection, container_config, container_target_dir):
    """
    Copy the contents of a local directory to a container directory.
    """
    dir_content = fileutil.get_dir_content(local_source_dir)
    for item in dir_content:
        source_path = local_source_dir.joinpath(item)
        if os.path.isfile(str(source_path)):
            target_path = container_target_dir.joinpath(item)
            copy_textfile_to_container(container_host_connection, container_config, source_path, target_path)


def rtocontainercopy(source_host_connection, target_host_connection, container_conf, source_file, target_file):
    """
    Copies the source_file from a host machine to the target target path target_file on a container.
    """
    temp_path_container_host = target_host_connection.info.temp_dir.joinpath(source_file.name)
    fileutil.rtorcopy(source_host_connection.sftp_client, target_host_connection.sftp_client, source_file, temp_path_container_host)
    copy_file_from_host_to_container(target_host_connection, container_conf, temp_path_container_host, target_file)


def containertorcopy(source_host_connection, container_conf, target_host_connection, source_file, target_file):
    """
    Copies a file from a container to an ssh host.
    """
    sftp_client = source_host_connection.sftp_client
    temp_dir_chost = source_host_connection.info.temp_dir
    fileutil.guarantee_directory_exists(sftp_client, temp_dir_chost)
    
    # delete previously copied key-files
    full_temp_public_key_file = temp_dir_chost.joinpath(source_file.name)
    if fileutil.rexists(sftp_client, full_temp_public_key_file):
        sftp_client.remove(full_temp_public_key_file)

    # Copy the public key from the jenkins home directory to the
    # jenkins-workspace directory on the host
    source_host_connection.run_command('docker cp {0}:{1} {2}'.format(container_conf.container_name, source_file, full_temp_public_key_file))

    # Then copy it to the repository machine
    fileutil.rtorcopy(sftp_client, target_host_connection.sftp_client, full_temp_public_key_file, target_file)