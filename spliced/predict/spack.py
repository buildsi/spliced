# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import spliced.utils as utils
from .base import Prediction


class SpackTest(Prediction):
    """
    If we find this is a spack package (e.g, installed in a spack root) run spack test for the splice.
    """

    def spack_test(self, identifier):
        """
        Run spack tests for original and spliced
        """
        executable = utils.which("spack")
        cmd = "%s test run %s" % (executable, identifier)
        res = utils.run_command(cmd)
        res["prediction"] = True if res["return_code"] == 0 else False
        res["command"] = cmd
        return res

    def predict(self, splice):
        splice.predictions["spack-test"] = []

        # Run spack tests for original and spliced
        if splice.original_id:
            test_original = self.spack_test(splice.original_id)
            test_original["install"] = "original"
            splice.predictions["spack-test"].append(test_original)
        if splice.spliced_id:
            test_spliced = self.spack_test(splice.spliced_id)
            test_spliced["install"] = "spliced"
            splice.predictions["spack-test"].append(test_spliced)
