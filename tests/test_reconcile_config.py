import httpx
import pytest
import sqlite_utils
from datasette.app import Datasette
from datasette.utils.asgi import NotFound

from datasette_reconcile.utils import ReconcileError, check_config
from tests.fixtures import ds


@pytest.mark.asyncio
async def test_plugin_configuration_missing(ds):
    with pytest.raises(NotFound, match="datasette-reconcile not configured .*"):
        config = await check_config({}, ds.get_database("test"), "dogs")


@pytest.mark.asyncio
async def test_plugin_configuration_no_name(ds):
    with pytest.raises(
        ReconcileError, match="Name field must be defined to activate reconciliation"
    ):
        config = await check_config({"id_field": "id"}, ds.get_database("test"), "dogs")


@pytest.mark.asyncio
async def test_plugin_configuration_table_not_found(ds):
    with pytest.raises(NotFound, match="Table not found: test"):
        config = await check_config(
            {"name_field": "name"}, ds.get_database("test"), "test"
        )


@pytest.mark.asyncio
async def test_plugin_configuration_use_pk(ds):
    config = await check_config({"name_field": "name"}, ds.get_database("test"), "dogs")
    assert config["name_field"] == "name"
    assert config["id_field"] == "id"
    assert config["type_default"] == [
        {
            "name": "Object",
            "id": "object",
        }
    ]
    assert "type_field" not in config


@pytest.mark.asyncio
async def test_plugin_configuration_use_id_field(ds):
    config = await check_config(
        {
            "name_field": "name",
            "id_field": "id",
        },
        ds.get_database("test"),
        "dogs",
    )
    assert config["name_field"] == "name"
    assert config["id_field"] == "id"
    assert config["type_default"] == [
        {
            "name": "Object",
            "id": "object",
        }
    ]
    assert "type_field" not in config


@pytest.mark.asyncio
async def test_plugin_configuration_use_type_field(ds):
    config = await check_config(
        {
            "name_field": "name",
            "id_field": "id",
            "type_field": [
                {
                    "name": "Status",
                    "id": "status",
                }
            ],
        },
        ds.get_database("test"),
        "dogs",
    )
    assert config["name_field"] == "name"
    assert config["id_field"] == "id"
    assert config["type_field"] == [
        {
            "name": "Status",
            "id": "status",
        }
    ]
    assert "type_default" not in config


@pytest.mark.asyncio
async def test_plugin_configuration_use_type_default_incorrect(ds):
    with pytest.raises(ReconcileError, match="type_default should"):
        config = await check_config(
            {
                "name_field": "name",
                "id_field": "id",
                "type_default": "dog",
            },
            ds.get_database("test"),
            "dogs",
        )


@pytest.mark.asyncio
async def test_plugin_configuration_use_type_default(ds):
    config = await check_config(
        {
            "name_field": "name",
            "id_field": "id",
            "type_default": [
                {
                    "name": "Dog",
                    "id": "dog",
                }
            ],
        },
        ds.get_database("test"),
        "dogs",
    )
    assert config["name_field"] == "name"
    assert config["id_field"] == "id"
    assert config["type_default"] == [
        {
            "name": "Dog",
            "id": "dog",
        }
    ]
    assert "type_field" not in config


@pytest.mark.asyncio
async def test_plugin_configuration_use_fts_table(ds):
    config = await check_config(
        {
            "name_field": "name",
            "id_field": "id",
            "type_default": [
                {
                    "name": "Dog",
                    "id": "dog",
                }
            ],
        },
        ds.get_database("test"),
        "dogs",
    )
    assert config["fts_table"] is None
