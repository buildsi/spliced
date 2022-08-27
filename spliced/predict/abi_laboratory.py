# Copyright 2013-2021 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os
import shutil
import tempfile

from spliced.logger import logger

from .base import Prediction, match_by_prefix, timed_run


class AbiLaboratoryPrediction(Prediction):
    container = "docker://ghcr.io/buildsi/abi-laboratory-docker"

    def predict(self, splice, predict_type=None):
        """
        Run the ABI laboratory to add to the predictions
        """
        self.set_cache()
        if predict_type == "diff":
            return self.run_diff(splice)

        if splice.different_libs:
            return self.splice_different_libs(splice)
        return self.splice_equivalent_libs(splice)

    def set_cache(self):
        """
        Set the cache directory.
        """
        # If we have defined a cache, use it
        self.cache_dir = os.environ.get(
            "SPLICED_ABILAB_CACHE_DIR",
            os.path.join(tempfile.gettempdir(), "spliced-cache"),
        )
        logger.info("Abi Laboratory cache directory is %s" % self.cache_dir)

    def splice_different_libs(self, splice):
        """
        In the case of splicing "the same lib" into itself (a different version)
        we can do matching based on names.
        """
        raise NotImplementedError

    def run_abi_laboratory(self, original_lib, replace_lib, name):
        """
        Run abi-dumper + abi-compliance-checker with original and comparison library.
        This assumes we are in the container, and falls back to running a container.
        """
        script_path = shutil.which("run_abi_laboratory.sh")
        if script_path:
            return self.run_local_abi_laboratory(original_lib, replace_lib, name)
        return self.run_containerized_abi_laboratory(original_lib, replace_lib, name)

    def run_local_abi_laboratory(self, original_lib, replace_lib, name):
        """
        Run containerized abi laboratory with singularity
        """
        script_path = shutil.which("run_abi_laboratory.sh")
        command = "/bin/bash %s %s %s %s" % (
            script_path,
            original_lib,
            replace_lib,
            name,
        )
        return self._run_abi_laboratory(command, original_lib, replace_lib, name)

    def run_containerized_abi_laboratory(self, original_lib, replace_lib, name):
        """
        Run containerized abi laboratory with singularity
        """
        command = "singularity run %s %s %s %s" % (
            self.container,
            original_lib,
            replace_lib,
            name,
        )
        return self._run_abi_laboratory(command, original_lib, replace_lib, name)

    def _run_abi_laboratory(self, command, original_lib, replace_lib, name):
        """
        Shared function to run (and return a result)
        """
        disable_reports = os.environ.get("ABILAB_DISABLE_REPORTS") is not None
        if self.cache_dir and not disable_reports:
            cache_key = os.path.join(
                self.cache_dir,
                "%s-abi-laboratory-%s.html" % (original_lib.strip(os.sep), name),
            )
            command = f"{command} {cache_key}"

        res = timed_run(command)
        res["command"] = command

        # The spliced lib and original
        res["spliced_lib"] = replace_lib
        res["original_lib"] = original_lib

        # If there is a libabigail output, print to see
        if res["message"] != "":
            print(res["message"])
        is_compatible = (
            "Binary compatibility: 100%" in res["message"]
            and "Source compatibility: 100%" in res["message"]
        )
        res["prediction"] = res["return_code"] == 0 and is_compatible
        return res

    def splice_equivalent_libs(self, splice):
        """
        In the case of splicing "the same lib" into itself (a different version)
        we can do matching based on names. We can use abicomat with binaries, and
        abidiff for just between the libs.
        """
        basename = ("%s-%s" % (splice.package, splice.splice)).replace("@", "-v")

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

    def run_diff(self, splice):
        """
        Run pairwise diffs for libs we need.
        """
        # For each original (we assume working) binary, find its deps from elfcall,
        # and then match to the equivalent lib (via basename) for the splice
        original_deps = self.create_elfcall_deps_lookup(splice, splice.original)
        spliced_deps = self.create_elfcall_deps_lookup(splice, splice.spliced)

        # Create a set of predictions for each of libs combination
        predictions = []

        for libA, metaA in original_deps.items():
            for libB, metaB in spliced_deps.items():

                libA_fullpath = metaA["lib"]
                libB_fullpath = metaB["lib"]
                libs = [libA, libB]
                libs.sort()
                libs_uid = "-".join(libs).replace(".", "-")

                res = self.run_abi_laboratory(libA_fullpath, libB_fullpath, libs_uid)
                res["splice_type"] = "different_lib"
                predictions.append(res)

        if predictions:
            splice.predictions["abi-laboratory"] = predictions
            print(splice.predictions)
