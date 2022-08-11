# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import spliced.utils as utils

from .base import Prediction, timed_run


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
        res = timed_run(cmd)
        res["prediction"] = True if res["return_code"] == 0 else False
        res["command"] = cmd
        return res

    def predict(self, splice, predict_type=None):
        """
        The spack predictor runs spack test for the original and splice.
        """
        tests = {}
        for key, identifier in splice.ids.items():
            result = self.spack_test(identifier)
            tests[key] = result
        print(tests)
        splice.predictions["spack-test"] = tests
