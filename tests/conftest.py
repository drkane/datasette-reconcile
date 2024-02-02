import json
import os
import re

import pytest
import sqlite_utils
from datasette.app import Datasette
from referencing import Registry
from referencing.jsonschema import DRAFT7

from datasette_reconcile.settings import SUPPORTED_API_VERSIONS

SCHEMA_DIR = os.path.join(
    os.path.dirname(__file__),
    "../specs",
)


def create_db(tmp_path_factory):
    db_directory = tmp_path_factory.mktemp("dbs")
    db_path = db_directory / "test.db"
    db = sqlite_utils.Database(db_path)
    db["dogs"].insert_all(
        [
            {"id": 1, "name": "Cleo", "age": 5, "status": "good dog"},
            {"id": 2, "name": "Pancakes", "age": 4, "status": "bad dog"},
            {"id": 3, "name": "Fido", "age": 3, "status": "bad dog"},
            {"id": 4, "name": "Scratch", "age": 3, "status": "good dog"},
        ],
        pk="id",
    )
    return db_path


def plugin_metadata(metadata=None):
    to_return = {"databases": {"test": {"tables": {"dogs": {"title": "Some dogs"}}}}}
    if isinstance(metadata, dict):
        to_return["databases"]["test"]["tables"]["dogs"]["plugins"] = {"datasette-reconcile": metadata}
    return to_return


def get_schema(filename):
    schemas = {}
    for f in os.scandir(SCHEMA_DIR):
        if not f.is_dir():
            continue
        if f.name not in SUPPORTED_API_VERSIONS:
            continue
        schema_path = os.path.join(f.path, "schemas", filename)
        if os.path.exists(schema_path):
            with open(schema_path, encoding="utf8") as schema_file:
                schemas[f.name] = json.load(schema_file)
    return schemas


@pytest.fixture(scope="session")
def ds(tmp_path_factory):
    ds = Datasette([create_db(tmp_path_factory)], metadata=plugin_metadata())
    return ds


@pytest.fixture(scope="session")
def db_path(tmp_path_factory):
    return create_db(tmp_path_factory)


def retrieve_schema_from_filesystem(uri: str):
    recon_schema = re.match(
        r"https://reconciliation-api\.github\.io/specs/(.*)/schemas/(.*\.json)",
        uri,
    )
    if recon_schema:
        schema_version = recon_schema.group(1)
        schema_file = recon_schema.group(2)
        return DRAFT7.create_resource(get_schema(schema_file)[schema_version])

    msg = f"Unknown URI {uri}"
    raise ValueError(msg)


registry = Registry(retrieve=retrieve_schema_from_filesystem)
