# Copyright 2013-2022 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

# An experiment loads in a splice setup, and runs a splice session.

from .base import Experiment
import re
import os
import sys
import traceback
import spliced.utils as utils
from spliced.logger import logger
from elfcall.main import BinaryInterface

try:
    import spack.binary_distribution as bindist
    import spack.user_environment as uenv
    import spack.util.environment
    import spack.rewiring
    import spack.bootstrap
    import spack.store
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

        spec_main = self.concretize(
            self.package, error_message="package-concretization-failed"
        )
        if not spec_main:
            return []

        # Failure case 1: the main package does not build
        if not self.do_install(spec_main, "package-install-failed", name=self.package):
            return []

        # The second library we can try splicing all versions
        # This is the splice IN and splice OUT
        spec_spliced = Spec(self.splice)

        # A splice with the same package as the library is the first type
        # For this case, we already have a version in mind
        if self.splice == self.replace and "@" in self.splice:
            return self.do_splice(self.splice, spec_main, transitive)

        # If the splice and replace are different, we can't attempt a splice with
        # spack (there is simply no support for it) but we can emulate it
        elif self.splice != self.replace and "@" in self.splice:
            return self.mock_splice(self.splice, self.replace, spec_main)

        # New spack requires concretized to ask for package
        spec_spliced = self.concretize(
            spec=spec_spliced, error_message="splice-concretization-failed"
        )
        if not spec_spliced:
            return

        if self.splice != self.replace:
            for version in self.get_sorted_versions(spec_spliced):
                splice = "%s@%s" % (self.splice, version)
                self.mock_splice(splice, self.replace, spec_main)

        # Otherwise, splice all versions
        elif self.splice == self.replace:
            for version in self.get_sorted_versions(spec_spliced):
                splice = "%s@%s" % (self.splice, version)
                self.do_splice(splice, spec_main, transitive)

        else:
            print(
                "Splice is %s and replace spec is %s we do not handle this case"
                % (self.splice, self.replace)
            )

    def get_sorted_versions(self, spec):
        """
        Helper function to get sorted versions (for consistency)
        """
        versions = set()
        for version, vmeta in spec.package.versions.items():

            # Do not provide deprecated versions
            if not version or vmeta.get("deprecated", False) == True:
                continue
            versions.add(str(version))
        return sorted(list(versions))

    def do_install(self, spec, error_message, name=None, different_libs=False):
        """
        Helper function to do an install.
        """
        # Cut out early if installed
        if spec.installed:
            return True

        if not name:
            name = f"{spec.name}@{spec.version}"
        # Failure case 1: the main package does not build
        try:
            spec.package.do_install(force=True)
            return True
        except:
            traceback.print_exc()
            self.add_splice(
                error_message, success=False, splice=name, different_libs=different_libs
            )
            return False

    def concretize(
        self,
        spec_name=None,
        error_message="spec-concretization-failed",
        spec=None,
        different_libs=False,
    ):
        """
        A shared function to attempt concretization.
        """
        # Try to first concretize the splice dependency
        try:
            if spec:
                spec.concretize()
                return spec
            return Spec(spec_name).concretized()
        except:
            traceback.print_exc()
            self.add_splice(
                error_message,
                success=False,
                splice=spec_name,
                different_libs=different_libs,
            )

    def mock_splice(self, splice_name, replace_name, spec_main):
        """
        A mock splice is not possible with spack (it usually means replacing one
        dependency with another that isn't an actual dependency) but we can still
        install the needed specs and then add their libs / binaries for other
        predictors. A "mock" of different libs means different_libs is set to True
        on the splice.
        """
        print("Preparing mock splice for %s -> %s" % (replace_name, splice_name))

        # Try to first concretize the splice dependency
        dep = self.concretize(
            splice_name, "mock-splice-concretization-failed", different_libs=True
        )
        if not dep:
            return

        # And install the dependency
        if not self.do_install(
            dep, "mock-splice-install-failed", name=spec_name, different_libs=True
        ):
            return

        # And also the replacement spec
        replace = self.concretize(
            replace_name, "mock-replace-concretization-failed", different_libs=True
        )
        if not replace:
            return

        # And install the dependency
        if not self.do_install(
            replace,
            "mock-replace-install-failed",
            name=replace_name,
            different_libs=True,
        ):
            return

        # If we get here, we can add binaries for the main thing, and all libs from te splice and replace
        splice = self.add_splice(
            "mock-splice-success", success=True, splice=splice_name, different_libs=True
        )
        self._populate_splice(splice, spec_main, replace)

    def do_splice(self, splice_name, spec_main, transitive=True):
        """
        do the splice, the spliced spec goes into the main spec
        """
        print("Testing splicing in (and out) %s" % splice_name)

        dep = self.concretize(splice_name, "splice-concretization-failed")
        if not dep:
            return

        # Failure case 3: the dependency does not build, we can't test anything here
        if not self.do_install(dep, "splice-install-failed", name=splice_name):
            return

        # Failure case 4: the splice itself fails
        try:
            spliced_spec = spec_main.splice(dep, transitive=transitive)
        except:
            traceback.print_exc()
            splice = self.add_splice("splice-failed", success=False, splice=splice_name)
            return

        # Failure case 5: the dag hash is unchanged
        if spec_main is spliced_spec or spec_main.dag_hash() == spliced_spec.dag_hash():
            splice = self.add_splice(
                "splice-dag-hash-unchanged", success=False, splice=splice_name
            )
            return

        # Failure case 6: the rewiring fails during rewiring
        try:
            spack.rewiring.rewire(spliced_spec)
        except:
            traceback.print_exc()
            splice = self.add_splice(
                "rewiring-failed", success=False, splice=splice_name
            )
            return

        # Failure case 5: the spliced prefix doesn't exist, so there was a rewiring issue
        if not os.path.exists(spliced_spec.prefix):
            splice = self.add_splice(
                "splice-prefix-doesnt-exist", success=False, splice=splice_name
            )
            return

        # If we get here, a success case!
        splice = self.add_splice("splice-success", success=True, splice=splice_name)

        # Prepare the libs / binaries for the splice (also include original dependency paths)
        self._populate_splice(splice, spliced_spec, spec_main)
        return self.splices

    def _populate_spack_directory(self, path):
        """
        Given a path, find all libraries and resolve links.
        """
        paths = set()
        if not os.path.exists(path):
            return paths
        for contender in utils.recursive_find(path):
            if os.path.islink(contender):
                contender = os.path.realpath(contender)
            paths.add(contender)
        return paths

    def get_spack_ld_library_paths(self, original):
        """
        Get all of spack's changes to the LD_LIBRARY_PATH for elfcall
        """
        loads = set()

        # Get all deps to add to path
        env_mod = spack.util.environment.EnvironmentModifications()
        for depspec in original.traverse(root=True, order="post"):
            env_mod.extend(uenv.environment_modifications_for_spec(depspec))
            env_mod.prepend_path(uenv.spack_loaded_hashes_var, depspec.dag_hash())

        # Look for appends to LD_LIBRARY_PATH
        for env in env_mod.env_modifications:
            if env.name == "LD_LIBRARY_PATH":
                loads.add(env.value.strip())
        return list(loads)

    def _populate_splice(self, splice, spliced_spec, original):
        """
        Prepare each splice to also include binaries and libs involved.
        The populate splice algorithm is included here. For the spack experiment,
        the splice must be successful to test it.

        1. Find all binaries and libraries for original package and spliced package
        2. Use elfcall on each found binary or library to get list of libraries
           and symbols that the linker would find. This set stops for each one
           when all imported (needed) symbols are found
        3. Present this result to predictor
           Libabigail and symbolator will name match and do "diffs"
           Smeagle doesn't care about the original
           We will need elfcall to report back if there are any missing
           imported symbols. If yes, STOP (optimization)
           SEE SMEAGLE FOR REST
        """
        # Populate list of all binaries/libs for each of original and spliced
        # This does not include dependencies - these will be added in spice.metadata
        # below using elfcall!
        for subdir in ["bin", "lib"]:
            original_dir = os.path.join(original.prefix, subdir)
            [
                splice.original.add(x)
                for x in self._populate_spack_directory(original_dir)
            ]
            splice_dir = os.path.join(spliced_spec.prefix, subdir)
            [splice.spliced.add(x) for x in self._populate_spack_directory(splice_dir)]

        # IMPORTANT we must emulate "spack load" in order for libs to be found...
        loads = {}
        with spack.store.db.read_transaction():
            loads["original"] = self.get_spack_ld_library_paths(original)
            loads["spliced"] = self.get_spack_ld_library_paths(spliced_spec)

        # Save the ld library path loads
        splice.paths["loads"] = loads

        # Keep set of dependency libs to run elfcall on (other spack deps)
        dep_libs = set()
        all_libs = set()

        def iter_deps(res, key):
            for _, m in res["found"].items():
                if "lib" in m:
                    dep_libs.add((m["lib"]["realpath"], key))
                    all_libs.add(m["lib"]["realpath"])

        # Parse both original libs and spliced libs, ensuring to update LD_LIBRARY_PATH
        keepers = set()
        for lib in splice.original:
            res = self.run_elfcall(lib, ld_library_paths=loads["original"])
            if not res:
                # If we fail to parse it, cannot be in analysis
                continue
            keepers.add(lib)
            iter_deps(res, "original")
            all_libs.add(lib)
            splice.metadata[lib] = res

        # Update orignal set
        splice.original = keepers
        keepers = set()
        for lib in splice.spliced:

            # Some shared dependency, don't need to parse twice!
            if lib in splice.metadata:
                continue
            res = self.run_elfcall(lib, ld_library_paths=loads["spliced"])
            if not res:
                continue
            keepers.add(lib)
            iter_deps(res, "spliced")
            all_libs.add(lib)
            splice.metadata[lib] = res

        # Update spliced set
        splice.spliced = keepers

        # Run elfcall on all non system libs
        for libset in dep_libs:
            lib, ld_path_type = libset
            all_libs.add(lib)

            # If the dep is a system lib, don't include for now
            if re.search("^(/usr|/lib)", lib):
                continue

            key = "%s:%s" % (ld_path_type, lib)
            if key in splice.metadata:
                continue
            res = self.run_elfcall(lib, ld_library_paths=loads[ld_path_type])
            if res:
                splice.metadata[key] = res

        # Calculate sizes for all libs
        for lib in all_libs:
            splice.stats["sizes_bytes"][lib] = os.path.getsize(lib)

        # Add the dag hash as the identifier
        splice.add_spec("original", original)
        splice.add_spec("spliced", spliced_spec)

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


def get_linked_deps(spec):
    """
    A helper function to only return a list of linked deps
    """
    linked_deps = []
    contenders = spec.to_dict()["spec"]["nodes"][0].get("dependencies", [])
    for contender in contenders:
        if "link" in contender["type"]:
            linked_deps.append(contender["name"])

    deps = []
    for contender in spec.dependencies():
        if contender.name in linked_deps:
            deps.append(contender)
    return deps


def add_libraries(spec, library_name=None):
    """
    Given a spliced spec, get a list of its libraries matching a name (e.g., a library
    that has been spliced in). E.g., if the spec is curl, we might look for zlib.
    """
    # We will return a list of libraries
    libs = []

    # For each depedency, add libraries
    deps = get_linked_deps(spec)

    # Only choose deps that are for link time
    seen = set([x.name for x in deps])
    while deps:
        dep = deps.pop(0)
        new_deps = [x for x in get_linked_deps(dep) if x.name not in seen]
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
