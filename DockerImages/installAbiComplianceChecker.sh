#!/bin/sh

# This script downloads the git sources, builds and installs
set -e


echo -------------- Install abi-dumper  ---------------

VERSION=1.1

# Install dependencies by installing an old version
apt-get update && apt-get install -y \
elfutils \
abi-compliance-checker


PACKAGE_NAME=$VERSION.tar.gz
BUILD_DIR=abi-dumper-$VERSION

# get source package
wget https://github.com/lvc/abi-dumper/archive/$PACKAGE_NAME
tar -zxf $PACKAGE_NAME

cd $BUILD_DIR

make install prefix=/usr

# clean the build dir
cd ..
rm -rf $BUILD_DIR
rm $PACKAGE_NAME


echo -------------- Install abi-compliance-checker  ---------------

VERSION=2.2

PACKAGE_NAME=$VERSION.tar.gz
BUILD_DIR=abi-compliance-checker-$VERSION

# get source package
wget https://github.com/lvc/abi-compliance-checker/archive/$PACKAGE_NAME
tar -zxf $PACKAGE_NAME

cd $BUILD_DIR

make install prefix=/usr

# clean the build dir
cd ..
rm -rf $BUILD_DIR
rm $PACKAGE_NAME
