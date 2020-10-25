from datasette.app import Datasette
import pytest
import httpx
import sqlite_utils

from datasette_reconcile import check_config, ReconcileError

@pytest.fixture(scope="session")
def ds(tmp_path_factory):
    db_directory = tmp_path_factory.mktemp("dbs")
    db_path = db_directory / "test.db"
    db = sqlite_utils.Database(db_path)
    db["dogs"].insert_all([
        {"id": 1, "name": "Cleo", "age": 5, "status": "good dog"},
        {"id": 2, "name": "Pancakes", "age": 4, "status": "bad dog"},
        {"id": 3, "name": "Fido", "age": 3, "status": "bad dog"},
        {"id": 4, "name": "Scratch", "age": 3, "status": "good dog"},
    ], pk="id")
    ds = Datasette(
        [db_path],
        metadata={
            "databases": {
                "test": {
                    "tables": {
                        "dogs": {
                            "title": "Some dogs"
                        }
                    }
                }
            }
        }
    )
    return ds


@pytest.mark.asyncio
async def test_plugin_is_installed():
    app = Datasette([], memory=True).app()
    async with httpx.AsyncClient(app=app) as client:
        response = await client.get("http://localhost/-/plugins.json")
        assert 200 == response.status_code
        installed_plugins = {p["name"] for p in response.json()}
        assert "datasette-reconcile" in installed_plugins


@pytest.mark.asyncio
async def test_plugin_configuration_missing(ds):
    with pytest.raises(ReconcileError, match="datasette-reconcile not configured .*"):
        config = await check_config({}, ds.get_database('test'), 'dogs')


@pytest.mark.asyncio
async def test_plugin_configuration_no_name(ds):
    with pytest.raises(ReconcileError, match="Name field must be defined to activate reconciliation"):
        config = await check_config({
            'id_field': 'id'
        }, ds.get_database('test'), 'dogs')


@pytest.mark.asyncio
async def test_plugin_configuration_table_not_found(ds):
    with pytest.raises(ReconcileError, match="Table not found: test"):
        config = await check_config({
            'name_field': 'name'
        }, ds.get_database('test'), 'test')


@pytest.mark.asyncio
async def test_plugin_configuration_use_pk(ds):
    config = await check_config({
        'name_field': 'name'
    }, ds.get_database('test'), 'dogs')
    assert config['name_field'] == 'name'
    assert config['id_field'] == 'id'
    assert config['type_default'] == 'Object'
    assert "type_field" not in config


@pytest.mark.asyncio
async def test_plugin_configuration_use_id_field(ds):
    config = await check_config({
        'name_field': 'name',
        'id_field': 'id',
    }, ds.get_database('test'), 'dogs')
    assert config['name_field'] == 'name'
    assert config['id_field'] == 'id'
    assert config['type_default'] == 'Object'
    assert "type_field" not in config


@pytest.mark.asyncio
async def test_plugin_configuration_use_type_field(ds):
    config = await check_config({
        'name_field': 'name',
        'id_field': 'id',
        'type_field': 'status',
    }, ds.get_database('test'), 'dogs')
    assert config['name_field'] == 'name'
    assert config['id_field'] == 'id'
    assert config['type_field'] == 'status'
    assert 'type_default' not in config


@pytest.mark.asyncio
async def test_plugin_configuration_use_type_default(ds):
    config = await check_config({
        'name_field': 'name',
        'id_field': 'id',
        'type_default': 'dog',
    }, ds.get_database('test'), 'dogs')
    assert config['name_field'] == 'name'
    assert config['id_field'] == 'id'
    assert config['type_default'] == 'dog'
    assert 'type_field' not in config


@pytest.mark.asyncio
async def test_plugin_configuration_use_fts_table(ds):
    config = await check_config({
        'name_field': 'name',
        'id_field': 'id',
        'type_default': 'dog',
    }, ds.get_database('test'), 'dogs')
    assert config['fts_table'] is None
