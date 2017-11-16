#!/bin/sh

# This script downloads the git sources, builds and installs
set -e

echo -------------- Build Git ---------------

VERSION=2.14.2


# Install dependencies
apt-get -y update && apt-get install -y \
dh-autoreconf \
libcurl4-gnutls-dev \
libexpat1-dev \
gettext \
zlib1g-dev \
libssl-dev


PACKAGE_NAME=v$VERSION.tar.gz
BUILD_DIR=git-$VERSION

# get source package
wget https://github.com/git/git/archive/$PACKAGE_NAME
tar -zxf $PACKAGE_NAME

cd $BUILD_DIR

make configure
./configure --prefix=/usr
make all -j4
make install

# clean the build dir
cd ..
rm -rf $BUILD_DIR
rm $PACKAGE_NAME
