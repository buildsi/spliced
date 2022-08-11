# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

# An experiment loads in a splice setup, and runs a splice session.

import os

from elfcall.main import BinaryInterface

from spliced.logger import logger

from .base import Experiment


class ManualExperiment(Experiment):
    def populate_elfcall(self, splice, libA, libB):
        """
        Derive library metadata for each of the original and splice spec
        """
        liba_res = self.run_elfcall(libA)
        libb_res = self.run_elfcall(libB)
        splice.original.add(libA)
        splice.spliced.add(libB)

        splice.metadata[libA] = liba_res
        splice.metadata[libB] = libb_res

        # Calculate sizes for all libs
        for lib in libA, libB:
            splice.stats["sizes_bytes"][lib] = os.path.getsize(lib)
        return splice

    def run(self, *args, **kwargs):
        """
        Given two libraries, A and B, with debug, do a direct comparison.
        Arguments:
        package (specA_name): the name of package A
        replace (specB_name): the name of package B

        For many cases, specA and specB might be the same, but not always.
        """
        # Both package and splice must exist
        if not self.package or not self.splice:
            logger.exit(f"Either {self.package} or {self.splice} is not defined.")

        if not os.path.exists(self.package) or not os.path.exists(self.splice):
            logger.exit(f"Either {self.package} or {self.splice} does not exist.")
        self.diff(self.package, self.splice)

    def diff(self, libA, libB):
        """
        Prepare setup to do a diff.

        specA: the main package
        specB: the to splice
        """
        splice = self.add_splice(
            "diff-libraries-present",
            success=True,
            package=libA,
            splice=libB,
            different_libs=True,
        )
        self.populate_elfcall(splice, libA, libB)

    def run_elfcall(self, lib, ld_library_paths=None):
        """
        A wrapper to run elfcall and ensure we add LD_LIBRARY_PATH additions
        (usually from spack)
        """
        bi = BinaryInterface(lib)

        # We don't want to include non-ELF files (and possible limitation - we cannot parse Non ELF)
        try:
            return bi.gen_output(
                lib,
                secure=False,
                no_default_libs=False,
                ld_library_paths=ld_library_paths,
            )
        except:
            logger.warning(
                "Cannot parse binary or library %s, not including in analysis." % lib
            )
