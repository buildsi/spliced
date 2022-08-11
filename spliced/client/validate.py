# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)


import os

import jsonschema

import spliced.utils as utils
from spliced.logger import logger
from spliced.schemas import spliced_result_schema


def main(args, parser, extra, subparser):
    """
    Validate a spliced result file
    """
    if not os.path.exists(args.json_file):
        logger.exit("%s does not exist." % args.json_file)
    content = utils.read_json(args.json_file)
    if jsonschema.validate(content, schema=spliced_result_schema) == None:
        logger.info("%s is valid! 😂️" % args.json_file)
    else:
        logger.exit("%s is not valid 😥️" % args.json_file)
