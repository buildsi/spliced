# Copyright 2013-2021 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from .base import Prediction
from spliced.logger import logger
import spliced.utils as utils
from .base import match_by_prefix

import os


class AbiLaboratoryPrediction(Prediction):
    def predict(self, splice):
        """
        Run the ABI laboratory to add to the predictions
        """
        self.container = os.environ.get("SPLICED_ABILAB_CONTAINER")
        if not self.container or not os.path.exists(self.container):
            logger.exit("SPLICED_ABILAB_CONTAINER not defined or does not exist.")

        if splice.different_libs:
            return self.splice_different_libs(splice)
        return self.splice_equivalent_libs(splice)

    def splice_different_libs(self, splice):
        """
        In the case of splicing "the same lib" into itself (a different version)
        we can do matching based on names.
        """
        raise NotImplementedError

    def run_abi_laboratory(self, name, original_lib, replace_lib):
        """
        Run abi-dumper + abi-compliance-checker with original and comparison library
        """
        command = "singularity run %s %s %s %s" % (
            self.container,
            original_lib,
            replace_lib,
            name,
        )
        res = utils.run_command(command)
        res["command"] = command

        # The spliced lib and original
        res["spliced_lib"] = replace_lib
        res["original_lib"] = original_lib

        # If there is a libabigail output, print to see
        if res["message"] != "":
            print(res["message"])
        res["prediction"] = res["return_code"] == 0
        return res

    def splice_equivalent_libs(self, splice):
        """
        In the case of splicing "the same lib" into itself (a different version)
        we can do matching based on names. We can use abicomat with binaries, and
        abidiff for just between the libs.
        """
        basename = "%s-%s-%s" % (splice.package, splice.splice, splice - replace)

        # For each original (we assume working) binary, find its deps from elfcall,
        # and then match to the equivalent lib (via basename) for the splice
        original_deps = self.create_elfcall_deps_lookup(splice, splice.original)
        spliced_deps = self.create_elfcall_deps_lookup(splice, splice.spliced)

        # Create a set of predictions for each spliced binary / lib combination
        predictions = []

        # Keep track of diffs we have done!
        diffs = set()
        count = 0
        for binary, meta in original_deps.items():
            # Match the binary to the spliced one
            if binary not in spliced_deps:
                continue

            spliced_meta = spliced_deps[binary]

            # We must find a matching lib for each based on prefix
            matches = match_by_prefix(meta["deps"], spliced_meta["deps"])

            # If we don't have matches, nothing to look at
            if not matches:
                continue

            # Also cache the lib (original or after splice) if we don't have it yet
            for match in matches:

                # Run abidiff if we haven't for this pair yet
                key = (match["original"], match["spliced"])
                if key not in diffs:
                    name = "%s-%s" % (basename, count)
                    res = self.run_abi_laboratory(
                        match["original"], match["spliced"], name
                    )
                    res["splice_type"] = "same_lib"
                    predictions.append(res)
                    diffs.add(key)
                    count += 1

        if predictions:
            splice.predictions["abi-laboratory"] = predictions
            print(splice.predictions)
