.. _manual-main:

=======
Spliced
=======

.. image:: https://img.shields.io/github/stars/buildsi/spliced?style=social
    :alt: GitHub stars
    :target: https://github.com/buildsi/spliced/stargazers


Spliced is software for performing or emulating splices, meaning subbing in one version of a library
for another, and predicting (through many avenues) whether it will work or not. A few concepts of
interest:

 - A **package** is a primarily library that we want to cut (or splice) up.
 - A **spliced out** library is a dependency or linked library that we are removing.
 - A **spliced in** library is a dependency or linked library that we want to sub in.


This is primarily a research library, so you likely want to use splice if you are interested
in running some kind of experiment to determine if splicing in a dependency for another
will work.

To see the code, head over to the `repository <https://github.com/buildsi/spliced/>`_.

.. _main-getting-started:

----------------------------
Getting started with Spliced
----------------------------

Spliced can be installed from pypi or directly from the repository. See :ref:`getting_started-installation` for
installation, and then the :ref:`getting-started` section for using spliced on the command line.

.. _main-support:

-------
Support
-------

* For **bugs and feature requests**, please use the `issue tracker <https://github.com/buildsi/spliced/issues>`_.
* For **contributions**, visit Spliced on `Github <https://github.com/buildsi/spliced>`_.

---------
Resources
---------

`GitHub Repository <https://github.com/buildsi/spliced>`_
    The code on GitHub.


.. toctree::
   :caption: Getting started
   :name: getting_started
   :hidden:
   :maxdepth: 2

   getting_started/index
   getting_started/user-guide
   getting_started/developer-guide

.. toctree::
    :caption: API Reference
    :name: api-reference
    :hidden:
    :maxdepth: 1

    api_reference/spliced
    api_reference/internal/modules
