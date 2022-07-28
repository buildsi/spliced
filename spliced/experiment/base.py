# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

# An experiment loads in a splice setup, and runs a splice session.


from spliced.logger import logger
import spliced.predict
import spliced.schemas
import spliced.utils as utils
import jsonschema
import json
import os
import re


class Splice:
    """
    A Splice holds the metadata for a splice, and if successful (or possible)
    will hold a result. A default splice result is not successful
    """

    def __init__(
        self,
        package=None,
        splice=None,
        experiment=None,
        replace=None,
        result=None,
        success=False,
        different_libs=False,
    ):

        # Keep track of original and spliced paths
        self.original = set()
        self.spliced = set()
        self.paths = {}

        # This lookup has metadata for each (e.g., elfcall)
        self.metadata = {}

        # Extra stats for the predictor to record
        self.stats = {"sizes_bytes": {}}

        self.predictions = {}
        self.package = package
        self.specs = {}
        self.ids = {}
        self.experiment = experiment
        self.success = success
        self.result = result
        self.splice = splice

        # Are we splicing different libs?
        self.different_libs = different_libs

    def add_spec(self, key, spec):
        """
        Add a spec (with a key) to metadata
        """
        self.add_identifier(key, "/" + spec.dag_hash()[0:6])
        self.specs[key] = spec

    def add_identifier(self, key, identifier):
        """
        Add some experiment specific identifier (e.g., dag hash for spack)
        """
        self.ids[key] = identifier

    def match_libs(self):
        """
        Try to match dependencies between spliced/original library for comparison
        """
        pass

    def to_dict(self):
        """
        Return the result as a dictionary
        """
        return {
            "specs": {k: str(v) for k, v in self.specs.items()},
            "ids": self.ids,
            "original": list(self.original),
            "spliced": list(self.spliced),
            "paths": self.paths,
            "predictions": self.predictions,
            "stats": self.stats,
            "experiment": self.experiment,
            "result": self.result,
            "success": self.success,
            "splice": self.splice,
            "package": self.package,
            "different_libs": self.different_libs,
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
        replace=None,
        validate=True,
        splice_versions=None,
    ):
        """
        Init config variables directly
        """
        self.config = {
            "splice": splice,
            "package": {"name": package},
            "replace": replace,
        }
        if experiment:
            self._experiment = experiment
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

    def add_splice(
        self, result, success=False, splice=None, command=None, different_libs=False
    ):
        """
        Add a splice to the experiment

        A splice can either be successful (so it will have libs, binaries, etc)
        or it can represent a failed state (for any number of reasons)

        TODO refactor so we do one splice at a time
        TODO can we cache the splice setup?
        # ALSO add cache variable to save cache for smeagle (add to spack experiment)
        """
        print(f"*** ADDING SPLICE RESULT {result} ***")
        new_splice = Splice(
            package=self.package,
            splice=splice or self.splice,
            result=result,
            success=success,
            experiment=self.name,
            replace=self.replace,
            different_libs=different_libs,
        )
        self.splices.append(new_splice)

        # We can return the new splice here to do additional work, etc.
        return new_splice

    @property
    def package(self):
        return self.config.get("package", {}).get("name")

    @property
    def splice(self):
        return self.config.get("splice")

    @property
    def splice_versions(self):
        return self.config.get("splice_versions") or self._splice_versions

    @property
    def name(self):
        if self.config_file is not None:
            return os.path.basename(self.config_file).split(".")[0]
        return self._experiment

    @property
    def replace(self):
        return self.config.get("replace") or self.splice
