.. _getting_started-developer-guide:

===============
Developer Guide
===============

This developer guide includes more complex interactions like adding experiments
or using containers. If you haven't read :ref:`getting_started-installation`
you should do that first.

Design of Spliced
=================

As a reminder, spiced works by having **experiment runners** (e.g., spack) that present a splice object with metadata about libraries to a **predictor** to parse (and make predictions for). This design section will include details for how the experiment runner and subsequent predictors work.

Spack Experiment Runner
-----------------------

The spack experiment runner works by starting with a main library (e.g., caliper) and a dependency of interest (e.g., papi). We then, for each version of the depedency:

1. Perform a splice of the new version into the main package to derive a new spliced directory.
2. Find libs and binaries within the new (spliced) package install (and the original)
3. Use `Elfcall <https://vsoch.github.io/elfcall>`_ to emulate the linker and find paths of libraries with needed (undefined) symbols.
4. Present the elfcall output to each predictor to use appropriately.

In the case of a "diff" comparator like libabigail or symbolator, we match names of libraries that are used for each of the original dependency (A) and spliced dependency (B) case.

In the case of smeagle, we first check if elfcall didn't find any symbols, and if so we stop and report failure. The smeagle model depends on function symbol names and will always fail if a symbol is entirely missing. If we found all our symbols, we then
derive first smeagle json (saved to a cache based on the library name) and 
then a scoped set of asp facts the main library (A) and the entire set of dependencies (under the namespace B) to compare to. Since elfcall only matches one library to one symbol, there won't be conflicts within the B space.

**Note** that elfcall can only parse ELF. A library or binary that is not ELF cannot be included, and this is a small set but still represents a limitation of the analysis.


Add An Experiment
=================

The core of an experiment is to be able to run the initial steps for a splice,
and return the splice object, which should have binaries and libraries for a spec pre and post splice,
along with other metadata. This general format allows us to have an experiment runner like spack
(that will install what we need and then set the paths) or eventually a manual runner (where we can just
set them arbitrarily to our liking).

Add A Predictor
===============

A predictor should be added as a module to ``spliced/predict`` so it is retrieved
on init. It should have a main function, predict, which takes a splice object and optional kwargs.
At this point you can iterate through the splice structure to use whatever metadata you need. The splice metadata is derived from `Elfcall _<https://vsoch.github.io/elfcall>`_ which should have all the sets of libraries found and symbols for each (and we stop when all needed and undefined symbols are found). E.g.,:

## TODO need to update here
 
Importantly, your predictor should set `spliced.predictions[<name_of_predictor>]` to be a list of dictionaries,
where you can put any needed metadata. The binary/lib is suggested, along with a return code or message from the console,
and *importantly* you should have a boolean true/false for "prediction" about whether the splice is predicted to work.
Here is an example list of results (with a single splice prediction using abicompat) from libaibgail.


.. code-block:: python

    "predictions": {
    "libabigail": [
        {
            "message": "",
            "return_code": 0,
            "binary": "/home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/curl-7.50.2-7ybfviq4uauvq4hhggxn3npc6ib4clr3/bin/curl",
            "lib": "/home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/zlib-1.2.11-3kmnsdv36qxm3slmcyrb326gkghsp6px/lib/libz.so.1.2.11",
            "original_lib": "/home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/zlib-1.2.11-3kmnsdv36qxm3slmcyrb326gkghsp6px/lib/libz.so.1.2.11",
            "prediction": true
        }
    ],


To be clear, the predictor must save a list of predictions to the splice.predicitions, keyed by the name, and the following fields are requried:

 - binary
 - lib
 - prediction
 
The following fields are not required but suggested:

 - message (the terminal output of running the predictor)
 - return_code
 - original_lib or original_binary if relevant for the command
 - any other relevant results information


Develop with Docker
===================

You can easily build a docker container in the present working directory:

.. code-block:: console

    $ docker build -t spliced .
    
And then shell in, binding code so we can install from there.

.. code-block:: console

    $ docker run -it --entrypoint bash -v $PWD:/code spliced 

Install locally:

.. code-block:: console

    $ pip install -e .

And try generating and running a command:

.. code-block:: console

    $ spliced command examples/sqlite.yaml
    ...
    $ spliced splice --package sqlite@3.35.4 --splice zlib --runner spack --replace zlib --experiment sqlite sqlite3 -version
    pkg-sqlite@3.35.5-splice-zlib-with-zlib-experiment-sqlite-splices.json is valid! 😂️


Creating a container base
=========================

Typically, a container base should have the dependencies that you need to run your
splice. E.g., if you want to use the libabigial splicer, libabigail should
be installed. We provide a set of automated builds for containers to provide the software 
needed [here](docker) (e.g., including libabigail, spack, and symbolator) so you can use this container set,
or if you choose, bootstrap these containers for your own customization. Note that for these containers:

 - we provide several os bases - the default of the spliced execuable is ubuntu 20.04, and you can change this with `--container`
 - the containers are flagged with [spack labels](https://github.com/spack/label-schema) for `org.spack.compilers` to be discovered by the tool. If you don't provide labels, all compilers in the container will be used.
 - it's assumed you have software you need in the container, or use our container bases as testing CI bases and install there on the fly.
 
If you want to use the default containers provided by spliced, you shouldn't need to worry about this.
If you have any questions, don't hesitate to open an issue.
