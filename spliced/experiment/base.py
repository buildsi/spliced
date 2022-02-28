# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

# An experiment loads in a splice setup, and runs a splice session.

# TODO can we run in parallel?

from spliced.logger import logger
import spliced.predict
import spliced.schemas
import spliced.utils as utils
import jsonschema
import json
import os
import re


class Splice:
    """A Splice holds the metadata for a splice, and if successful (or possible)
    will hold a result. A default splice result is not successful
    """

    def __init__(
        self,
        package=None,
        splice=None,
        command=None,
        experiment=None,
        replace=None,
        result=None,
        success=False,
    ):

        # Typically has "original" and "spliced"
        self.binaries = {}
        self.libs = {}

        self.predictions = {}
        self.package = package
        self.experiment = experiment
        self.success = success
        self.result = result
        self.splice = splice
        self.command = command
        self.id = None

    def add_identifier(self, identifier):
        """
        Add some experiment specific identifier (e.g., dag hash for spack)
        """
        self.id = identifier

    def match_libs(self):
        """
        Try to match dependencies between spliced/original library for comparison
        """
        pass

    def get_binaries(self):
        """return if the splice was successful and the binaries for it"""
        binaries = self.binaries.get("spliced", [])
        if not binaries:
            print(
                "Warning - this splice was not successful or not possible, predictions will use original binaries installed of spliced."
            )
            binaries = self.binaries.get("original", [])
        return binaries

    def get_libs(self):
        """return if the splice was successful and the libs for it"""
        # Same is case for libset - use what we have
        libs = self.libs.get("spliced", [])
        if not libs:
            print(
                "Warning - this splice was not successful or not possible, predictions will use dependency libs (not spliced) instead."
            )
            libs = self.libs.get("libs", [])
        return libs

    def to_dict(self):
        """
        Return the result as a dictionary
        """
        return {
            "binaries": self.binaries,
            "predictions": self.predictions,
            "libs": self.libs,
            "experiment": self.experiment,
            "result": self.result,
            "success": self.success,
            "splice": self.splice,
            "package": self.package,
        }

    def to_json(self):
        """
        Return the result as json
        """
        return json.dumps(self.to_dict())


class Experiment:
    """
    A base Experiment holds information for a splice experiment!
    """

    def __init__(self):
        self.splices = []
        self.config_file = None
        self._splice_versions = None

    def load(self, config_file, validate=True):
        """
        Load a config from a yaml file
        """
        self.config = utils.read_yaml(config_file)
        self.config_file = config_file
        self._experiment = re.sub("[.](yml|yaml)", "", os.path.basename(config_file))
        if validate:
            self.validate()

    def init(
        self,
        package,
        splice,
        experiment,
        command=None,
        replace=None,
        validate=True,
        splice_versions=None,
    ):
        """
        Init config variables directly
        """
        self.config = {"splice": splice, "package": package, "replace": replace}
        if experiment:
            self._experiment = experiment
        if command:
            self.config["command"] = command
        if splice_versions:
            self._splice_versions = splice_versions
        if validate:
            self.validate()

    def run(self):
        """
        run the experiment.
        """
        raise NotImplementedError

    def run_parallel(self):
        # TODO- will be nice to possibly speed things up!
        pass

    def predict(self, names=None):
        """
        Given a single named predictor (or a list to skip) make predictions.
        """
        predictors = spliced.predict.get_predictors(names)
        if not predictors:
            logger.warning("No matching predictors were found.")
            return

        for name, predictor in predictors.items():
            logger.info("Making predictions for %s" % name)

            # Result is added to splice
            for splice in self.splices:
                predictor.predict(splice)

    def to_json(self):
        """
        Return a json dump of results
        """
        return json.dumps(self.to_dict())

    def to_dict(self):
        """
        Return a dictionary of results
        """
        results = []
        for result in self.splices:
            results.append(result.to_dict())
        return results

    def validate(self):
        jsonschema.validate(instance=self.config, schema=spliced.schemas.spliced_schema)

    def add_splice(self, result, success=False, splice=None, command=None):
        """Add a splice to the experiment

        A splice can either be successful (so it will have libs, binaries, etc)
        or it can represent a failed state (for any number of reasons)
        """
        new_splice = Splice(
            package=self.package,
            splice=splice or self.splice,
            result=result,
            success=success,
            command=command or self.command,
            experiment=self.name,
            replace=self.replace,
        )
        self.splices.append(new_splice)

        # We can return the new splice here to do additional work, etc.
        return new_splice

    @property
    def package(self):
        return self.config.get("package")

    @property
    def splice(self):
        return self.config.get("splice")

    @property
    def splice_versions(self):
        return self.config.get("splice_versions") or self._splice_versions

    @property
    def command(self):
        return self.config.get("command")

    @property
    def name(self):
        if self.config_file is not None:
            return os.path.basename(self.config_file).split(".")[0]
        return self._experiment

    @property
    def replace(self):
        return self.config.get("replace") or self.splice
