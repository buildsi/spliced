# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

from .base import Prediction, match_by_prefix
from symbolator.asp import PyclingoDriver, ABIGlobalSolverSetup, ABICompatSolverSetup
from symbolator.facts import get_facts
from symbolator.corpus import JsonCorpusLoader, Corpus

import os


class SymbolatorPrediction(Prediction):
    def predict(self, splice):
        """
        Run symbolator to add to the predictions
        """
        if splice.different_libs:
            return self.splice_different_libs(splice)
        return self.splice_equivalent_libs(splice)

    def splice_different_libs(self, splice):
        """
        This is subbing in a library with a version of itself, and requires binaries
        """
        raise NotImplementedError

    def splice_equivalent_libs(self, splice):
        """
        This is subbing in a library with a version of itself, and requires binaries
        """
        # For each original (we assume working) binary, find its deps from elfcall,
        # and then match to the equivalent lib (via basename) for the splice
        original_deps = self.create_elfcall_deps_lookup(splice, splice.original)
        spliced_deps = self.create_elfcall_deps_lookup(splice, splice.spliced)

        # A corpora cache to not derive again if we already have
        corpora = {}

        # Create a set of predictions for each spliced binary / lib combination
        predictions = []

        for binary, meta in original_deps.items():
            # Match the binary to the spliced one
            if binary not in spliced_deps:
                continue

            spliced_meta = spliced_deps[binary]
            binary_fullpath = meta["lib"]

            # We must find a matching lib for each based on prefix
            matches = match_by_prefix(meta["deps"], spliced_meta["deps"])

            # If we don't have matches, nothing to look at
            if not matches:
                continue

            # Cache the corpora if we don't have it yet
            if binary_fullpath not in corpora:
                corpora[binary_fullpath] = get_corpus(binary_fullpath)

            # Also cache the lib (original or after splice) if we don't have it yet
            for match in matches:
                for _, lib in match.items():
                    if lib not in corpora:
                        corpora[lib] = get_corpus(lib)

                # Make the splice prediction with symbolator for the match
                # The original symbolator tried to create the entire space - this one is more conservative
                # and just looks at what A needs, and what each of B (original) and C (spliced) provide
                result = run_replacement_splice(
                    corpora[binary_fullpath],
                    corpora[match["original"]],
                    corpora[match["spliced"]],
                )
                result["binary"] = binary_fullpath
                result["splice_type"] = "same_lib"
                result["original_lib"] = match["original"]
                result["spliced_lib"] = match["spliced"]
                result["prediction"] = True if not result["missing"] else False
                predictions.append(result)

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
