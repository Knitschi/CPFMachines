"""
This module holds functionality for executing commands and filesystem operations in containers and host machines.
"""

import paramiko
import getpass
import weakref
import time


from . import config_data


class ConnectionsHolder:
    """
    This class holds the ssh connections to all the host machines in the CPF infrastucture.
    """

    def __init__(self, host_machine_infos):
        self._connection_holders = {}
        self._establish_host_machine_connections(host_machine_infos)


    def _establish_host_machine_connections(self, host_machine_infos):
        """
        Reads the machine login date from a config file dictionary.
        Returns a map that contains machine ids as keys and HostMachineInfo objects as values.
        """
        for info in host_machine_infos:
            self._connection_holders[info.machine_id] = ConnectionHolder(info)


    def get_connection(self, machine_id):
        return self._connection_holders[machine_id]


class ConnectionHolder:
    """
    This class stores a paramiko ssh and sftp connection and
    closes them when deleted.
    """

    _CONNECTION_TIMEOUT = 10
    _DEFAULT_SSH_PORT = 22

    @property
    def removed(self):
        return not self._finalizer.alive


    def __init__(self, host_info):
        """
        Connections are opened during construction.
        """
        self.info = host_info
        self._ssh_client = paramiko.SSHClient()

        # prompt for password if it was not provided in the file
        if not self.info.user_password:
            prompt_message = "Please enter the password for account {0}@{1}.".format(self.info.user_name, self.info.host_name)
            self.info.user_password = getpass.getpass(prompt_message)

        # make the connection
        self._ssh_client.load_system_host_keys()
        #connection.ssh_client.set_missing_host_key_policy(paramiko.WarningPolicy)
        self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self._ssh_client.connect(
                self.info.host_name,
                port=self._DEFAULT_SSH_PORT,
                username=self.info.user_name,
                password=self.info.user_password,
                timeout=self._CONNECTION_TIMEOUT
            )
        except Exception as err:
            print('Failed to connect to ssh account {0}@{1} with {2} seconds timeout'.format(self.info.user_name, self.info.host_name, self._CONNECTION_TIMEOUT))
            raise err

        self.sftp_client = self._ssh_client.open_sftp()
        
        # object to close open connections when the object is destroyed
        self._finalizer = weakref.finalize(self, self._close_connections)


    def _close_connections(self):
        self.sftp_client.close()
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
        if print_command:
            print(self._prepend_machine_id(command))

        stdin, stdout, stderr = self._ssh_client.exec_command(command, get_pty=True)

        # print output as soon as it is produced
        out_list = []
        for line in iter(stdout.readline, ""):
            
            # add the line without line separators
            out_list.append(line.rstrip()) 

            if print_output:
                print(self._prepend_machine_id(line), end="")

            # Paramiko sometimes does not close the channel after the command is done.
            # See https://github.com/paramiko/paramiko/issues/109
            # The exit code is however set. With this we can close the channel
            # and prevent infinite loops.
            if stdout.channel.exit_status_ready():
                stdout.channel.close()
                stderr.channel.close()

        err_list = stderr.readlines()
        err_list = self._remove_line_separators(err_list)
        retcode = stdout.channel.recv_exit_status()

        if not ignore_return_code and retcode != 0:
            if not print_output:                         # always print the output in case of an error
                self._print_output(out_list, err_list)
            error = 'Command "{0}" executed on host {1} returned error code {2}.'.format(command, self.info.machine_id, str(retcode))
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
        return "[{0}] ".format(self.info.machine_id) + string


def _print_string_list(list):
    for string in list:
        print(string)


    