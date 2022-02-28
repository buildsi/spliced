# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

# An experiment loads in a splice setup, and runs a splice session.

from .base import Experiment
import os
import sys
import shlex

try:
    import spack.binary_distribution as bindist
    import spack.rewiring
    import spack.bootstrap
    from spack.spec import Spec
except Exception as e:
    sys.exit("This needs to be run from spack python, also: %s" % e)


class SpackExperiment(Experiment):
    def __init__(self):
        super().__init__()

        # Ensure we have debug flags added
        os.putenv("SPACK_ADD_DEBUG_FLAGS", "true")
        os.environ["SPACK_ADD_DEBUG_FLAGS"] = "true"

    def run(self, *args, **kwargs):
        """
        Perform a splice with a SpecA (a specific spec with a binary),
        and SpecB (the high level spec that is a dependency that we can test
        across versions).

        Arguments:
        package (specA_name): the name of the main package we are splicing up
        splice (specB_name): the spec we are removing / switching out
        replace (specC_name): the spec we are splicing in (replacing with)

        For many cases, specB and specC might be the same, but not always.
        """
        transitive = kwargs.get("transitive", True)

        print("Concretizing %s" % self.package)
        spec_main = Spec(self.package).concretized()

        # Failure case 1: the main package does not build
        try:
            spec_main.package.do_install(force=True)
        except:
            self.add_splice("package-install-failed", success=False)
            return []

        # The second library we can try splicing all versions
        # This is the splice IN and splice OUT
        spec_spliced = Spec(self.splice)

        # A splice with the same package as the library is the first type
        # For this case, we already have a version in mind
        if self.splice == self.replace and "@" in self.splice:
            self.do_splice(self.splice, spec_main, transitive)

        # If the splice and replace are different, we can't attempt a splice with
        # spack (there is simply no support for it) but we can emulate it
        elif self.splice != self.replace and "@" in self.splice:
            self.mock_splice(self.splice, self.replace, spec_main)

        elif self.splice != self.replace:
            for version in spec_spliced.package.versions:
                if not version:
                    continue
                splice = "%s@%s" % (self.splice, version)
                self.mock_splice(splice, self.replace, spec_main)

        # Otherwise, splice all versions
        elif self.splice == self.replace:
            for version in spec_spliced.package.versions:
                if not version:
                    continue

                # spec_spliced version goes into spec_main
                splice = "%s@%s" % (self.splice, version)
                self.do_splice(splice, spec_main, transitive)
        else:
            print(
                "Splice is %s and replace spec is %s we do not handle this case"
                % (self.splice, self.replace)
            )

    def mock_splice(self, splice_name, replace_name, spec_main):
        """
        A mock splice is not possible with spack (it usually means replacing one
        dependency with another that isn't an actual dependency) but we can still
        install the needed specs and then add their libs / binaries for other
        predictors.
        """
        print("Preparing mock splice for %s -> %s" % (replace_name, splice_name))

        # Try to first concretize the splice dependency
        try:
            dep = Spec(splice_name).concretized()
        except:
            self.add_splice(
                "mock-splice-concretization-failed", success=False, splice=splice_name
            )
            return

        # And install the dependency
        try:
            dep.package.do_install(force=True)
        except:
            self.add_splice(
                "mock-splice-install-failed", success=False, splice=splice_name
            )
            return

        # And also the replacement spec
        try:
            replace = Spec(replace_name).concretized()
        except:
            self.add_splice(
                "mock-replace-concretization-failed", success=False, splice=replace_name
            )
            return

        # And install the replacement
        try:
            replace.package.do_install(force=True)
        except:
            self.add_splice(
                "mock-replace-install-failed", success=False, splice=replace_name
            )
            return

        # If we get here, we can add binaries for the main thing, and all libs from te splice and replace
        splice = self.add_splice(
            "mock-splice-success", success=True, splice=splice_name
        )
        self._populate_mock_splice(splice, spec_main, dep, replace)

    def do_splice(self, splice_name, spec_main, transitive=True):
        """
        do the splice, the spliced spec goes into the main spec
        """
        print("Testing splicing in (and out) %s" % splice_name)

        # Failure case 2: dependency fails to concretize
        # We can't test anything here
        try:
            dep = Spec(splice_name).concretized()
        except:
            self.add_splice(
                "splice-concretization-failed", success=False, splice=splice_name
            )
            return

        # Failure case 3: the dependency does not build, we can't test anything here
        try:
            dep.package.do_install(force=True)
        except:
            self.add_splice("splice-install-failed", success=False, splice=splice_name)
            return

        # Failure case 4: the splice itself fails
        try:
            spliced_spec = spec_main.splice(dep, transitive=transitive)
        except:
            splice = self.add_splice("splice-failed", success=False, splice=splice_name)
            self._populate_failed_splice(splice, dep, spec_main)
            return

        # Failure case 5: the dag hash is unchanged
        if spec_main is spliced_spec or spec_main.dag_hash() == spliced_spec.dag_hash():
            splice = self.add_splice(
                "splice-dag-hash-unchanged", success=False, splice=splice_name
            )
            self._populate_failed_splice(splice, dep, spec_main)
            return

        # Failure case 6: the rewiring fails during rewiring
        try:
            spack.rewiring.rewire(spliced_spec)
        except:
            splice = self.add_splice(
                "rewiring-failed", success=False, splice=splice_name
            )
            self._populate_failed_splice(splice, dep, spec_main)
            return

        # Failure case 5: the spliced prefix doesn't exist, so there was a rewiring issue
        if not os.path.exists(spliced_spec.prefix):
            splice = self.add_splice(
                "splice-prefix-doesnt-exist", success=False, splice=splice_name
            )
            self._populate_failed_splice(splice, dep, spec_main)
            return

        # If we get here, a success case!
        splice = self.add_splice("splice-success", success=True, splice=splice_name)

        # Prepare the libs / binaries for the splice (also include original dependency paths)
        self._populate_splice(splice, spliced_spec, spec_main)
        return self.splices

    def _populate_mock_splice(self, splice, original, dep, replace):
        """
        A mock splice is not actually done by spack, but we add all libs to emulate
        a splice.
        """
        binary = None
        if self.command:

            # We need to know the binary of interest from the command
            binary = shlex.split(self.command)[0]

        # We still care about the original lib we are testing
        splice.binaries["original"] = list(add_contenders(original, "bin", binary))

        # We don't need to "discover" the dependency or replacement, we have them directly
        splice.libs["dep"] = [
            {"dep": str(dep), "paths": list(add_contenders(dep, "lib"))}
        ]
        splice.libs["replace"] = [
            {"dep": str(replace), "paths": list(add_contenders(replace, "lib"))}
        ]

    def _populate_failed_splice(self, splice, dep, original):
        """
        Given a failed spack splice, try to still populate the failed object with
        libs and binaries from the original library and dependency.
        """
        binary = None
        if self.command:

            # We need to know the binary of interest from the command
            binary = shlex.split(self.command)[0]

        # Add binaries to the libary for just the original lib
        splice.binaries["original"] = list(add_contenders(original, "bin", binary))

        # The splice name won't have a version
        spliced_lib = self.splice.split("@")[0]

        # And add libs for the original and (non-spliced) dependency
        splice.libs["dep"] = add_libraries(dep, spliced_lib)
        splice.libs["original"] = add_libraries(original)

    def _populate_splice(self, splice, spliced_spec, original):
        """
        Prepare each splice to also include binaries and libs involved.
        """
        # If we have a command, get te binary of interest from it
        # Otherwise we have to add all binaries
        binary = None
        if self.command:

            # We need to know the binary of interest from the command
            binary = shlex.split(self.command)[0]

        # Add binaries to the libary for both spliced and original lib
        splice.binaries["spliced"] = list(add_contenders(spliced_spec, "bin", binary))
        splice.binaries["original"] = list(add_contenders(original, "bin", binary))

        # The splice name won't have a version
        spliced_lib = self.splice.split("@")[0]

        # And add libs for the spliced dependency (each from original and spliced)
        splice.libs["spliced"] = add_libraries(spliced_spec, spliced_lib)
        splice.libs["original"] = add_libraries(original, spliced_lib)

        # Add the dag hash as the identifier
        splice.add_identifier("/" + spliced_spec.dag_hash()[0:6])


def add_libraries(spec, library_name=None):
    """
    Given a spliced spec, get a list of its libraries matching a name (e.g., a library
    that has been spliced in). E.g., if the spec is curl, we might look for zlib.
    """
    # We will return a list of libraries
    libs = []

    # For each depedency, add libraries
    deps = spec.dependencies()
    seen = set([x.name for x in deps])
    while deps:
        dep = deps.pop(0)
        new_deps = [x for x in dep.dependencies() if x.name not in seen]
        [seen.add(x.name) for x in new_deps]
        deps += new_deps

        # We will only have a library name if we switching out something for itself
        if library_name and dep.name == library_name:
            libs.append({"dep": str(dep), "paths": list(add_contenders(dep, "lib"))})
        elif not library_name:
            libs.append({"dep": str(dep), "paths": list(add_contenders(dep, "lib"))})

    return libs


def add_contenders(spec, loc="lib", match=None):
    """
    Given a spec, find contender binaries and/or libs
    """
    binaries = set()
    manifest = bindist.get_buildfile_manifest(spec.build_spec)
    for contender in manifest.get("binary_to_relocate"):
        # Only add binaries of interest, if relevant
        if match and os.path.basename(contender) != match:
            continue
        if contender.startswith(loc):
            binaries.add(os.path.join(spec.prefix, contender))
    return binaries
