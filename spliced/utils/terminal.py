# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from spliced.logger import logger
from subprocess import Popen, PIPE, STDOUT
import os
import sys
import shlex
import shutil


def which(software, strip_newline=True):
    """get_install will return the path to where Singularity (or another
    executable) is installed.
    """
    return shutil.which(software)


def check_install(software, quiet=True, command="--version"):
    """check_install will attempt to run the singularity command, and
    return True if installed. The command line utils will not run
    without this check.

    Parameters
    ==========
    software: the software to check if installed
    quiet: should we be quiet? (default True)
    command: the command to use to check (defaults to --version)
    """
    cmd = [software, command]
    try:
        version = run_command(cmd, software)
    except:  # FileNotFoundError
        return False
    if version:
        if not quiet and version["return_code"] == 0:
            version = version["message"]
            logger.info("Found %s version %s" % (software.upper(), version))
        return True
    return False


def get_installdir():
    """get_installdir returns the installation directory of the application"""
    return os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


def run_command(cmd, stream=False):
    """run_command uses subprocess to send a command to the terminal.

    Parameters
    ==========
    cmd: the command to send, should be a list for subprocess
    error_message: the error message to give to user if fails,
    if none specified, will alert that command failed.

    """
    if not isinstance(cmd, list):
        cmd = shlex.split(cmd)
    stdout = PIPE if not stream else None

    output = Popen(cmd, stderr=STDOUT, stdout=stdout)
    t = output.communicate()[0], output.returncode
    output = {"message": t[0], "return_code": t[1]}

    if isinstance(output["message"], bytes):
        output["message"] = output["message"].decode("utf-8")
    return output


def confirm_action(question, force=False):
    """confirm if the user wants to perform a certain action

    Parameters
    ==========
    question: the question that will be asked
    force: if the user wants to skip the prompt
    """
    if force is True:
        return True

    response = input(question)
    while len(response) < 1 or response[0].lower().strip() not in "ynyesno":
        response = input("Please answer yes or no: ")

    if response[0].lower().strip() in "no":
        return False

    return True


def add_spack_to_path():
    """
    Find spack and add to path, allowing for import of spack modules
    """
    # Find path to spack install
    spack_python = which("spack-python")
    if not spack_python:
        sys.exit("Make sure spack and spack-python are on your path for this runner.")

    # Find spack's location and its prefix, add libs and external libs
    spack_prefix = os.path.dirname(os.path.dirname(spack_python))
    spack_lib_path = os.path.join(spack_prefix, "lib", "spack")
    spack_external_libs = os.path.join(spack_lib_path, "external")
    for path in [spack_lib_path, spack_external_libs]:
        sys.path.insert(0, path)


def confirm_uninstall(filename, force=False):
    """confirm if the user wants to uninstall a module

    Parameters
    ==========
    filename: the file that will be removed
    force: if the user wants to skip the prompt
    """
    return confirm_action(
        "Are you sure you want to uninstall {}".format(filename), force
    )
