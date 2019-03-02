#!/bin/sh

# This script installs the current version of ctags (https://github.com/universal-ctags/ctags)
# Which is a dependency of the abi-compliance-checker tools.
set -e

apt-get -q update && apt-get -q -y install autoconf autogen

archive=89811d9e.zip
extractDir=ctags-89811d9ec18bcff68d7a0d34050047ef7e9c61bc

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
