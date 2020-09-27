#!/bin/sh

# This script downloads the python sources, builds and installs
set -e

echo -------------- Build Python ---------------

VERSION=3.6.12

# Install dependencies
apt-get -y update && apt-get install -y \
libreadline-gplv2-dev \
libncursesw5-dev \
libssl-dev \
libsqlite3-dev \
tk-dev \
libgdbm-dev \
libc6-dev \
libbz2-dev

# get source package
wget https://www.python.org/ftp/python/$VERSION/$PACKAGE_NAME 
tar -zxf $PACKAGE_NAME

cd $BUILD_DIR

./configure --enable-optimizations
make all -j$(nproc)
make install

# clean the build dir
cd ..
rm -rf $BUILD_DIR
rm $PACKAGE_NAME
