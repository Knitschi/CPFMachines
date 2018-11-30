#!/bin/sh

# This script downloads the qt sources, builds and installs qt.
set -e

echo -------------- Build Qt base ---------------

VERSION=5.9.1
VERSION_SHORT=5.9
PACKAGE_NAME=qtbase-opensource-src-$VERSION


# Install dependencies
apt-get update && apt-get install -y \
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
libxcb-render-util0-dev \
libssl1.0-dev # qt 5.9 requries libssl1.0. vor later qt-versions the the newer default version libssl1.1 may work.


# get source package
wget http://download.qt.io/archive/qt/$VERSION_SHORT/$VERSION/submodules/$PACKAGE_NAME.tar.xz
tar xf $PACKAGE_NAME.tar.xz    # uncompress the archive
#tar xf $PACKAGE_NAME.tar       # unpack it

# build and install doxygen
cd $PACKAGE_NAME

# compile and install release version
./configure -prefix /usr/local/Qt-$VERSION/release -release -opensource -confirm-license -c++std c++11 -no-qml-debug -nomake examples -nomake tests -qt-xcb
make -j$(nproc)
make install

# compile and install debug version

# clean the build dir
cd ..
rm -rf $PACKAGE_NAME
tar xf $PACKAGE_NAME.tar.xz
cd $PACKAGE_NAME

./configure -prefix /usr/local/Qt-$VERSION/debug -debug -opensource -confirm-license -c++std c++11 -no-qml-debug -nomake examples -nomake tests -qt-xcb
make -j$(nproc) 
make install

cd ..

rm -rf $PACKAGE_NAME
rm $PACKAGE_NAME.tar.xz


# Create symlink to uic because environment variables did not work.
# This is needed for the static conde analysis job.
cd /usr/local/bin
ln -s /usr/local/Qt-$VERSION/bin/uic uic
