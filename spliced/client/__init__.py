#!/usr/bin/env python

# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import spliced
from spliced.logger import setup_logger
import argparse
import sys
import os


def get_parser():
    parser = argparse.ArgumentParser(
        description="Spliced",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Global Variables
    parser.add_argument(
        "--debug",
        dest="debug",
        help="use verbose logging to debug.",
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--quiet",
        dest="quiet",
        help="suppress additional output.",
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--version",
        dest="version",
        help="show software version.",
        default=False,
        action="store_true",
    )

    description = "actions for spliced"
    subparsers = parser.add_subparsers(
        help="spliced actions",
        title="actions",
        description=description,
        dest="command",
    )

    # print version and exit
    subparsers.add_parser("version", description="show software version")

    splice = subparsers.add_parser(
        "splice",
        description="generate predictions for a splice.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # For a splice, we provie a config OR the command line args as is
    splice.add_argument(
        "-c",
        "--config",
        dest="config_yaml",
        help="read config values from yaml (overrides command line variables)",
    )

    splice.add_argument(
        "-p",
        "--package",
        dest="package",
        help="package to splice into (overridden by package in config yaml)",
    )

    splice.add_argument(
        "--splice",
        dest="splice",
        help="splice OUT this package or library (overridden by splice in config yaml)",
    )

    splice.add_argument(
        "--replace",
        dest="replace",
        help="splice IN this package or library (overridden by replace in config yaml)",
    )

    splice.add_argument(
        "--predictor",
        dest="predictor",
        help="A named predictor to use (if not defined, defaults to all)",
        action="append",
    )

    splice.add_argument(
        "-r",
        "--runner",
        dest="runner",
        help="experiment runner to use (defaults to spack)",
        choices=["spack"],
        default="spack",
    )
    splice.add_argument(
        "-e",
        "--experiment",
        dest="experiment",
        help="experiment name or identifier",
    )

    # Just generate a list of commands (no matrix!)
    matrix = subparsers.add_parser(
        "command",
        description="generate a list of commands to run splices (instead of a matrix",
    )

    # Validate a spliced result
    validate = subparsers.add_parser(
        "validate",
        description="Validate a spliced result file",
    )
    validate.add_argument("json_file", help="json file to validate")

    # Generate matrix of splice commands and outputs, etc.
    command = subparsers.add_parser(
        "matrix",
        description="generate matrix of splices (intended for GitHub actions or similar)",
    )
    for cmd in [matrix, command]:
        cmd.add_argument(
            "-g",
            "--generator",
            dest="generator",
            help="generator to use (defaults to spack)",
            choices=["spack"],
            default="spack",
        )

        cmd.add_argument(
            "-l",
            "--limit",
            help="Set a limit for job entries to generate (defaults to 0, no limit)",
            type=int,
            default=0,
        )

        # recommended: ghcr.io/buildsi/spack-ubuntu-20.04
        cmd.add_argument(
            "-c",
            "--container",
            help="container base to use.",
        )

        # Generate the matrix from a config
        cmd.add_argument(
            "config_yaml",
            help="A configuration file to run a splice prediction.",
        )

    for subparser in [command, matrix, splice]:
        subparser.add_argument(
            "-o",
            "--outfile",
            help="write json output to this file",
        )
    return parser


def run_spliced():
    """run_spliced to perform a splice!"""

    parser = get_parser()

    def help(return_code=0):
        version = spliced.__version__

        print("\nSpliced Client v%s" % version)
        parser.print_help()
        sys.exit(return_code)

    # If the user didn't provide any arguments, show the full help
    if len(sys.argv) == 1:
        help()

    # If an error occurs while parsing the arguments, the interpreter will exit with value 2
    args, extra = parser.parse_known_args()

    if args.debug is True:
        os.environ["MESSAGELEVEL"] = "DEBUG"

    # Show the version and exit
    if args.command == "version" or args.version:
        print(spliced.__version__)
        sys.exit(0)

    setup_logger(
        quiet=args.quiet,
        debug=args.debug,
    )

    # retrieve subparser (with help) from parser
    helper = None
    subparsers_actions = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    for subparsers_action in subparsers_actions:
        for choice, subparser in subparsers_action.choices.items():
            if choice == args.command:
                helper = subparser
                break

    # Does the user want a shell?
    if args.command == "splice":
        from .splice import main
    if args.command == "matrix":
        from .command import matrix as main
    if args.command == "command":
        from .command import command as main
    if args.command == "validate":
        from .validate import main

    # Pass on to the correct parser
    return_code = 0
    try:
        main(args=args, parser=parser, extra=extra, subparser=helper)
        sys.exit(return_code)
    except UnboundLocalError:
        return_code = 1

    help(return_code)


if __name__ == "__main__":
    run_spliced()
