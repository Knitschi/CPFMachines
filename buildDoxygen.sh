#!/bin/sh

# This script is used to compile doxygen from source
set -e

echo -------------- Build Doxygen ---------------

DOXYGEN_VERSION=1.8.14

# cleanup
rm -rf doxygen-$DOXYGEN_VERSION || true
rm doxygen-$DOXYGEN_VERSION.src.tar.gz || true

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
#wget ftp://ftp.stack.nl/pub/users/dimitri/doxygen-$DOXYGEN_VERSION.src.tar.gz #this did not work the last time
wget https://sourceforge.net/projects/doxygen/files/rel-$DOXYGEN_VERSION/doxygen-$DOXYGEN_VERSION.src.tar.gz # this is slow (sometimes)
tar xf doxygen-$DOXYGEN_VERSION.src.tar.gz

# build and install doxygen
cd doxygen-$DOXYGEN_VERSION
mkdir build
cd build
# cmake -Dbuild_search=ON -DCMAKE_CXX_COMPILER=/usr/bin/gcc -G "Unix Makefiles" ..
# disable the clang option because the debian cmake clang package is currently buggy (21.01.2018)
cmake -Dbuild_search=ON -G "Unix Makefiles" .. # -Duse_libclang=ON -DClang_DIR=/usr/lib/cmake 
make -j$(nproc)
make install

# cleanup
cd ../..
rm -rf doxygen-$DOXYGEN_VERSION
rm doxygen-$DOXYGEN_VERSION.src.tar.gz
