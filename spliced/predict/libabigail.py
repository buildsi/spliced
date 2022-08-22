# Copyright 2013-2021 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os

import spliced.utils as utils
from spliced.logger import logger

from .base import Prediction, match_by_prefix, timed_run


def add_to_path(path):
    path = "%s:%s" % (path, os.environ["PATH"])
    os.putenv("PATH", path)
    os.environ["PATH"] = path


class LibabigailPrediction(Prediction):

    abicompat = None
    abidiff = None

    def find_tooling(self):
        """
        Find abicompat and abidiff and add to class
        """
        for tool in ["abicompat", "abidiff"]:
            self.find_tool(tool)

    def find_tool(self, name):
        """
        Find a specific named tool (abidiff or abicompat)
        """
        tool = utils.which(name)
        if not tool:
            logger.warning(f"{name} not found on path, will look for spack instead.")

            # Try getting from spack
            try:
                utils.add_spack_to_path()
                import spack.store

                installed_specs = spack.store.db.query("libabigail")
                if not installed_specs:
                    import spack.spec

                    abi = spack.spec.Spec("libabigail")
                    abi.concretize()
                    abi.package.do_install(force=True)
                else:
                    abi = installed_specs[0]

                add_to_path(os.path.join(abi.prefix, "bin"))
                tool = utils.which(name)

            except:
                logger.error(
                    f"You must either have {name} (libabigail) on the path, or spack."
                )
                return

        if not tool:
            logger.error(
                f"You must either have {name} (libabigail) on the path, or spack."
            )
            return

        # This is the executable path
        setattr(self, name, tool)

    def predict(self, splice, predict_type=None):
        """
        Run libabigail to add to the predictions
        """
        # Both should be found regardless of prediction type
        if not self.abicompat or not self.abidiff:
            self.find_tooling()

        if not predict_type:
            return self.full_prediction(splice)
        if predict_type == "diff":
            return self.diff_prediction(splice)
        logger.warning(f"{predict_type} is not a known prediction type.")

    def full_prediction(self, splice):
        """
        A full prediction is run with spliced splice, includes libs and binaries.
        """
        # If no splice libs OR no tools, cut out early
        if (
            not splice.original
            or not splice.spliced
            or (not self.abicompat and not self.abidiff)
        ):
            return

        if splice.different_libs:
            return self.splice_different_libs(splice)
        return self.splice_equivalent_libs(splice)

    def diff_prediction(self, splice):
        """
        Only do pairwise diffs between libs
        """
        if not splice.original or not splice.spliced or not self.abidiff:
            return

        # For each original (we assume working) binary, find its deps from elfcall,
        # and then match to the equivalent lib (via basename) for the splice
        original_deps = self.create_elfcall_deps_lookup(splice, splice.original)
        spliced_deps = self.create_elfcall_deps_lookup(splice, splice.spliced)

        # Create a set of predictions for each spliced binary / lib combination
        predictions = []

        for libA, metaA in original_deps.items():
            for libB, metaB in spliced_deps.items():
                libA_fullpath = metaA["lib"]
                libB_fullpath = metaB["lib"]

                res = self.run_abidiff(libA_fullpath, libB_fullpath)
                res["splice_type"] = "different_lib"
                predictions.append(res)

        if predictions:
            splice.predictions["libabigail"] = predictions
            print(splice.predictions)

    def splice_different_libs(self, splice):
        """
        In the case of splicing "the same lib" into itself (a different version)
        we can do matching based on names.
        """
        raise NotImplementedError

    def run_abidiff(self, original_lib, replace_lib):
        """
        Run abi diff with an original and comparison library
        """
        debug1 = os.environ.get("LIBABIGAIL_DEBUGINFO_DIR1", "")
        if debug1:
          debug1 = f"--debug-info-dir1 {debug1}"
        
        debug2 = os.environ.get("LIBABIGAIL_DEBUGINFO_DIR2", "")
        if debug2:
          debug2 = f"--debug-info-dir2 {debug2}"

        command = "%s %s %s %s %s" % (self.abidiff, debug1, debug2, original_lib, replace_lib)
        res = timed_run(command)
        res["command"] = command

        # The spliced lib and original
        res["spliced_lib"] = replace_lib
        res["original_lib"] = original_lib

        # If there is a libabigail output, print to see
        if res["message"] != "":
            print(res["message"])
        res["prediction"] = res["message"] == "" and res["return_code"] == 0
        return res

    def run_abicompat(self, binary, original, lib):
        """
        Run abicompat against two libraries
        """
        # Run abicompat to make a prediction
        command = "%s %s %s %s" % (self.abicompat, binary, original, lib)
        res = timed_run(command)
        res["command"] = command
        res["binary"] = binary

        # The spliced lib and original
        res["original_lib"] = lib
        res["spliced_lib"] = original

        # If there is a libabigail output, print to see
        if res["message"] != "":
            print(res["message"])
        res["prediction"] = res["message"] == "" and res["return_code"] == 0
        return res

    def splice_equivalent_libs(self, splice):
        """
        In the case of splicing "the same lib" into itself (a different version)
        we can do matching based on names. We can use abicomat with binaries, and
        abidiff for just between the libs.
        """
        # For each original (we assume working) binary, find its deps from elfcall,
        # and then match to the equivalent lib (via basename) for the splice
        original_deps = self.create_elfcall_deps_lookup(splice, splice.original)
        spliced_deps = self.create_elfcall_deps_lookup(splice, splice.spliced)

        # Create a set of predictions for each spliced binary / lib combination
        predictions = []

        # Keep track of abidiffs we've done
        abidiffs = set()
        for binary, meta in original_deps.items():

            # Match the binary to the spliced one
            if binary not in spliced_deps:
                logger.warning(
                    f"{binary} is missing from splice! This should not happen!"
                )
                continue

            spliced_meta = spliced_deps[binary]
            binary_fullpath = meta["lib"]

            # We must find a matching lib for each based on prefix
            matches = match_by_prefix(meta["deps"], spliced_meta["deps"])

            # Also cache the lib (original or after splice) if we don't have it yet
            for match in matches:

                # Run abicompat with the binary
                result = self.run_abicompat(
                    binary_fullpath, match["original"], match["spliced"]
                )
                result["splice_type"] = "same_lib"
                predictions.append(result)

                # Run abidiff if we haven't for this pair yet
                key = (match["original"], match["spliced"])
                if key not in abidiffs:
                    res = self.run_abidiff(match["original"], match["spliced"])
                    res["splice_type"] = "same_lib"
                    predictions.append(res)
                    abidiffs.add(key)

        if predictions:
            splice.predictions["libabigail"] = predictions
            print(splice.predictions)
