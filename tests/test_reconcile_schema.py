import json

import httpx
import jsonschema
import pytest
from datasette.app import Datasette

from tests.fixtures import db_path, get_schema, plugin_metadata


@pytest.mark.asyncio
async def test_schema_manifest(db_path):
    schemas = get_schema("manifest.json")

    app = Datasette([db_path], metadata=plugin_metadata({"name_field": "name"})).app()
    async with httpx.AsyncClient(app=app) as client:
        response = await client.get("http://localhost/test/dogs/-/reconcile")
        data = response.json()
        for schema_version, schema in schemas.items():
            print("Schema version: {}".format(schema_version))
            jsonschema.validate(
                instance=data,
                schema=schema,
                cls=jsonschema.Draft7Validator,
            )


@pytest.mark.asyncio
async def test_response_queries_schema_post(db_path):
    schemas = get_schema("reconciliation-result-batch.json")
    app = Datasette([db_path], metadata=plugin_metadata({"name_field": "name"})).app()
    async with httpx.AsyncClient(app=app) as client:
        response = await client.post(
            "http://localhost/test/dogs/-/reconcile",
            data={"queries": json.dumps({"q0": {"query": "fido"}})},
        )
        assert 200 == response.status_code
        data = response.json()
        for schema_version, schema in schemas.items():
            print("Schema version: {}".format(schema_version))
            jsonschema.validate(
                instance=data,
                schema=schema,
                cls=jsonschema.Draft7Validator,
            )


@pytest.mark.asyncio
async def test_response_queries_schema_get(db_path):
    schemas = get_schema("reconciliation-result-batch.json")
    app = Datasette([db_path], metadata=plugin_metadata({"name_field": "name"})).app()
    async with httpx.AsyncClient(app=app) as client:
        queries = json.dumps({"q0": {"query": "fido"}})
        response = await client.get(
            "http://localhost/test/dogs/-/reconcile?queries={}".format(queries)
        )
        assert 200 == response.status_code
        data = response.json()
        for schema_version, schema in schemas.items():
            print("Schema version: {}".format(schema_version))
            jsonschema.validate(
                instance=data,
                schema=schema,
                cls=jsonschema.Draft7Validator,
            )
