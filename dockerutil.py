"""
Contains functions for basic remote container operations.
"""

from .connections import ConnectionHolder


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


def remove_docker_network(connection, network):
    network_lines = connection.run_command('docker network ls')
    networks = []
    for line in network_lines:
        columns = line.split()
        networks.append(columns[1])

    if network in networks:
        connection.run_command('docker network rm ' + network)


def create_docker_network(connection, name, subnet_ip):
    connection.run_command("docker network create --driver bridge --subnet={0} {1}".format(subnet_ip, name))


def docker_container_image_exists(connection, image_name):
    images = connection.run_command('docker images')
    return image_name in images


def build_docker_image(connection, image_name, docker_file, build_context_directory, build_args):
    build_args_string = ''
    for arg in build_args:
        build_args_string += ' --build-arg ' + arg

    command = (
        'docker build' + build_args_string + ' -t ' + image_name +
        ' -f ' + str(docker_file) + ' ' + str(build_context_directory)
    )
    connection.run_command(command, print_output=True, print_command=True)


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