"""
Contains functions for fileoperations between the local machine, host machines and docker containers.
"""

import stat
import os
import shutil
from pathlib import PureWindowsPath, PurePosixPath, PurePath

from .connections import ConnectionHolder
from . import dockerutil


_SCRIPT_DIR = PurePath(os.path.dirname(os.path.realpath(__file__)))


def clear_rdirectory(sftp_client, directory):
    """
    This functions deletes the given directory and all its content and recreates it.
    It does it on the given machine.
    """
    if rexists(sftp_client, directory):
        rrmtree(sftp_client, directory)
    rmakedirs(sftp_client, directory)


def rexists(sftp_client, path):
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


def rrmtree(sftp_client, dir_path):
    """
    Removes the remote directory and its content.
    """
    for item in sftp_client.listdir_attr(str(dir_path)):
        rpath = dir_path.joinpath(item.filename)
        if stat.S_ISDIR(item.st_mode):
            rrmtree(sftp_client, rpath)
        else:
            rpath = dir_path.joinpath(item.filename)
            sftp_client.remove(str(rpath))

    sftp_client.rmdir(str(dir_path))


def rmakedirs(sftp_client, dir_path):
    """
    Creates a remote directory and all its parent directories.
    """
    # create a list with all sub-pathes, where the longer ones come first.
    pathes = [dir_path]
    pathes.extend(dir_path.parents) 
    # now create all sub-directories, starting with the shortest pathes
    for parent in reversed(pathes): 
        if not rexists(sftp_client, parent):
            sftp_client.mkdir(str(parent))


def guarantee_directory_exists(sftp_client, dir_path):
    if not rexists(sftp_client, dir_path):
        rmakedirs(sftp_client, dir_path)


def copy_local_files_to_host(connection, source_dir, context_dir, text_files, binary_files=[]):
    """
    context_dir is the directory on the host that is used as a build context for the container.
    source_dir is the absolute directory on the machine executing the script that contains the files
    required for building the container.
    """
    source_dir = PurePath(source_dir)

    # copy text files to the host
    for file_path in text_files:
        source_path = source_dir.joinpath(file_path)
        target_path = context_dir.joinpath(file_path)
        # Copy the file.
        copy_textfile_from_local_to_linux(connection, source_path, target_path)

    # copy binary files to the host
    for file_path in binary_files:
        source_path = source_dir.joinpath(file_path)
        target_path = context_dir.joinpath(file_path)
        # Copy the file.
        copy_file_from_local_to_remote(connection.sftp_client, source_path, target_path)


def copy_textfile_from_local_to_linux(connection, source_path, target_path):
    """
    This function ensures that the file-endings of the text-file are set to linux
    convention after the copy.
    """
    copy_file_from_local_to_remote(connection.sftp_client, source_path, target_path)
    # Remove \r from file from windows line endings.
    # This may be necessary when the machine that executes this script
    # is a windows machine.
    temp_file = target_path.parent.joinpath('temp.txt')
    format_line_endings_command = "tr -d '\r' < '{0}' > '{1}' && mv {1} {0}".format(str(target_path), str(temp_file))
    connection.run_command(format_line_endings_command)


def copy_file_from_local_to_remote(sftp_client, source_path, target_path):
    """
    Copies a file to a host machine defined by connection, without changing it.
    """
    # make sure a directory for the target file exists
    rmakedirs(sftp_client, target_path.parent)
    sftp_client.put( str(source_path), str(target_path) )


def copy_textfile_to_container(connection, container_conf, source_path, target_path):
    """
    We first copy the file to host_temp_dir and then to the container.
    """
    host_file = connection.info.temp_dir.joinpath(source_path.name)
    copy_textfile_from_local_to_linux(connection, source_path, host_file)
    copy_file_from_host_to_container(connection, container_conf, host_file, target_path)


def copy_file_from_host_to_container(host_connection, container_conf, source_file, target_file):
    dockerutil.run_command_in_container(
        host_connection,
        container_conf,
        'mkdir -p {0}'.format(target_file.parent),
        print_command=False
    )
    host_connection.run_command("docker cp {0} {1}:{2}".format(source_file, container_conf.container_name, target_file))


def rtorcopy(source_sftp_client, target_sftp_client, source_file, target_file):
    """
    Copy a file from one remote machine to another.
    """
    local_temp_file = _SCRIPT_DIR.joinpath(source_file.name)
    source_sftp_client.get(str(source_file), str(local_temp_file))
    target_sftp_client.put(str(local_temp_file), str(target_file))
    os.remove(local_temp_file)


def rtocontainercopy(source_host_connection, target_host_connection, container_conf, source_file, target_file):
    """
    Copies the source_file from a host machine to the target target path target_file on a container.
    """
    temp_path_container_host = target_host_connection.info.temp_dir.joinpath(source_file.name)
    rtorcopy(source_host_connection.sftp_client, target_host_connection.sftp_client, source_file, temp_path_container_host)
    copy_file_from_host_to_container(target_host_connection, container_conf, temp_path_container_host, target_file)


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
    dir_content = get_dir_content(local_source_dir)
    for item in dir_content:
        source_path = local_source_dir.joinpath(item)
        if os.path.isfile(source_path):
            target_path = container_target_dir.joinpath(item)
            copy_textfile_to_container(container_host_connection, container_config, source_path, target_path)


def get_dir_content(directory):
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


def clear_dir(directory):
    """
    After calling this function the directory will exist and be empty.
    """
    if os.path.isdir(directory):
        shutil.rmtree(directory)
    os.makedirs(directory)