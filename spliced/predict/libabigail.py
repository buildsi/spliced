# Copyright 2013-2021 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from .base import Prediction
from spliced.logger import logger
import spliced.utils as utils
import itertools

import os


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

    def predict(self, splice):
        """
        Run libabigail to add to the predictions
        """
        if not self.abicompat or not self.abidiff:
            self.find_tooling()

        # If no splice libs OR no tools, cut out early
        if not splice.libs or (not self.abicompat and not self.abidiff):
            return

        # We have TWO cases here:
        # Case 1: We ONLY have a list of libs that were spliced.
        if (
            "spliced" in splice.libs
            and "original" in splice.libs
            and splice.libs["spliced"]
        ):
            self.splice_equivalent_libs(splice, splice.libs["spliced"])

        # Case 2: We are mocking a splice, and we have TWO sets of libs: some original, and some to replace with
        elif "dep" in splice.libs and "replace" in splice.libs:
            self.splice_different_libs(
                splice, splice.libs["dep"], splice.libs["replace"]
            )

    def splice_different_libs(self, splice, original_libs, replace_libs):
        """
        In the case of splicing "the same lib" into itself (a different version)
        we can do matching based on names.
        """
        # If we have spliced binaries, this means the spack splice was successful.
        # Otherwise, we do not, but we have the original deps to test
        binaries = splice.get_binaries()

        # Flatten original and replacement libs
        original_libs = list(itertools.chain(*[x["paths"] for x in original_libs]))
        replace_libs = list(itertools.chain(*[x["paths"] for x in replace_libs]))

        # Assemble a set of predictions using abicompat
        predictions = []
        for binary in binaries:
            for original_lib in original_libs:
                for replace_lib in replace_libs:

                    # Run abicompat to make a prediction
                    res = self.run_abicompat(binary, original_lib, replace_lib)
                    res["splice_type"] = "different_lib"
                    predictions.append(res)

        # Assemble a set of predictions using abidiff
        for original_lib in original_libs:
            for replace_lib in replace_libs:

                res = self.run_abidiff(original_lib, replace_lib)
                res["splice_type"] = "different_lib"
                predictions.append(res)

        if predictions:
            splice.predictions["libabigail"] = predictions

    def run_abidiff(self, original_lib, replace_lib):
        """
        Run abi diff with an original and comparison library
        """
        command = "%s %s %s" % (self.abidiff, original_lib, replace_lib)
        res = utils.run_command(command)
        res["command"] = command

        # The spliced lib and original
        res["replace"] = replace_lib
        res["lib"] = original_lib

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
        res = utils.run_command(command)
        res["command"] = command
        res["binary"] = binary

        # The spliced lib and original
        res["lib"] = lib
        res["original_lib"] = original

        # If there is a libabigail output, print to see
        if res["message"] != "":
            print(res["message"])
        res["prediction"] = res["message"] == "" and res["return_code"] == 0
        return res

    def splice_equivalent_libs(self, splice, libs):
        """
        In the case of splicing "the same lib" into itself (a different version)
        we can do matching based on names. We can use abicomat with binaries, and
        abidiff for just between the libs.
        """
        # Flatten original libs into flat list
        original_libs = list(
            itertools.chain(*[x["paths"] for x in splice.libs.get("original", [])])
        )

        # If we have spliced binaries, this means the spack splice was successful.
        # Otherwise, we do not, but we have the original deps to test
        binaries = splice.get_binaries()

        # Assemble a set of predictions
        predictions = []
        for binary in binaries:
            for libset in libs:
                for lib in libset["paths"]:

                    # Try to match libraries based on prefix (versioning is likely to change)
                    libprefix = os.path.basename(lib).split(".")[0]

                    # Find an original library path with the same prefix
                    originals = [
                        x
                        for x in original_libs
                        if os.path.basename(x).startswith(libprefix)
                    ]
                    if not originals:
                        logger.warning(
                            "Warning, original comparison library not found for %s, required for abicompat."
                            % lib
                        )
                        continue

                    # The best we can do is compare all contender matches
                    for original in originals:

                        # Run abicompat to make a prediction
                        res = self.run_abicompat(binary, original, lib)
                        res["splice_type"] = "same_lib"
                        predictions.append(res)

        # Next predictions using abidiff
        for libset in libs:
            for lib in libset["paths"]:

                # Try to match libraries based on prefix (versioning is likely to change)
                libprefix = os.path.basename(lib).split(".")[0]

                # Find an original library path with the same prefix
                originals = [
                    x
                    for x in original_libs
                    if os.path.basename(x).startswith(libprefix)
                ]
                if not originals:
                    logger.warning(
                        "Warning, original comparison library not found for %s, required for abidiff."
                        % lib
                    )
                    continue

                # The best we can do is compare all contender matches
                for original in originals:
                    res = self.run_abidiff(original, lib)
                    res["splice_type"] = "same_lib"
                    predictions.append(res)

        if predictions:
            splice.predictions["libabigail"] = predictions
            print(splice.predictions)
