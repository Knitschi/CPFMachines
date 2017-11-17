#!/bin/sh

# This script downloads the qt sources, builds and installs qt.
set -e

echo -------------- Build Qt base ---------------

VERSION=5.5.1
PACKAGE_NAME=qtbase-opensource-src-$VERSION


# Install dependencies
apt-get install -y \
wget \
libgl1-mesa-dev \
libfontconfig1-dev \
libfreetype6-dev \
libx11-dev \
libxext-dev \
libxfixes-dev \
libxi-dev \
libxrender-dev \
libxcb1-dev \
libx11-xcb-dev \
libxcb-glx0-dev \
libxcb-keysyms1-dev \
libxcb-image0-dev \
libxcb-shm0-dev \
libxcb-icccm4-dev \
libxcb-sync0-dev \
libxcb-xfixes0-dev \
libxcb-shape0-dev \
libxcb-randr0-dev \
libxcb-render-util0-dev


# get source package
wget http://download.qt.io/archive/qt/5.5/5.5.1/submodules/$PACKAGE_NAME.tar.gz
gunzip $PACKAGE_NAME.tar.gz    # uncompress the archive
tar xf $PACKAGE_NAME.tar       # unpack it

# build and install doxygen
cd $PACKAGE_NAME

# compile and install release version
./configure -prefix /usr/local/Qt-5.5.1/release -release -opensource -confirm-license -c++11 -no-qml-debug -nomake examples -nomake tests 
make -j4
make install

# compile and install debug version

# clean the build dir
cd ..
rm -rf $PACKAGE_NAME
tar xf $PACKAGE_NAME.tar
cd $PACKAGE_NAME

./configure -prefix /usr/local/Qt-5.5.1/debug -debug -opensource -confirm-license -c++11 -no-qml-debug -nomake examples -nomake tests
make -j4
make install

cd ..
