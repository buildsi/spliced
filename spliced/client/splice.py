# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import sys
import json
import spliced.utils as utils


def main(args, parser, extra, subparser):

    if args.runner == "spack":
        run_spack_experiment(args, command=" ".join(extra))
    elif not args.runner:
        sys.exit("You must provide an experiment runner.")
    else:
        sys.exit("Runner %s is not recognized" % args.runner)


def run_spack_experiment(args, command):
    """
    Run a spack experiment, meaning we need to ensure spack is importable
    """
    utils.add_spack_to_path()

    import spliced.experiment.spack

    experiment = spliced.experiment.spack.SpackExperiment()

    # We either load a config, or the arguments provided
    if args.config_yaml:
        experiment.load(args.config_yaml)
    else:
        experiment.init(
            args.package, args.splice, args.experiment, command, args.replace
        )

    # Perform the splice!
    experiment.run()

    # TODO can we run_parallel here as an option? And do splice -> predict as such
    # And make predictions
    experiment.predict(args.predictor)
    results = experiment.to_dict()

    if args.outfile:
        utils.write_json(results, args.outfile)
    else:
        print(json.dumps(results, indent=4))
