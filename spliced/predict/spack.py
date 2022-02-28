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

    def predict(self, splice):
        if not splice.id or not splice.id.startswith("/"):
            return

        # Check each binary to match the command
        executable = utils.which("spack")
        cmd = "%s test run %s" % (executable, splice.id)
        res = utils.run_command(cmd)
        res["prediction"] = True if res["return_code"] == 0 else False
        res["command"] = cmd
        splice.predictions["spack-test"] = [res]
