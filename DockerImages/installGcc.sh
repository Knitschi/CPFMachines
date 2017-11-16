#!/bin/sh


# This script uses apt-get to install everything that is needed to compile c++ projects with g++
set -e

echo -------------- Install GCC ---------------

apt-get -q update && apt-get -q -y install \
build-essential
