#!/bin/bash
#
# This script finds out to which branch a push happened and triggers the build job for that branch on the buildserver. 
# Argument 1: The name of the reference that belongs to the pushed branch. This looks something like refs/heads/Knitschi-int-master
#

refname=$1

# The base url of the jenkins server on which a job is triggered
jenkinsUrl="http://knitschi@feldrechengeraet:8080"
# Change this to a user and a password that is used on your jenkins server for doing the automated integration of a commit.
jenkinsUser="CaptainGitHook"
jenkinsPassword="1234temp"

# Get the name of the buildjob by assuming that the repository base directory and the build job both have the name of the build package
dirName=$(basename "$PWD")
# remove the .git extension from the repo directory
packageName=${dirName/.git/} 

# Get the branch name from the refname argument
branch=$(git rev-parse --symbolic --abbrev-ref $refname)

# filter out pushes that do noot seem to belong to a developer branch
filterPattern="^.*-int-.*$"

if [[ "$branch" =~ $filterPattern ]]; then 

echo "Trigger jenkins job" $packageName "for branch" $branch

# Trigger the parameterized build-job and pass it the branch name as argument.
curl $jenkinsUrl/job/$packageName/build \
--user $jenkinsUser:$jenkinsPassword \
--data-urlencode json='{"parameter": [{"name":"branchOrTag", "value":"'$branch'"}]}'

fi

