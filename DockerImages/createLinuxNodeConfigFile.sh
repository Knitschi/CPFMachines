#!/bin/sh

# This script creates the xml config files for the jenkins linux slave nodes.

# Arg 1 is the slave name
# Arg 2 is the slave IP
set -e

slaveName=$1
IPSlave=$2
scriptDir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
nodeDir=$scriptDir/JenkinsConfig/nodes/$slaveName

addLine()
{
    echo $1 >> $nodeDir/config.xml
}

# clear the nodes directory
rm -rf $nodeDir
mkdir -p $nodeDir


addLine "<?xml version='1.0' encoding='UTF-8'?>"
addLine "<slave>"
addLine "   <name>$slaveName</name>"
addLine "   <description></description>"
addLine "   <remoteFS>/home/jenkins/workspaces</remoteFS>"
addLine " <numExecutors>1</numExecutors>"
addLine " <mode>NORMAL</mode>"
addLine ' <retentionStrategy class="hudson.slaves.RetentionStrategy$Always"/>'
addLine ' <launcher class="hudson.slaves.CommandLauncher">'
addLine "       <agentCommand>ssh $IPSlave java -jar ~/bin/slave.jar</agentCommand>"
addLine " </launcher>"
addLine " <label>Debian-8.9 Debian-8.9-0 Debian-8.9-1 Debian-8.9-2 Debian-8.9-3 Debian-8.9-4</label>"
addLine " <nodeProperties/>"
addLine "</slave>"



