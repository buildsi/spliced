.. _getting_started-user-guide:

==========
User Guide
==========

Why spliced?
============

Spliced will allow you to run splice experiments using various predictor.
Let's review some terminology first.

 - **predictor**: is a tool that can take some set of binaries or libraries, and say "I think if you use A with B, it will work."
 - **experiment**: an experiment is a set of steps you can do to perform a splice. For example, running a splice experiment with spack means you provide libraries to spack, and it splices them.
 - **splice**: We typically call the library we want to "cut out" the splice.
 - **replace** We typically call the library we want to replace the splice with (or "splice in" if you prefer) the replacement library.
 

What experiments are available?
===============================

Currently, our main experiment runner is `spack <https://github.com/spack/spack>`_ and we are installing from a fork and branch
under vsoch to get extra functionality that may (or may not) eventually be integrated. We also plan to add a manual experiment - e.g.,
instead of asking spack to figure out how a package and dependencies work together, just shove two at each other and force it.
We haven't developed this use case yet.


What predictors are available?
==============================

As stated above, a **predictor** is a tool that can take some set of binaries or libraries, and say "I think if you use A with B, it will work."
spliced currently has the following predictors:

 - **actual**: This is a base level of predictor, which (given that you provide a testing command) will simply test a binary, as is, and tell you if it works. This is our "ground truth" for the other predictors that aren't actually testing anything, but just predicting. For this predictor we test the original install and the spec install.
 - **libabigail**: is a `library provided by RedHat <https://sourceware.org/libabigail/>`_ that provides tooling for assessing ABI compatibility. You'll need the tools installed on your path, and if using the spack experiment runner, it will fall back to installing them with spack.
 - **symbolator**: is a `simple library developed by the group here <https://github.com/buildsi/symbolator>`_ that makes predictions based on comparing symbol sets.
 - **spack-test**: will, given that the splice has an id that matches a spack dag hash, run tests associated with that spec.
 - **abi-laboratory**: will use the ``abi-dumper`` and ``abi-compliance-checker`` from the Abi Laboratory, and requires that you export ``SPLICED_ABILAB_CONTAINER`` to be a path to `the Singularity container here <>`_, as shown with the Singularity pull command below.
 - **smeagle**: is `another library being developed here <https://github.com/buildsi/Smeagle>`_ that is added but considered to be in experimental state. It requires `my branch of cle <https://github.com/vsoch/cle>`_.

.. code-block:: console

    $ singularity pull docker://ghcr.io/buildsi/abi-laboratory-docker
    $ export SPLICED_ABILAB_CONTAINER=$PWD/abi-laboratory-docker_latest.sif

Config File
===========

Great, so let's get started! A splice experiment starts with a config file, a YAML file 
to help you generate splicing commands, either to run yourself locally or to hand
of to an automated solution. It's a simple YAML file that should minimally have the following:


.. code-block:: yaml

    package: curl
    splice: zlib
    command: curl --head https://linuxize.com/


It's currently a flat list because we have one of each, and this can be adjusted as needed.
Each of these is considered one experiment. You should not include versions with the package
to be spliced, or the library to splice in, as they will be discovered programatically.
The above says:

| Take the binary 'curl' for the package curl, and replace the chosen version of zlib with all other versions of zlib.

You can also ask to splice in a totally different dependency:


.. code-block:: yaml

    package: hdf5
    splice: openmpi
    replace: mpich

The above says

| Take the hdf5 package, and replace openmpi with mpich.

When you don't include a "replace" field, the replacement library is implied to be the same as the spliced one.
To then run the workflow, simply input "curl.yaml" as the splice variable in the GitHub
workflow interface. If you don't include a command, then the splice and prediction can still happen,
but we don't have a good way to test if the binary still (minimally) runs.


Spliced Commands
================

Spliced provides the following commands via the ``spliced`` command line client.

Command
-------

Thus the first thing we might want to do is take a config YAML file, and see all the commands it can generate
for us.

.. code-block:: console

    $ spliced command examples/curl.yaml
    spliced splice --package curl@7.74.0 --splice zlib --runner spack --replace zlib --experiment curl curl --head https://linuxize.com/
    spliced splice --package curl@7.68.0 --splice zlib --runner spack --replace zlib --experiment curl curl --head https://linuxize.com/
    ...
    spliced splice --package curl@7.72.0 --splice zlib --runner spack --replace zlib --experiment curl curl --head https://linuxize.com/
    spliced splice --package curl@7.49.1 --splice zlib --runner spack --replace zlib --experiment curl curl --head https://linuxize.com/


It looks exactly as you'd expect - every version of curl with instruction to splice zlib (meaning different versions) and a command (the last part of the line)
to test. Given the expeiment runner is spack, spack will receive this request and handle install, etc. We could then try running one of those commands, discussed
next.


Splice
------

The most basic functionality is to perform a splice! You can either [generate a matrix](#splice-matrix) via a config file, 
provide the same config file to splice (appropriate for runners with custom variables to include like library paths)
or come up with your own.  Current runners supported include:

 - spack
 
And likely we will add a "manual" runner soon. 

Spack Splice
^^^^^^^^^^^^

Let's start with an example command that says:

| splice all versions of zlib to replace the current version of zlib in curl

.. code-block:: console
  
    $ spliced splice --package curl@7.50.2 --splice zlib --runner spack --replace zlib --experiment curl


Since we only have one runner (spack) that's currently the default, so this works too:


.. code-block:: console
    
    $ spliced splice --package curl@7.50.2 --splice zlib --replace zlib --experiment curl


Also if you are splicing the same library in (e.g., different versions) you can leave out replace:

.. code-block:: console

    $ spliced splice --package curl@7.50.2 --splice zlib --experiment curl


The experiment is just a named identifier, for your use (to store with the results). When you do this
you'll see:

1. Concretizing curl@7.50.2: the main package concretizing and installing. If either of these steps fails, you'll get a result object reporting the error.
2. Splicing (for each version of the dependency found) this can also have various points of failure, which are logged.
3. Running splice predictors (not developed yet) but will give a prediction if the splice will work!
4. Commands, if provided, are then run to give an "actual" report of if it worked (according to the command) or not.

By default, the predictors used will be all that are provided (libabigail and symbolator and an actual) and if
any predictor dependency is missing, a warning will be printed and it will be skipped. If you want to filter
to a specific number of predictors, use `--predictor` for each.


.. code-block:: console

    $ spliced splice --package curl@7.50.2 --splice zlib --experiment curl --predictor symbolator

The above would run the experiment with a symbolator prediction.
Note that the "actual" run is always performed if a command is provided, but not if it isn't. 
Here is what an entire run looks like, with a testing command and  output saved to a json file with `--outfile`

.. code-block:: console

    $ spliced splice --package curl@7.50.2 --splice zlib --runner spack --replace zlib --experiment curl --outfile examples/curl-result.json curl --head https://linuxize.com/
    Concretizing curl@7.50.2
    [+] /home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/berkeley-db-18.1.40-pdlzkb4o4qsw3nglppv7eqjm7lepqvod
    [+] /home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/libiconv-1.16-infpf4xwcb7253odbry6ljjcsat2ksp5
    [+] /home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/pkgconf-1.8.0-5bckkoeicca3dtolbeyz6tnnyxwcsfn5
    [+] /home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/zlib-1.2.11-3kmnsdv36qxm3slmcyrb326gkghsp6px
    [+] /home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/diffutils-3.8-ae4ve7adrxntd2kafm4xxmeyhrwpzpmg
    [+] /home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/ncurses-6.2-5bzr63iqgpogufanleaw2fzjxnzziz67
    [+] /home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/bzip2-1.0.8-doeyikigv6jk4dk6fdxm3cl5j7j465if
    [+] /home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/readline-8.1-wkga37hicua476jm2bjjmuzufz6h574j
    [+] /home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/gdbm-1.19-wuhyaf477mw6nmgftp3gvrxic7qzgpso
    [+] /home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/perl-5.34.0-bvgnm2ejnajpvaruta22d5c24g6qi4zu
    [+] /home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/openssl-1.1.1l-antishvjbtniecep64dku2cenh7hkonc
    [+] /home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/curl-7.50.2-a7ncgyeci2upn3vimpc62whvdkagihou
    Testing splicing in (and out) zlib@1.2.11
    [+] /home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/zlib-1.2.11-3kmnsdv36qxm3slmcyrb326gkghsp6px
    Testing splicing in (and out) zlib@1.2.8
    [+] /home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/zlib-1.2.8-mtdthhgpvdcqsfmbqzzvdlvain56j6th
    Testing splicing in (and out) zlib@1.2.3
    [+] /home/vanessa/Desktop/Code/spack-vsoch/opt/spack/linux-ubuntu20.04-skylake/gcc-9.3.0/zlib-1.2.3-mum2pz5di4xf4pjkyac3olgpnbrtpxph
    Making predictions for actual
    Making predictions for symbolator

Matrix
------

While you can perform a single splice manually, generally you'd want to instead create a matrix!
You can do this with the `splice matrix` command, which will output json that you can use in GitHub or other CI workflows.
The spliced format

.. code-block:: console
    
    $ spliced matrix examples/curl.yaml 


If you provide a custom container base, it will be included in the matrix and compilers discovered from it:


.. code-block:: console

    $ spliced matrix examples/curl.yaml --container ghcr.io/buildsi/spack-ubuntu-20.04


This will output a matrix of commands and other metadata that you can use in GitHub actions or your CI tool of choice. 


.. code-block:: console

    $ spliced matrix examples/sqlite.yaml 
    ::set-output name=containers::[{"command": "spliced splice --package sqlite@3.27.0 --splice zlib --replace zlib --experiment sqlite", "package": "sqlite@3.27.0", "splice": "zlib", "replace": "zlib", "experiment": "sqlite", "container": null}, {"command": "spliced splice --package sqlite@3.28.0 --splice zlib --replace zlib --experiment sqlite", "package": "sqlite@3.28.0", "splice": "zlib", "replace": "zlib", "experiment": "sqlite", "container": null}, {"command": "spliced splice --package sqlite@3.29.0 --splice zlib --replace zlib --experiment sqlite", "package": "sqlite@3.29.0", 
    ...
    "splice": "zlib", "replace": "zlib", "experiment": "sqlite", "container": null}, {"command": "spliced splice --package sqlite@3.30.0 --splice zlib --replace zlib --experiment sqlite", "package": "sqlite@3.30.0", "splice": "zlib", "replace": "zlib", "experiment": "sqlite", "container": null}, {"command": "spliced splice --package sqlite@3.27.2 --splice zlib --replace zlib --experiment sqlite", "package": "sqlite@3.27.2", "splice": "zlib", "replace": "zlib", "experiment": "sqlite", "container": null}, {"command": "spliced splice --package sqlite@3.35.5 --splice zlib --replace zlib --experiment sqlite", "package": "sqlite@3.35.5", "splice": "zlib", "replace": "zlib", "experiment": "sqlite", "container": null}]


If you want to limit the number of results (if versions exceed this it will randomly sample to the limit):

.. code-block:: console

    # 256 is the job limit for GitHub actions
    $ spliced matrix examples/curl.yaml --limit 256

    # An example to show much fewier
    $ spliced matrix examples/curl.yaml --limit 3
    Warning: original output is length 29 and limit is set to 3 jobs!
    ::set-output name=containers::[{"command": "spliced splice --package curl@7.71.0 --splice zlib --replace zlib --experiment curl", "package": "curl@7.71.0", "splice": "zlib", "replace": "zlib", "experiment": "curl", "container": null}, {"command": "spliced splice --package curl@7.49.1 --splice zlib --replace zlib --experiment curl", "package": "curl@7.49.1", "splice": "zlib", "replace": "zlib", "experiment": "curl", "container": null}, {"command": "spliced splice --package curl@7.59.0 --splice zlib --replace zlib --experiment curl", "package": "curl@7.59.0", "splice": "zlib", "replace": "zlib", "experiment": "curl", "container": null}]


Finally, you can save the result directly to output file (json) instead:

.. code-block:: console

    $ spliced matrix examples/curl.yaml --outfile examples/curl-matrix.json


Validate
--------

Once you have a result, you can use the ``validate`` command to ensure the format is correct.

.. code-block:: console

    $ spliced validate pkg-sqlite\@3.35.5-splice-zlib-with-zlib-experiment-sqlite-splices.json


GitHub Actions
==============

Spliced provides a set of GitHub actions that make it easy to run splice experiments on GitHub.
The current documentation for these is in the ``.github/workflows/test-action.yaml`` file, and we will
add more detail here when the action development is finished (or when it is requested, whichever comes first).

Artifacts
---------

The artifacts action will discover artifacts within some number of days, download them to a root (defaults to artifacts)
in the following structure:

.. code-block:: console

    artifacts
    
    # experiment name
    └── curl

        # package name
        └── curl

            # detail
            ├── curl-7.49.1-splice-zlib-with-zlib-experiment-curl
            │   └── splices.json
            ├── curl-7.50.1-splice-zlib-with-zlib-experiment-curl


It is assumed that files under the same experiment belong together. In the example above,
the experiment happens to be named similar to the package, but it doesn't have to be the case.
Since experiments are typically stored as yaml files in the same directory, you shouldn't have issue
managing this namespace unless you decide to redo an experiment with the same name. If you do this, you'll
need to manually delete the experiment folder if you want new results to be propogated.
