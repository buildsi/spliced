.. _getting_started-installation:

============
Installation
============

Spliced can be installed from pypi, or from source. 

Note that `spack <https://github.com/spack/spack>`_ is required to be on your path
given that you are running a spack matrix build, and since splicing is required (which is
under development) you need to clone a branch from vsoch. 

.. code:: console

    $ git clone -b vsoch/db-17-splice --depth 1 https://github.com/vsoch/spack
    $ source spack/share/spack/setup-env.sh


Development Dependencies
========================

The smeagle predictor currently requires cle:

.. code:: console

    git clone https://github.com/vsoch/cle /tmp/cle
    cd /tmp/cle
    
    # archinfo, pyvex, pyelftools, then cle
    pip install wheel
    pip install git+https://github.com/angr/archinfo
    pip install git+https://github.com/angr/pyvex
    pip install git+https://github.com/eliben/pyelftools
    pip install .

Pypi
====

The module is available in pypi as `spliced <https://pypi.org/project/spliced/>`_.

.. code:: console

    $ pip install spliced

This will provide the latest release. If you want a branch or development version, you can install from GitHub, shown next.


Virtual Environment
===================

Here is how to clone the repository and do a local install.

.. code:: console

    $ git clone git@github.com:buildsi/spliced
    $ cd spliced

Create a virtual environment (recommended)

.. code:: console

    $ python -m venv env
    $ source env/bin/activate


And then install (this is development mode, remove the -e to not use it)

.. code:: console

    $ pip install -e .

Installation of spliced adds an executable, `spliced` to your path.

.. code:: console

    $ which spliced
    /opt/conda/bin/spliced


Once it's installed, you should be able to inspect the client!


.. code-block:: console

    $ spliced --help


You'll next want to configure and run experiments, discussed next in :ref:`getting-started`.
 
.. warning::

    If you are running spack experiments you will need spack on the path! Any other experiment technologies that you decide to use are also required.  


