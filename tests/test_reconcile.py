import json

import httpx
import pytest
from datasette.app import Datasette

from tests.fixtures import db_path, plugin_metadata


@pytest.mark.asyncio
async def test_plugin_is_installed():
    app = Datasette([], memory=True).app()
    async with httpx.AsyncClient(app=app) as client:
        response = await client.get("http://localhost/-/plugins.json")
        assert 200 == response.status_code
        installed_plugins = {p["name"] for p in response.json()}
        assert "datasette-reconcile" in installed_plugins


@pytest.mark.asyncio
async def test_response_not_configured(db_path):
    app = Datasette([db_path]).app()
    async with httpx.AsyncClient(app=app) as client:
        response = await client.get("http://localhost/test/dogs/-/reconcile")
        assert 404 == response.status_code


@pytest.mark.asyncio
async def test_response_without_query(db_path):
    app = Datasette([db_path], metadata=plugin_metadata({"name_field": "name"})).app()
    async with httpx.AsyncClient(app=app) as client:
        response = await client.get("http://localhost/test/dogs/-/reconcile")
        assert 200 == response.status_code
        data = response.json()
        assert "name" in data.keys()
        assert response.headers["Access-Control-Allow-Origin"] == "*"


@pytest.mark.asyncio
async def test_response_queries_post(db_path):
    app = Datasette([db_path], metadata=plugin_metadata({"name_field": "name"})).app()
    async with httpx.AsyncClient(app=app) as client:
        response = await client.post(
            "http://localhost/test/dogs/-/reconcile",
            data={"queries": json.dumps({"q0": {"query": "fido"}})},
        )
        assert 200 == response.status_code
        data = response.json()
        assert "q0" in data.keys()
        assert len(data["q0"]) == 1
        result = data["q0"][0]
        assert result["id"] == 3
        assert result["name"] == "Fido"
        assert result["score"] == 100
        assert response.headers["Access-Control-Allow-Origin"] == "*"


@pytest.mark.asyncio
async def test_response_queries_get(db_path):
    app = Datasette([db_path], metadata=plugin_metadata({"name_field": "name"})).app()
    async with httpx.AsyncClient(app=app) as client:
        queries = json.dumps({"q0": {"query": "fido"}})
        response = await client.get(
            "http://localhost/test/dogs/-/reconcile?queries={}".format(queries)
        )
        assert 200 == response.status_code
        data = response.json()
        assert "q0" in data.keys()
        assert len(data["q0"]) == 1
        result = data["q0"][0]
        assert result["id"] == 3
        assert result["name"] == "Fido"
        assert result["score"] == 100
        assert response.headers["Access-Control-Allow-Origin"] == "*"
