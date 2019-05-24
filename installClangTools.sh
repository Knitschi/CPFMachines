#!/bin/sh


# This script uses apt-get to install libraries and tools related to the llvm project
set -e

CLANG_VERSION=4.0
CLANG_FORMAT_VERSION=6.0

echo -------------- Install Clang Tools ---------------



apt-get -q update && apt-get -q -y install \
wget

# make sure we can install up-to-date libClang packages
#wget -O - http://llvm.org/apt/llvm-snapshot.gpg.key|apt-key add -&&\
#    echo "deb http://apt.llvm.org/stretch/ llvm-toolchain-stretch-$CLANG_VERSION main" >> /etc/apt/sources.list &&\
#    echo "deb-src http://apt.llvm.org/stretch/ llvm-toolchain-stretch-$CLANG_VERSION main" >> /etc/apt/sources.list

echo "deb http://ftp.uni-stuttgart.de/debian/ stretch-backports main" >> /etc/apt/sources.list
echo "deb-src http://ftp.uni-stuttgart.de/debian/ stretch-backports main" >> /etc/apt/sources.list

 
apt-get -q update && apt-get -q -y install \
clang-$CLANG_VERSION \
clang-$CLANG_VERSION-doc \
libclang-common-$CLANG_VERSION-dev \
libclang-$CLANG_VERSION-dev \
libclang1-$CLANG_VERSION \
libclang1-$CLANG_VERSION-dbg \
libllvm$CLANG_VERSION \
libllvm$CLANG_VERSION-dbg \
lldb-$CLANG_VERSION \
llvm-$CLANG_VERSION \
llvm-$CLANG_VERSION-dev \
llvm-$CLANG_VERSION-doc \
llvm-$CLANG_VERSION-examples \
llvm-$CLANG_VERSION-runtime \
clang-format-$CLANG_VERSION \
python-clang-$CLANG_VERSION \
libfuzzer-$CLANG_VERSION-dev \
clang-tidy-$CLANG_VERSION \
clang-format-$CLANG_FORMAT_VERSION