import sqlite3
import warnings

from datasette.utils import HASH_LENGTH
from datasette.utils.asgi import Forbidden, NotFound

from datasette_reconcile.settings import DEFAULT_TYPE, SQLITE_VERSION_WARNING

PERMISSION_TUPLE_SIZE = 2


class ReconcileError(Exception):
    pass


async def check_permissions(request, permissions, ds):
    "permissions is a list of (action, resource) tuples or 'action' strings"
    "from https://github.com/simonw/datasette/blob/main/datasette/views/base.py#L69"
    for permission in permissions:
        if isinstance(permission, str):
            action = permission
            resource = None
        elif isinstance(permission, (tuple, list)) and len(permission) == PERMISSION_TUPLE_SIZE:
            action, resource = permission
        else:
            msg = f"permission should be string or tuple of two items: {permission!r}"
            raise AssertionError(msg)
        ok = await ds.permission_allowed(
            request.actor,
            action,
            resource=resource,
            default=None,
        )
        if ok is not None:
            if ok:
                return
            else:
                raise Forbidden(action)


async def check_config(config, db, table):
    is_view = bool(await db.get_view_definition(table))
    table_exists = bool(await db.table_exists(table))
    if not is_view and not table_exists:
        msg = f"Table not found: {table}"
        raise NotFound(msg)

    if not config:
        msg = f"datasette-reconcile not configured for table {table} in database {db!s}"
        raise NotFound(msg)

    pks = await db.primary_keys(table)
    if not pks:
        pks = ["rowid"]

    if "id_field" not in config and len(pks) == 1:
        config["id_field"] = pks[0]
    elif "id_field" not in config:
        msg = "Could not determine an ID field to use"
        raise ReconcileError(msg)
    if "name_field" not in config:
        msg = "Name field must be defined to activate reconciliation"
        raise ReconcileError(msg)
    if "type_field" not in config and "type_default" not in config:
        config["type_default"] = [DEFAULT_TYPE]
    if "max_limit" in config and not isinstance(config["max_limit"], int):
        msg = "max_limit in reconciliation config must be an integer"
        raise TypeError(msg)
    if "type_default" in config:
        if not isinstance(config["type_default"], list):
            msg = "type_default should be a list of objects"
            raise ReconcileError(msg)
        for t in config["type_default"]:
            if not isinstance(t, dict):
                msg = "type_default values should be objects"
                raise ReconcileError(msg)
            if not isinstance(t.get("id"), str):
                msg = "type_default 'id' values should be strings"
                raise ReconcileError(msg)
            if not isinstance(t.get("name"), str):
                msg = "type_default 'name' values should be strings"
                raise ReconcileError(msg)

    config["fts_table"] = await db.fts_table(table)

    # let's show a warning if sqlite3 version is less than 3.30.0
    # full text search results will fail for < 3.30.0 if the table
    # name contains special characters
    if config["fts_table"] and (
        (
            sqlite3.sqlite_version_info[0] == SQLITE_VERSION_WARNING[0]
            and sqlite3.sqlite_version_info[1] < SQLITE_VERSION_WARNING[1]
        )
        or sqlite3.sqlite_version_info[0] < SQLITE_VERSION_WARNING[0]
    ):
        warnings.warn(
            "Full Text Search queries for sqlite3 version < 3.30.0 wil fail if table name contains special characters",
            stacklevel=2,
        )

    return config


def get_select_fields(config):
    select_fields = [config["id_field"], config["name_field"], *config.get("additional_fields", [])]
    if config.get("type_field"):
        select_fields.append(config["type_field"])
    return select_fields


def get_view_url(ds, database, table):
    id_str = "{{id}}"
    if hasattr(ds, "urls"):
        return ds.urls.row(database, table, id_str)
    db = ds.databases[database]
    base_url = ds.config("base_url")
    if ds.config("hash_urls") and db.hash:
        return f"{base_url}{database}-{db.hash[:HASH_LENGTH]}/{table}/{id_str}"
    else:
        return f"{base_url}{database}/{table}/{id_str}"
