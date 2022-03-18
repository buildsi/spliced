# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

__version__ = "0.0.15"
AUTHOR = "Vanessa Sochat"
NAME = "spliced"
PACKAGE_URL = "https://github.com/buildsi/spliced"
KEYWORDS = "splicing, spack, packages"
DESCRIPTION = "Emulate or predict splicing outcomes."
LICENSE = "LICENSE-MIT"

################################################################################
# Global requirements

INSTALL_REQUIRES = (
    ("pyaml", {"min_version": None}),
    ("requests", {"min_version": None}),
    ("symbolator-python", {"min_version": None}),
    ("jsonschema", {"min_version": None}),
)


TESTS_REQUIRES = (("pytest", {"min_version": "4.6.2"}),)

################################################################################
# Submodule Requirements (versions that include database)

INSTALL_REQUIRES_ALL = INSTALL_REQUIRES + TESTS_REQUIRES
