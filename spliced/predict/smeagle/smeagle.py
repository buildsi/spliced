# Copyright 2013-2021 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os
import sys

import spliced.utils as utils
from spliced.logger import logger

from .solver import FactGenerator, StabilitySetSolver, StabilitySolver

here = os.path.abspath(os.path.dirname(__file__))


class SmeagleRunner:
    def __init__(self):
        """
        Load in Smeagle output files, write to database, and run solver.
        """
        self.compatible_lp = os.path.join(here, "lp", "compatible.lp")
        self.stability_lp = os.path.join(here, "lp", "stability.lp")
        self.records = []

    def load_data(self, lib=None, data=None):
        """
        Common function to derive json data and a library.
        Each is optional to be provided, and we are flexible to accept either.
        """
        if not data and not lib:
            sys.exit("You must provide data or a library path.")
        if not data:
            data = self.get_smeagle_data(lib)

        if not lib:
            lib = data.get("library", "unknown")

        # Load data provided by path
        if not isinstance(data, dict) and os.path.exists(data):
            data = utils.read_json(data)

        # Cut out early if we don't have the records
        if not data:
            sys.exit("Cannot find database entry for %s." % lib)
        return data, lib

    def generate_facts(
        self, lib=None, data=None, out=None, lib_basename=False, namespace=None
    ):
        """
        Generate facts for one entry.
        """
        data, _ = self.load_data(lib, data)
        if "data" in data:
            data = data["data"]
        setup = FactGenerator(
            data, out=out, lib_basename=lib_basename, namespace=namespace
        )
        setup.solve()

    def get_smeagle_data(self, lib=None, data=None):
        """
        Get smeagle data
        """
        if not os.path.exists(lib):
            logger.exit("Library %s does not exist!" % lib)

        try:
            import cle
        except ImportError:
            logger.exit("cle is required to run the smeagle predictor.")

        # Get a smeagle corpus (facts.json)
        try:
            ld = cle.Loader(lib, load_debug_info=True, auto_load_libs=False)
            return {"return_code": 0, "data": ld.corpus.to_dict(), "message": "success"}
        except Exception as exc:
            msg = "Cannot load corpus: %s" % exc
            logger.error(msg)
            return {"return_code": -1, "message": msg, "data": {}}

    def compatible_test(self, lib, lib_set, lookup, detail=False, out=None):
        """
        A set test scopes a library A (lib) to be compared against its space of
        dependencies (lib_set). To properly scope the output list of facts,
        we take a lookup that has key (the library facts json to load) and value
        as the set of symbols to include in the model
        """
        if not os.path.exists(self.compatible_lp):
            logger.exit("Logic program %s does not exist!" % self.compatible_lp)

        # This function assumes that the data files exist (provided in lookup)
        # We have to incrementally add the lib as A, and then all data as B,
        # each scoped to the set of symbols we know are used or provided

        setup = StabilitySetSolver(lib, lib_set, lookup, out=out)
        result = setup.solve(logic_programs=self.compatible_lp)

        # Assuming anything missing is failure
        res = {"A": lib, "B": lib_set, "prediction": True}

        # Keep a subset of data (missing stuff) for the result
        missing = {}
        for key in ["not_compatible"]:
            if key in result:
                res["prediction"] = False
                missing[key] = result[key]

        # Add details about missing only if missing!
        if missing:
            res["message"] = missing
        return res

    def stability_test(self, lib1, lib2, data1=None, data2=None, out=None):
        """
        Run the stability test for two entries.
        """
        # We must have the stability program!
        if not os.path.exists(self.stability_lp):
            logger.exit("Logic program %s does not exist!" % self.stability_lp)

        # First get facts from smeagle
        lib1_res, lib1 = self.load_data(lib1, data1)
        lib2_res, lib2 = self.load_data(lib2, data2)

        # The spliced lib and original (assume failure)
        res = {"original_lib": lib1, "lib": lib2, "prediction": False}

        # If either result has nonzero return code, no go
        if not lib1_res or not lib2_res:
            res.update(
                {
                    "return_code": -1,
                    "message": "Smeagle failed to generate facts for both libraries",
                }
            )
            return res

        # Success case gets here
        # Setup and run the stability solver
        # lib1 is original, lib2 is to sub in
        setup = StabilitySolver(lib1_res, lib2_res, out=out)
        result = setup.solve(logic_programs=self.stability_lp)

        # Assuming anything missing is failure
        res["prediction"] = True

        # Keep a subset of data (missing stuff) for the result
        missing = {}
        for key in ["missing_imports", "missing_exports"]:
            if key in result:
                res["prediction"] = False
                missing[key] = result[key]

        # Add details about missing only if missing!
        if missing:
            res["message"] = missing
        return res
