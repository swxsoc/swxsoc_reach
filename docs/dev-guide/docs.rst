.. _docs_guidelines:

*******************
Documentation Rules
*******************

Overview
========

All code must be documented and we follow the style conventions described here:

* `numpydoc <https://numpydoc.readthedocs.io/en/latest/format.html#docstring-standard>`_

Referring to other code
-----------------------

To link to methods, classes, or modules in your repo you have to use backticks, for example:

.. code-block:: rst

    `swxsoc_reach.io.read_file()`

generates a link like this: `swxsoc_reach.io.read_file()`.

Links can also be generated to external packages via
`intersphinx <http://www.sphinx-doc.org/en/master/ext/intersphinx.html>`_:

.. code-block:: rst

    `numpy.mean`

will return this link: `numpy.mean`.
This works for Python, Numpy and Astropy (full list is in :file:`docs/conf.py`).

With Sphinx, if you use ``:func:`` or ``:meth:``, it will add closing brackets to the link.
If you get the wrong pre-qualifier, it will break the link, so we suggest that you double check if what you are linking is a method or a function.

.. code-block:: rst

    :class:`numpy.mean()`
    :meth:`numpy.mean()`
    :func:`numpy.mean()`

will return two broken links ("class" and "meth") but "func" will work.

Project-specific Rules
----------------------

* For **all** RST files, we enforce a one sentence per line rule and ignore the line length.


Sphinx
======

All of the documentation (like this page) is built by `Sphinx <https://www.sphinx-doc.org/en/stable/>`_, which is a tool especially well-suited for documenting Python projects.
Sphinx works by parsing files written using a `a Mediawiki-like syntax <http://docutils.sourceforge.net/docs/user/rst/quickstart.html>`_ called `reStructuredText <http://docutils.sourceforge.net/rst.html>`_.
It can also parse markdown files.
In addition to parsing static files of reStructuredText, Sphinx can also be told to parse code comments.
In fact, in addition to what you are reading right now, the `Python documentation <https://www.python.org/doc/>`_ was also created using Sphinx.

Usage and Building the documentation
------------------------------------

All of the documentation is contained in the "docs" folder and code documentation strings.
Sphinx builds documentation iteratively, only adding things that have changed.
For more information on how to use Sphinx, consult the `Sphinx documentation <http://www.sphinx-doc.org/en/stable/contents.html>`_.

HTML
^^^^

To build the html documentation locally use the following command, in the docs directory run::

    $ make html

If you use conda and have multiple Sphinx installations (for example Homebrew and a conda environment), build docs from the project environment so the correct Sphinx is used::

    $ conda run -n reach make -C docs html

Or activate the environment first and then run ``make html`` from ``docs/``.

This will generate HTML documentation in the "docs/_build/html" directory.
You can open the "index.html" file to browse the final product.

Rebuilding from scratch
^^^^^^^^^^^^^^^^^^^^^^^

Sphinx builds incrementally, so a full rebuild is rarely needed.
If you encounter stale output or unexplained errors, wipe all generated files and rebuild in one step::

    $ conda run -n reach make -C docs clean html

Or, if the environment is already active, from the ``docs/`` directory::

    $ make clean html

This deletes ``_build/`` and the ``_autosummary/`` directory before regenerating everything from source.

Sphinx can also build documentation as a PDF but this requires latex to be installed.