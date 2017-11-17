#!/bin/sh


# This script uses apt-get to install libraries and tools related to the llvm project
set -e

echo -------------- Install Clang Tools ---------------

apt-get -q update && apt-get -q -y install \
wget

# make sure we can install up-to-date libClang packages
wget -O - http://llvm.org/apt/llvm-snapshot.gpg.key|apt-key add -&&\
    echo "deb http://apt.llvm.org/jessie/ llvm-toolchain-jessie-3.9 main" >> /etc/apt/sources.list &&\
    echo "deb-src http://apt.llvm.org/jessie/ llvm-toolchain-jessie-3.9 main" >> /etc/apt/sources.list

 
apt-get -q update && apt-get -q -y install \
clang-3.9 \
clang-3.9-doc \
libclang-common-3.9-dev \
libclang-3.9-dev \
libclang1-3.9 \
libclang1-3.9-dbg \
libllvm-3.9-ocaml-dev \
libllvm3.9 \
libllvm3.9-dbg \
lldb-3.9 \
llvm-3.9 \
llvm-3.9-dev \
llvm-3.9-doc \
llvm-3.9-examples \
llvm-3.9-runtime \
clang-format-3.9 \
python-clang-3.9 \
libfuzzer-3.9-dev \
clang-tidy-3.9