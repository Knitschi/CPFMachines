#!/bin/sh

# This script is used to compile doxygen from source
set -e

echo -------------- Build Doxygen ---------------

DOXYGEN_VERSION=1.8.13

# GET PACKAGES FOR DOXYGEN BUILD
# install more tools needed to build doxygen
apt-get -y update && apt-get install -y \
bison \
flex \
libxapian-dev \
python3 \
wget \
build-essential \
zlib1g-dev \
cmake

cmake --version
gcc --version
g++ --version
python3 --version

# get doxygen sources
wget ftp://ftp.stack.nl/pub/users/dimitri/doxygen-$DOXYGEN_VERSION.src.tar.gz
gunzip doxygen-$DOXYGEN_VERSION.src.tar.gz    # uncompress the archive
tar xf doxygen-$DOXYGEN_VERSION.src.tar       # unpack it

# build and install doxygen
cd doxygen-$DOXYGEN_VERSION
mkdir build
cd build
# cmake -Dbuild_search=ON -DCMAKE_CXX_COMPILER=/usr/bin/gcc -G "Unix Makefiles" ..
cmake -Dbuild_search=ON -Duse_libclang=ON -G "Unix Makefiles" ..
make -j4
make install
