#!/bin/sh

# This script is used to compile and install CMake from source because the version of the debian package was too old.
set -e

echo -------------- Build CMake ---------------

# install dependencies for cmake build
apt-get -y update && apt-get install -y \
libcurl4 \
curl \
libcurl4-gnutls-dev \
zlib1g \
zlib1g-dev \
libssl-dev


CMAKE_BUILD_DIR=TempCMakeBuild

git clone https://gitlab.kitware.com/cmake/cmake.git $CMAKE_BUILD_DIR

cd $CMAKE_BUILD_DIR
git checkout v3.22.1

# hunter needs the --system-curl option to enable downloading with https.
./bootstrap --system-curl
make -j$(nproc)
make install
cd ..
rm -r $CMAKE_BUILD_DIR