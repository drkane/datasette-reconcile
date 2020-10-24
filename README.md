# datasette-reconcile

[![PyPI](https://img.shields.io/pypi/v/datasette-reconcile.svg)](https://pypi.org/project/datasette-reconcile/)
[![Changelog](https://img.shields.io/github/v/release/drkane/datasette-reconcile?include_prereleases&label=changelog)](https://github.com/drkane/datasette-reconcile/releases)
[![Tests](https://github.com/drkane/datasette-reconcile/workflows/Test/badge.svg)](https://github.com/drkane/datasette-reconcile/actions?query=workflow%3ATest)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/drkane/datasette-reconcile/blob/main/LICENSE)

Adds a reconciliation API to Datasette.

## Installation

Install this plugin in the same environment as Datasette.

    $ datasette install datasette-reconcile

## Usage

Usage instructions go here.

## Development

To set up this plugin locally, first checkout the code. Then create a new virtual environment:

    cd datasette-reconcile
    python3 -mvenv venv
    source venv/bin/activate

Or if you are using `pipenv`:

    pipenv shell

Now install the dependencies and tests:

    pip install -e '.[test]'

To run the tests:

    pytest
