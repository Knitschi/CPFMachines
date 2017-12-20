#!/bin/sh

# This script installs the current version of ctags (https://github.com/universal-ctags/ctags)
# Which is a dependency of the abi-compliance-checker tools.
set -e

archive=master.zip
extractDir=ctags-master

# download and extract
wget https://github.com/universal-ctags/ctags/archive/$archive
unzip $archive

# install
cd $extractDir
sh ./autogen.sh
./configure --prefix=/usr
make
make install

# clean up the downloaded files
rm -rf $extractDir