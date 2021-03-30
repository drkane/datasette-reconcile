import os

from setuptools import setup

VERSION = "0.2.1"


"""
python setup.py sdist bdist_wheel
python -m twine upload dist/*
"""


def get_long_description():
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md"),
        encoding="utf8",
    ) as fp:
        return fp.read()


setup(
    name="datasette-reconcile",
    description="Adds a reconciliation API to Datasette.",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="David Kane",
    author_email="david@dkane.net",
    url="https://github.com/drkane/datasette-reconcile",
    project_urls={
        "Issues": "https://github.com/drkane/datasette-reconcile/issues",
        "CI": "https://github.com/drkane/datasette-reconcile/actions",
        "Changelog": "https://github.com/drkane/datasette-reconcile/releases",
    },
    license="Apache License, Version 2.0",
    version=VERSION,
    packages=["datasette_reconcile"],
    entry_points={"datasette": ["reconcile = datasette_reconcile"]},
    install_requires=["datasette", "fuzzywuzzy[speedup]"],
    extras_require={
        "test": [
            "pytest",
            "pytest-asyncio",
            "httpx",
            "sqlite-utils",
            "black",
            "isort",
            "jsonschema",
        ]
    },
    tests_require=["datasette-reconcile[test]"],
    python_requires=">=3.6",
)
