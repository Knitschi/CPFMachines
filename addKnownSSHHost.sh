#!/bin/sh

# This script makes sure that we need not confirm connecting to an unknown host when opening the first ssh connection 
# to the machine given in the first argument.
set -e

ssh-keyscan -H -t rsa -p $2 $1 >> ~/.ssh/known_hosts