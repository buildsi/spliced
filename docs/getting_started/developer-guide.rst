.. _getting_started-developer-guide:

===============
Developer Guide
===============

This developer guide includes more complex interactions like adding experiments
or using containers. If you haven't read :ref:`getting_started-installation`
you should do that first.

Add An Experiment
==================

The core of an experiment is to be able to run the initial steps for a splice,
and return the splice object, which should have binaries and libraries for a spec pre and post splice,
along with other metadata. This general format allows us to have an experiment runner like spack
(that will install what we need and then set the paths) or eventually a manual runner (where we can just
set them arbitrarily to our liking).

Add A Predictor
===============

A predictor should be added as a module to [spliced/predict](spliced/predict) so it is retrieved
on init. It should have a main function, predict, which takes a splice object and optional kwargs.
At this point you can iterate through the splice structure to use whatever metadata you need. E.g.,:

 - splice.libs: is a dictionary with "original" and "spliced" for original and spliced libs, respectively
 - splice.binaries: is the same structure, but with binaries for the original and spliced package
 
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
