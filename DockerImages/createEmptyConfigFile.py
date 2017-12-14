import sys
import json
import collections

def main():
    """
    Entry point of the script.
    """
    # create an empty dictionary with all possible config values.

    configDict = {
        'RepositoryMachineName' : '',               # The naeme of the machine that holds the repository
        'RepositoryMachineUser' : '',               # A user on the repository machine that can access the repository
        'RepositoryMachineSSHDir' : '',             # The .ssh configuration directory for the RepositoryMachineUser
        'HostJenkinsMasterShare' : '',              # A directory on the docker host machine that will contain the jenkins home directory of the jenkins master container.
        'HostHTMLShare' : '',                       # A directory on the docker host machine that is used to transfer the content of the web-page from the jenkins master to the webserver.
        'HostTempDir' : '',                         # A directory on the docker host that can be used to operate on intermediate files.
        'BuildSlaveWindowsMachine' : '',            # The name of the machine that is used as a windows build slave.
        'BuildSlaveWindowsMachineUser' : '',        # A user on the BuildSlaveWindowsMachine
        'BuildSlaveWindowsMachinePassword' : '',    # An optionally provided password for the BuildSlaveWindowsMachineUser. If none is provided, you will be prompted to enter one during script execution.
        'UseUnconfiguredJenkinsMaster' : False,     # If this is set to true, the jenkins master will be left in the fresh installation state without initializing existing general settings, accounts, jobs and build-slave.
                                                    # This is useful when no previously made settings exist.
        'JenkinsAdminUser' : '',                    # The name of an initial jenkins user with administrative rights.
        'JenkinsAdminUserPassword' : '',            # An optionally provided password for the JenkinsAdminUserName. If none is provided, you will be prompted to enter one during script execution.
        'JenkinsAccountconfig_files' : {},           # A map with user names as keys and the location of their config.xml account configuration files, relative to the generated config file.
        'JenkinsJobsconfig_files' : {}               # A map with jenkins job names as keys and the location of their config.xml job configuration files, relative to the generated config file.
    }
    config_values = collections.OrderedDict(sorted(configDict.items(), key=lambda t: t[0]))

    config_file = 'EmptyConfig.json'
    with open(config_file, 'w') as file:
        json.dump(config_values, file, indent=2)


if __name__ == '__main__':
    sys.exit(main())
