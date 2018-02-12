"""
This module holds functionality for executing commands and filesystem operations in containers and host machines.
"""

import paramiko
import getpass
import weakref

from . import config_data


class RemoteCommandExecutor:
    """
    This class holds data and connections that are required for executing remote commands.
    Connections to the remote machines are opened during construction.
    """


    def __init__(self, config):

        self._hosts = _get_host_machine_infos(config)
        self._container_dict = _get_container_machine_dictionary(config)

        self._connection_holders = {}
        self._establish_host_machine_connections()


    def _establish_host_machine_connections(self):
        """
        Reads the machine login date from a config file dictionary.
        Returns a map that contains machine ids as keys and HostMachineInfo objects as values.
        """
        for machine_id, host in self._hosts.items():
            self._connection_holders[machine_id] = ConnectionHolder(host.host_name, host.user, host.password)


    def _get_container_connection(self, container):
        """
        Returns the connection to the host machine that hosts the given container
        or None if there is no such container.
        """
        return self._connection_holders[self._container_dict[container]]


    def remove_all_container(self):
        """
        Stop and remove all containers of the CPF infrastructure.
        """
        for container in self._container_dict:
            self._stubbornly_remove_container(container)
    

    def _stubbornly_remove_container(self, container):
        """
        Removes a given docker container even if it is running.
        If the container does not exist, the function does nothing.
        """
        connection = self._get_container_connection(container)
        if self._container_exists(connection, container):
            if self._container_is_running(connection, container):
                self._stop_docker_container(connection, container)
            self._remove_container(connection, container)


    def _container_exists(self, connection, container):
        """
        Returns true if the container exists on the host.
        """
        connection = self._get_container_connection(container)
        all_container = self._get_all_docker_container(connection)
        return container in all_container


    def _get_all_docker_container(self, connection):
        return connection.run_command("docker ps -a --format '{{.Names}}'")


    def _container_is_running(self, connection, container):
        """
        Returns true if the container is running on its host.
        """
        running_container = self._get_running_docker_container(connection)
        return container in running_container


    def _get_running_docker_container(self, connection):
        return connection.run_command("docker ps --format '{{.Names}}'")


    def _stop_docker_container(self, connection, container):
        connection.run_command('docker stop ' + container)


    def _start_docker_container(self, connection, container):
        connection.run_command('docker start ' + container)


    def _remove_container(self, connection, container):
        """
        This removes a given docker container and will fail if the container is running.
        """
        connection = self._get_container_connection(container)
        connection.run_command('docker rm -f ' + container)


    def remove_all_docker_networks(self, network_name):
        """
        Removes the CFP docker networks from all docker instances.
        """
        container_machines = set(self._container_dict.values())
        for machine_id in container_machines:
            self._remove_docker_network(machine_id, network_name)


    def _remove_docker_network(self, machine_id, network):
        connection = self._hosts[machine_id]
        network_lines = connection.run_command('docker network ls')
        networks = []
        for line in network_lines:
            columns = line.split()
            networks.append(columns[1])

        if network in networks:
            connection.run_command('docker network rm ' + network)


def _print_string_list(list):
    for string in list:
        print(string)


def _get_host_machine_infos(config):
    info_dict = {}
    for info in config.host_machine_infos:
        info_dict[info.machine_id] = info
    return info_dict


def _get_container_machine_dictionary(config):
    """
    Returns a dictionary with all docker container as keys and
    the associated host machine_ids as values.
    """
    id_dict = {}
    id_dict[config.jenkins_master_host_config.container_conf.container_name] = config.jenkins_master_host_config.machine_id
    id_dict[config.web_server_host_config.container_conf.container_name] = config.web_server_host_config.machine_id
    for slave_config in config.jenkins_slave_configs:
        if slave_config.container_conf:
            id_dict[slave_config.container_conf.container_name] = slave_config.machine_id
    
    # Note that RemoteCommandExecutor expects all container names to be unique across all hosts.
    if not len(id_dict) == 2 + len(config.jenkins_slave_configs):
        raise Exception('Container names must be unique over all hosts.')

    return id_dict


class ConnectionHolder:
    """
    This class stores a paramiko ssh and sftp connection and
    closes them when deleted.
    """

    _CONNECTION_TIMEOUT = 2
    _DEFAULT_SSH_PORT = 22

    @property
    def removed(self):
        return not self._finalizer.alive


    def __init__(self, host_name, user, password):
        """
        Connections are opened during construction.
        """
        
        self._ssh_client = paramiko.SSHClient()

        # prompt for password if it was not provided in the file
        if not password:
            prompt_message = "Please enter the password for account {0}@{1}.".format(user, host_name)
            password = getpass.getpass(prompt_message)

        # make the connection
        self._ssh_client.load_system_host_keys()
        #connection.ssh_client.set_missing_host_key_policy(paramiko.WarningPolicy)
        self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._ssh_client.connect(
            host_name,
            port=self._DEFAULT_SSH_PORT,
            username=user,
            password=password,
            timeout=self._CONNECTION_TIMEOUT
        )

        self._sftp_client = self._ssh_client.open_sftp()
        
        # object to close open connections when the object is destroyed
        self._finalizer = weakref.finalize(self, self._close_connections)


    def _close_connections(self):
        self._sftp_client.close()
        self._ssh_client.close()


    def remove(self):
        self._finalizer()


    def run_command(self, command, print_output=False, print_command=False, ignore_return_code=False):
        """
        The function runs a console command on the remote host machine via the paramiko ssh client.
        The function returns the output of the command as a list of strings, where each element
        in the list is a line in the output. 

        The function throws if the return code is not zero and ignore_return_code is set to False.
        """
        stdin, stdout, stderr = self.ssh_client.exec_command(command, get_pty=True)

        if print_command:
            print(self._prepend_machine_id(command))

        # print output as soon as it is produced
        out_list = []
        if print_output:
            for line in iter(stdout.readline, ""):
                out_list.append(line.rstrip()) # add the line without line separators
                print(self._prepend_machine_id(line), end="")
        else:
            out_list = stdout.readlines()
            out_list = self._remove_line_separators(out_list)

        err_list = stderr.readlines()
        err_list = self._remove_line_separators(err_list)
        retcode = stdout.channel.recv_exit_status()

        if not ignore_return_code and retcode != 0:
            if not print_output:                         # always print the output in case of an error
                self._print_output(out_list, err_list)
            error = 'Command "{0}" executed on host {1} returned error code {2}.'.format(command, self.machine_id, str(retcode))
            raise Exception(error)

        return out_list


    def _remove_line_separators(self, stringlist):
        new_list = []
        for string in stringlist:
            new_list.append(string.rstrip())
        return new_list


    def _print_output(self, out_list, err_list):
        out_list = self._prepend_machine_ids(out_list)
        _print_string_list(out_list)
        err_list = self._prepend_machine_ids(err_list)
        _print_string_list(err_list)


    def _prepend_machine_ids(self, stringlist):
        return [ (self._prepend_machine_id(string)) for string in stringlist]


    def _prepend_machine_id(self, string):
        return "[{0}] ".format(self.machine_id) + string


    