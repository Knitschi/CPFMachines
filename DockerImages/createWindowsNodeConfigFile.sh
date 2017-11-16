#!/bin/sh

# This script creates the xml config files for the jenkins windows slave nodes.

# Arg 1 is the slave name
# Arg 2 is the slave IP
set -e

slaveName=$1
scriptDir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
nodeDir=$scriptDir/JenkinsConfig/nodes/$slaveName

addLine()
{
    echo $1 >> $nodeDir/config.xml
}

# clear the nodes directory
rm -rf $nodeDir
mkdir $nodeDir


addLine "<?xml version='1.0' encoding='UTF-8'?>"
addLine "<slave>"
addLine "  <name>$slaveName</name>"
addLine "  <description>A Windows 10 build slave based on a virtual machine.</description>"
addLine "  <remoteFS>C:\jenkins</remoteFS>"
addLine "  <numExecutors>1</numExecutors>"
addLine "  <mode>NORMAL</mode>"
addLine '  <retentionStrategy class="hudson.slaves.RetentionStrategy$Always"/>'
addLine '  <launcher class="hudson.slaves.CommandLauncher">'
addLine '    <agentCommand>ssh Knitschi@buildknechtwin java -jar C:/jenkins/slave.jar</agentCommand>'
addLine '  </launcher>'
addLine "  <label>Windows-10 Windows-10-0 Windows-10-1 Windows-10-2 Windows-10-3 Windows-10-4</label>"
addLine "  <nodeProperties/>"
addLine "</slave>"

