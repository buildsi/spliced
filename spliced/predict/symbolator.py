# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from .base import Prediction
from symbolator.asp import PyclingoDriver, ABIGlobalSolverSetup, ABICompatSolverSetup
from symbolator.facts import get_facts
from symbolator.corpus import JsonCorpusLoader, Corpus

import itertools
import os


class SymbolatorPrediction(Prediction):
    def predict(self, splice):
        """
        Run symbolator to add to the predictions
        """
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
        This is subbing in a library with a version of itself, and requires binaries
        """
        # A corpora cache to not derive again if we already have
        corpora = {}

        binaries = splice.get_binaries()

        # Flatten original and replacement libs
        original_libs = list(itertools.chain(*[x["paths"] for x in original_libs]))
        replace_libs = list(itertools.chain(*[x["paths"] for x in replace_libs]))

        # Create a set of predictions for each spliced binary / lib combination
        predictions = []
        for binary in binaries:

            # Cache the corpora if we don't have it yet
            if binary not in corpora:
                corpora[binary] = get_corpus(binary)

            # Sub the original lib with the replacement
            for original_lib in original_libs:

                # Also cache the lib if we don't have it yet
                if original_lib not in corpora:
                    corpora[original_lib] = get_corpus(original_lib)

                for replace_lib in replace_libs:

                    # Also cache the lib if we don't have it yet
                    if replace_lib not in corpora:
                        corpora[replace_lib] = get_corpus(replace_lib)

                    # Make the splice prediction with symbolator
                    sym_result = run_replacement_splice(
                        corpora[binary], corpora[original_lib], corpora[replace_lib]
                    )
                    sym_result["binary"] = binary
                    sym_result["splice_type"] = "different_lib"
                    sym_result["lib"] = original_lib
                    sym_result["replace"] = replace_lib
                    sym_result["prediction"] = (
                        True if not sym_result["missing"] else False
                    )
                    predictions.append(sym_result)

        if predictions:
            splice.predictions["symbolator"] = predictions

    def splice_equivalent_libs(self, splice, libs):
        """
        This is subbing in a library with a version of itself, and requires binaries
        """
        # A corpora cache to not derive again if we already have
        corpora = {}

        binaries = splice.get_binaries()

        # Create a set of predictions for each spliced binary / lib combination
        predictions = []
        for binary in binaries:

            # Cache the corpora if we don't have it yet
            if binary not in corpora:
                corpora[binary] = get_corpus(binary)

            for libset in libs:
                for lib in libset["paths"]:

                    # Also cache the lib if we don't have it yet
                    if lib not in corpora:
                        corpora[lib] = get_corpus(lib)

                    # Make the splice prediction with symbolator
                    sym_result = run_symbols_splice(corpora[binary], corpora[lib])
                    sym_result["binary"] = binary
                    sym_result["splice_type"] = "same_lib"
                    sym_result["lib"] = lib
                    sym_result["prediction"] = (
                        True if not sym_result["missing"] else False
                    )
                    predictions.append(sym_result)

        if predictions:
            splice.predictions["symbolator"] = predictions


def run_symbol_solver(corpora):
    """
    A helper function to run the symbol solver.
    """
    driver = PyclingoDriver()
    setup = ABIGlobalSolverSetup()
    return driver.solve(
        setup,
        corpora,
        dump=False,
        logic_programs=get_facts("missing_symbols.lp"),
        facts_only=False,
        # Loading from json already includes system libs
        system_libs=False,
    )


def get_corpus(path):
    """
    Given a path, generate a corpus
    """
    setup = ABICompatSolverSetup()
    corpus = Corpus(path)
    return setup.get_json(corpus, system_libs=True, globals_only=True)


def run_replacement_splice(A, B, C):
    """
    A replacement splice is a binary (A), a library in it (B) and a replacement (C):
    """
    # This is te original library / binary
    loader = JsonCorpusLoader()
    loader.load(A)
    corpora = loader.get_lookup()

    # original set of symbols without splice to compare to
    corpora_result = run_symbol_solver(list(corpora.values()))

    # This is the one we want to splice out (remove)
    splice_loader = JsonCorpusLoader()
    splice_loader.load(B)
    splices = splice_loader.get_lookup()

    # Remove matching libraries based on the name
    # This is a list of names [libm...libiconv] including the binary
    to_remove = [x.split(".")[0] for x in list(splices.keys())]

    # Now we want to remove ANYTHING that is provided by this spliced lib
    corpora_spliced_out = {}
    for libname, lib in corpora.items():
        prefix = libname.split(".")[0]
        if prefix not in to_remove:
            corpora_spliced_out[libname] = lib

    # Now here is the corpora we want to replace with
    splice_loader = JsonCorpusLoader()
    splice_loader.load(C)
    replaces = splice_loader.get_lookup()

    # Add them to the main corpus
    for libname, lib in replaces.items():
        corpora_spliced_out[libname] = lib

    spliced_result = run_symbol_solver(list(corpora_spliced_out.values()))

    # Compare sets of missing symbols
    result_missing = [
        "%s %s" % (os.path.basename(x[0]).split(".")[0], x[1])
        for x in corpora_result.answers.get("missing_symbols", [])
    ]
    spliced_missing = [
        "%s %s" % (os.path.basename(x[0]).split(".")[0], x[1])
        for x in spliced_result.answers.get("missing_symbols", [])
    ]

    # these are new missing symbols after the splice
    missing = [x for x in spliced_missing if x not in result_missing]
    return {"missing": missing}


def run_symbols_splice(A, B):
    """
    Given two results, each a corpora with json values, perform a splice
    """
    result = {
        "missing": [],
        "selected": [],
    }

    # Spliced libraries will be added as corpora here
    loader = JsonCorpusLoader()
    loader.load(A)
    corpora = loader.get_lookup()

    # original set of symbols without splice
    corpora_result = run_symbol_solver(list(corpora.values()))

    # Now load the splices separately, and select what we need
    splice_loader = JsonCorpusLoader()
    splice_loader.load(B)
    splices = splice_loader.get_lookup()

    # If we have the library in corpora, delete it, add spliced libraries
    # E.g., libz.so.1.2.8 is just "libz" and will be replaced by anything with the same prefix
    corpora_lookup = {key.split(".")[0]: corp for key, corp in corpora.items()}
    splices_lookup = {key.split(".")[0]: corp for key, corp in splices.items()}

    # Keep a lookup of libraries names
    corpora_libnames = {key.split(".")[0]: key for key, _ in corpora.items()}
    splices_libnames = {key.split(".")[0]: key for key, _ in splices.items()}

    # Splices selected
    selected = []

    # Here we match based on the top level name, and add splices that match
    # (this assumes that if a lib is part of a splice corpus set but not included, we don't add it)
    for lib, corp in splices_lookup.items():

        # ONLY splice in those known
        if lib in corpora_lookup:

            # Library A was spliced in place of Library B
            selected.append([splices_libnames[lib], corpora_libnames[lib]])
            corpora_lookup[lib] = corp

    spliced_result = run_symbol_solver(list(corpora_lookup.values()))

    # Compare sets of missing symbols
    result_missing = [
        "%s %s" % (os.path.basename(x[0]).split(".")[0], x[1])
        for x in corpora_result.answers.get("missing_symbols", [])
    ]
    spliced_missing = [
        "%s %s" % (os.path.basename(x[0]).split(".")[0], x[1])
        for x in spliced_result.answers.get("missing_symbols", [])
    ]

    # these are new missing symbols after the splice
    missing = [x for x in spliced_missing if x not in result_missing]
    result["missing"] = missing
    result["selected"] = selected
    return result
