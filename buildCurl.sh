#!/bin/sh

# This script is used to compile and install libcurl from source or otherwise cmake can not be compiled with the --system-curl option which is needed for hunter
set -e

echo -------------- Build Curl ---------------

CURL_VERSION=7.52.1

apt-get remove curl -y

# get doxygen sources
wget https://curl.haxx.se/download/curl-$CURL_VERSION.tar.gz
gunzip curl-$CURL_VERSION.tar.gz    # uncompress the archive
tar xf curl-$CURL_VERSION.tar       # unpack it

# build and install doxygen
cd curl-$CURL_VERSION
./configure --with-ssl
make -j4
make install
cd ..
# rm -r curl-$CURL_VERSION


