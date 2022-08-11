# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import json
import os
import sys

import spliced.utils as utils
from spliced.logger import logger


def main(args, parser, extra, subparser):

    if args.outfile:
        logger.info(f"Results will be written to {args.outfile}")

    if args.runner == "spack":
        run_spack_experiment(args, command=" ".join(extra))
    elif args.runner == "manual":
        run_manual_experiment(args, command=" ".join(extra))
    elif not args.runner:
        sys.exit("You must provide an experiment runner.")
    else:
        sys.exit("Runner %s is not recognized" % args.runner)


def run_manual_experiment(args, command):
    """
    Run a manual experiment
    """
    import spliced.experiment.manual

    # A general SpackExperiment does a replacement
    experiment = spliced.experiment.manual.ManualExperiment()

    # We either load a config, or the arguments provided
    if args.config_yaml:
        experiment.load(args.config_yaml)
    else:
        experiment.init(
            package=args.package, splice=args.splice, experiment=args.experiment
        )

    # Perform the experiment
    experiment.run()
    experiment.predict(args.predictor, skip=args.skip, predict_type="diff")
    results = experiment.to_dict()

    if args.outfile:
        utils.mkdir_p(os.path.dirname(os.path.abspath(args.outfile)))
        utils.write_json(results, args.outfile)
    else:
        print(json.dumps(results, indent=4))


def run_spack_experiment(args, command):
    """
    Run a spack experiment, meaning we need to ensure spack is importable
    """
    utils.add_spack_to_path()

    import spliced.experiment.spack

    # A general SpackExperiment does a replacement
    experiment = spliced.experiment.spack.SpackDiffExperiment()

    # We either load a config, or the arguments provided
    if args.config_yaml:
        experiment.load(args.config_yaml)
    else:
        experiment.init(
            package=args.package, splice=args.splice, experiment=args.experiment
        )

    # Perform the experiment
    experiment.run()
    experiment.predict(args.predictor, skip=args.skip, predict_type="diff")
    results = experiment.to_dict()

    if args.outfile:
        utils.mkdir_p(os.path.dirname(os.path.abspath(args.outfile)))
        utils.write_json(results, args.outfile)
    else:
        print(json.dumps(results, indent=4))
