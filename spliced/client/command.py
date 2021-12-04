# Copyright 2013-2021 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)


import spliced.experiment
import spliced.utils as utils
import random
import requests
import os
import sys
import json


def matrix(args, parser, extra, subparser):
    """
    Upper level function for generating an experiment matrix
    """
    # Generate a base experiment
    experiment = spliced.experiment.Experiment()
    experiment.load(args.config_yaml)

    if args.generator == "spack":
        generate_spack_matrix(args, experiment, " ".join(extra))


def command(args, parser, extra, subparser):
    """
    Generate command list
    """
    # Generate a base experiment
    experiment = spliced.experiment.Experiment()
    experiment.load(args.config_yaml)

    if args.generator == "spack":
        generate_spack_commands(args, experiment, " ".join(extra))


def get_package_versions(package):
    """
    Given a spack package, get a list of all versions
    """
    versions = requests.get(
        "https://raw.githubusercontent.com/spack/packages/main/data/packages/%s.json"
        % package
    )
    if versions.status_code != 200:
        sys.exit("Failed to get package versions")
    versions = versions.json()
    return list(set([x["name"] for x in versions["versions"]]))


def get_compiler_labels(container):
    """
    Given a container URI, get all associated compiler labels (if they exist)
    """
    # If we have a container, get compilers. Otherwise default to "all"
    labels = ["all"]

    if container:
        response = requests.get("https://crane.ggcr.dev/config/%s" % container)
        if response.status_code != 200:
            sys.exit(
                "Issue retrieving image config for % container: %s"
                % (container, response.reason)
            )

        config = response.json()
        labels = config["config"].get("Labels", {}).get("org.spack.compilers")
        labels = [x for x in labels.strip("|").split("|") if x]
    return labels


def generate_spack_commands(args, experiment, command=None):
    """
    Generate a list of spliced commands
    """
    versions = get_package_versions(experiment.package)
    labels = get_compiler_labels(args.container)
    commands = []

    # Command can come from command line or config file
    command = command or experiment.command

    # Generate list of commands
    for version in versions:

        # versioned package
        package = "%s@%s" % (experiment.package, version)
        cmd = "spliced splice --package %s --splice %s --runner spack --replace %s --experiment %s" % (
            package,
            experiment.splice,
            experiment.replace,
            experiment.name,
        )
        if args.container:
            cmd = "%s --containers %s" % (cmd, args.container)
        if command:
            cmd = "%s %s" % (cmd, command)
        commands.append(cmd)

    # flatten to be printable
    commands = "\n".join(commands)

    if args.outfile:
        utils.write_file(commands, args.outfile)
    else:
        print(commands)


def generate_spack_matrix(args, experiment, command=None):
    """A spack matrix derives versions from spack, and prepares
    to generate commands (and metadata) to support a spack splice
    experiment
    """
    versions = get_package_versions(experiment.package)
    labels = get_compiler_labels(args.container)

    # We will build up a matrix of container and associated compilers
    matrix = []

    # Command can come from command line or config file
    command = command or experiment.command

    # Generate list of commands
    for version in versions:

        # versioned package
        package = "%s@%s" % (experiment.package, version)
        cmd = "spliced splice --package %s --splice %s --runner spack --replace %s --experiment %s" % (
            package,
            experiment.splice,
            experiment.replace,
            experiment.name,
        )
        if args.container:
            cmd = "%s --containers %s" % (cmd, args.container)
        if command:
            cmd = "%s %s" % (cmd, command)
        matrix.append(
            {
                "command": cmd,
                "package": package,
                "runner": "spack",
                "splice": experiment.splice,
                "replace": experiment.replace,
                "experiment": experiment.name,
                "container": args.container,
            }
        )

    # We can only get up to 256 max - select randomly
    if args.limit != 0 and len(matrix) >= args.limit:
        print(
            "Warning: original output is length %s and limit is set to %s jobs!"
            % (len(matrix), args.limit)
        )
        matrix = random.sample(matrix, args.limit)

    if args.outfile:
        utils.write_json(matrix, args.outfile)
    print("::set-output name=matrix::%s\n" % json.dumps(matrix))
