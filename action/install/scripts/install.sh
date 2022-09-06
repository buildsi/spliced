#!/bin/bash

set -e

# Show the user all relevant variables for debugging!
printf "release: ${INPUT_RELEASE}\n"
printf "branch: ${INPUT_BRANCH}\n"

if [[ "${INPUT_DOINSTALL}" == "false" ]]; then
    printf "Skipping install, spliced should be installed by you.\n"
    exit 0;
else
    printf "Moving forward with install ${INPUT_DOINSTALL}\n"
fi

python -m pip install --upgrade pip setuptools wheel

# archinfo, pyvex, pyelftools, then cle
python -m pip install git+https://github.com/vsoch/elfcall@main

# Case 1: no branch or release, install from pip
if [ -z "${INPUT_BRANCH}" ] && [ -z "${INPUT_RELEASE}" ]; then
    printf "Installing latest from pypi\n"
    pip install spliced
elif [ ! -z "${INPUT_BRANCH}" ]; then

    if [ -d "/opt/spliced" ]; then
        rm -rf /opt/spliced
    fi
    printf "Installing from branch ${INPUT_BRANCH}\n"
    git clone -b "${INPUT_BRANCH}" https://github.com/buildsi/spliced /opt/spliced
    cd /opt/spliced
    pip install -e .
else
    printf "Installing from release ${INPUT_RELEASE}\n"
    if [ -d "/opt/spliced" ]; then
        rm -rf /opt/spliced
    fi
    wget https://github.com/buildsi/spliced/releases/download/v${INPUT_RELEASE}/spliced-${INPUT_RELEASE}.tar.gz
    tar -xzvf spliced-${INPUT_RELEASE}.tar.gz
    cd spliced-${INPUT_RELEASE} 
    pip install -e .
fi
