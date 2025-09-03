===============================
squirrel
===============================

.. image:: https://github.com/slaclab/squirrel/actions/workflows/standard.yml/badge.svg
        :target: https://github.com/slaclab/squirrel/actions/workflows/standard.yml

.. image:: https://img.shields.io/pypi/v/squirrel.svg
        :target: https://pypi.python.org/pypi/squirrel


`Documentation <https://slaclab.github.io/squirrel/>`_

Configuration Management for EPICS PVs

Requirements
------------

* Python 3.10+

Installation
------------

::

  $ conda create --name squirrel pip
  $ conda activate squirrel
  $
  $ conda install --file requirements.txt  # install statically, and only include packages necessary to run
  $ pip install .
  $ #or
  $ conda install --file requirements.txt --file dev-requirements.txt # include packages for development and testing
  $ pip install -e .  # install as editable package

Running the Tests
-----------------
::

  $ pytest
