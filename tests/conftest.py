import json
import os

import pytest
import sqlite_utils
from datasette.app import Datasette

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
