import json
import logging

import httpx
import jsonschema
import pytest
from datasette.app import Datasette

from tests.conftest import get_schema, plugin_metadata, registry

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.parametrize("schema_version, schema", get_schema("manifest.json").items())
async def test_schema_manifest(schema_version, schema, db_path):
    app = Datasette([db_path], metadata=plugin_metadata({"name_field": "name"})).app()
    async with httpx.AsyncClient(app=app) as client:
        response = await client.get("http://localhost/test/dogs/-/reconcile")
        data = response.json()
        logging.info(f"Schema version: {schema_version}")
        jsonschema.validate(
            instance=data,
            schema=schema,
            cls=jsonschema.Draft7Validator,
            registry=registry,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("schema_version, schema", get_schema("manifest.json").items())
async def test_schema_manifest_extend(schema_version, schema, db_path):
    app = Datasette(
        [db_path],
        metadata=plugin_metadata(
            {"name_field": "name", "properties": [{"name": "status", "label": "Status", "type": "text"}]}
        ),
    ).app()
    async with httpx.AsyncClient(app=app) as client:
        response = await client.get("http://localhost/test/dogs/-/reconcile")
        data = response.json()
        logging.info(f"Schema version: {schema_version}")
        jsonschema.validate(
            instance=data,
            schema=schema,
            cls=jsonschema.Draft7Validator,
            registry=registry,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("schema_version, schema", get_schema("reconciliation-result-batch.json").items())
async def test_response_queries_schema_post(schema_version, schema, db_path):
    app = Datasette([db_path], metadata=plugin_metadata({"name_field": "name"})).app()
    async with httpx.AsyncClient(app=app) as client:
        response = await client.post(
            "http://localhost/test/dogs/-/reconcile",
            data={"queries": json.dumps({"q0": {"query": "fido"}})},
        )
        assert 200 == response.status_code
        data = response.json()
        logging.info(f"Schema version: {schema_version}")
        jsonschema.validate(
            instance=data,
            schema=schema,
            cls=jsonschema.Draft7Validator,
            registry=registry,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("schema_version, schema", get_schema("reconciliation-result-batch.json").items())
async def test_response_queries_schema_get(schema_version, schema, db_path):
    app = Datasette([db_path], metadata=plugin_metadata({"name_field": "name"})).app()
    async with httpx.AsyncClient(app=app) as client:
        queries = json.dumps({"q0": {"query": "fido"}})
        response = await client.get(f"http://localhost/test/dogs/-/reconcile?queries={queries}")
        assert 200 == response.status_code
        data = response.json()
        logging.info(f"Schema version: {schema_version}")
        jsonschema.validate(
            instance=data,
            schema=schema,
            cls=jsonschema.Draft7Validator,
            registry=registry,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("schema_version, schema", get_schema("reconciliation-result-batch.json").items())
async def test_response_queries_no_results_schema_post(schema_version, schema, db_path):
    app = Datasette([db_path], metadata=plugin_metadata({"name_field": "name"})).app()
    async with httpx.AsyncClient(app=app) as client:
        response = await client.post(
            "http://localhost/test/dogs/-/reconcile",
            data={"queries": json.dumps({"q0": {"query": "abcdef"}})},
        )
        assert 200 == response.status_code
        data = response.json()
        logging.info(f"Schema version: {schema_version}")
        jsonschema.validate(
            instance=data,
            schema=schema,
            cls=jsonschema.Draft7Validator,
            registry=registry,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("schema_version, schema", get_schema("reconciliation-result-batch.json").items())
async def test_response_queries_no_results_schema_get(schema_version, schema, db_path):
    app = Datasette([db_path], metadata=plugin_metadata({"name_field": "name"})).app()
    async with httpx.AsyncClient(app=app) as client:
        queries = json.dumps({"q0": {"query": "abcdef"}})
        response = await client.get(f"http://localhost/test/dogs/-/reconcile?queries={queries}")
        assert 200 == response.status_code
        data = response.json()
        logging.info(f"Schema version: {schema_version}")
        jsonschema.validate(
            instance=data,
            schema=schema,
            cls=jsonschema.Draft7Validator,
            registry=registry,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("schema_version, schema", get_schema("data-extension-response.json").items())
async def test_extend_schema_post(schema_version, schema, db_path):
    app = Datasette([db_path], metadata=plugin_metadata({"name_field": "name"})).app()
    async with httpx.AsyncClient(app=app) as client:
        extend = {"extend": json.dumps({"ids": ["1", "2", "3", "4"], "properties": [{"id": "status"}, {"id": "age"}]})}
        response = await client.post("http://localhost/test/dogs/-/reconcile", data=extend)
        assert 200 == response.status_code
        data = response.json()
        logging.info(f"Schema version: {schema_version}")
        jsonschema.validate(
            instance=data,
            schema=schema,
            cls=jsonschema.Draft7Validator,
            registry=registry,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("schema_version, schema", get_schema("suggest-properties-response.json").items())
async def test_suggest_property_schema(schema_version, schema, db_path):
    app = Datasette([db_path], metadata=plugin_metadata({"name_field": "name"})).app()
    async with httpx.AsyncClient(app=app) as client:
        response = await client.get("http://localhost/test/dogs/-/reconcile/suggest/property?prefix=a")
        assert 200 == response.status_code
        data = response.json()
        logging.info(f"Schema version: {schema_version}")
        jsonschema.validate(
            instance=data,
            schema=schema,
            cls=jsonschema.Draft7Validator,
            registry=registry,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("schema_version, schema", get_schema("suggest-entities-response.json").items())
async def test_suggest_entity_schema(schema_version, schema, db_path):
    app = Datasette([db_path], metadata=plugin_metadata({"name_field": "name"})).app()
    async with httpx.AsyncClient(app=app) as client:
        response = await client.get("http://localhost/test/dogs/-/reconcile/suggest/entity?prefix=a")
        assert 200 == response.status_code
        data = response.json()
        logging.info(f"Schema version: {schema_version}")
        jsonschema.validate(
            instance=data,
            schema=schema,
            cls=jsonschema.Draft7Validator,
            registry=registry,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("schema_version, schema", get_schema("suggest-types-response.json").items())
async def test_suggest_type_schema(schema_version, schema, db_path):
    app = Datasette([db_path], metadata=plugin_metadata({"name_field": "name"})).app()
    async with httpx.AsyncClient(app=app) as client:
        response = await client.get("http://localhost/test/dogs/-/reconcile/suggest/type?prefix=a")
        assert 200 == response.status_code
        data = response.json()
        logging.info(f"Schema version: {schema_version}")
        jsonschema.validate(
            instance=data,
            schema=schema,
            cls=jsonschema.Draft7Validator,
            registry=registry,
        )
