# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)


import spliced.utils as utils
from time import time

import os


class Prediction:
    """
    A prediction is a base for assessing a Splice and making predictions.
    """

    def predict(self, splice):
        raise NotImplementedError

    def __str__(self):
        return str(self.__class__.__name__)

    # Elfcall metadata functions
    # We assume now that most experiment runners (and predictors) could use this
    # If we derive another means, this can be generalized
    def find_elfcall_deps_for(self, splice, lib):
        """
        Given a library (that is assumed to be in metadata, from elfcall)
        find libraries that the linker is assumed to hit and find symbols.
        """
        deps = set()
        for _, symbols in splice.metadata[lib].items():
            for _, meta in symbols.items():
                if "lib" not in meta:
                    continue
                deps.add(meta["lib"]["realpath"])
        return deps

    def create_elfcall_deps_lookup(self, splice, libs):
        """
        This is subbing in a library with a version of itself, and requires binaries
        """
        deps = {}
        for lib in libs:
            deps[os.path.basename(lib)] = {
                "lib": lib,
                "deps": self.find_elfcall_deps_for(splice, lib),
            }
        return deps


def time_run_decorator(func):
    """
    Decorator to add run seconds to result
    """

    def wrap_func(*args, **kwargs):
        t1 = time()
        result = func(*args, **kwargs)
        t2 = time()
        result["seconds"] = t2 - t1
        return result

    return wrap_func


@time_run_decorator
def timed_run(cmd):
    return utils.run_command(cmd)


def get_prefix(lib):
    return os.path.basename(lib).split(".")[0]


def match_by_prefix(meta, spliced_meta):
    """
    Given an iterable of two things, match based on library prefix. E.g.,
    basename -> split at . -> match first piece
    """
    matches = []
    for binary_dep in meta:
        for spliced_dep in spliced_meta:
            # No use to compare exact same libs
            if spliced_dep == binary_dep:
                continue
            spliced_prefix = get_prefix(spliced_dep)
            dep_prefix = get_prefix(binary_dep)
            if spliced_prefix == dep_prefix:
                matches.append({"original": binary_dep, "spliced": spliced_dep})
    return matches
