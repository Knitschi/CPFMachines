
import sys
import json
import io
import collections

def main():
    
    # create an empty dictionary with all possible config values.

    configDict = {
        'RepositoryMachineName' : '',
        'RepositoryMachineUser' : '',
        'RepositoryMachineSSHDir' : '',
        'HostJenkinsMasterShare' : '',
        'HostHTMLShare' : '',
        'HostTempDir' : '',
        'BuildSlaveWindowsMachine' : '',
        'BuildSlaveWindowsMachineUser' : '',
        'JenkinsAccountConfigFiles' : {}
        'JenkinsJobsConfigFiles' : {}
    }
    configValues = collections.OrderedDict(sorted(configDict.items(), key=lambda t: t[0]))

    configFile = 'CppCodeBaseConfig.json'
    with open(configFile, 'w') as file:
        json.dump(configValues, file, indent=2)


if __name__ == '__main__':
    sys.exit(main())

