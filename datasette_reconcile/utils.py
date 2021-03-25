import sqlite3
import warnings

from datasette.utils.asgi import Forbidden, NotFound, Response

from datasette_reconcile.settings import DEFAULT_TYPE


class ReconcileError(Exception):
    pass


async def check_permissions(request, permissions, ds):
    "permissions is a list of (action, resource) tuples or 'action' strings"
    "from https://github.com/simonw/datasette/blob/main/datasette/views/base.py#L69"
    for permission in permissions:
        if isinstance(permission, str):
            action = permission
            resource = None
        elif isinstance(permission, (tuple, list)) and len(permission) == 2:
            action, resource = permission
        else:
            assert (
                False
            ), "permission should be string or tuple of two items: {}".format(
                repr(permission)
            )
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
        raise NotFound("Table not found: {}".format(table))

    if not config:
        raise NotFound(
            "datasette-reconcile not configured for table {} in database {}".format(
                table, str(db)
            )
        )

    pks = await db.primary_keys(table)
    if not pks:
        pks = ["rowid"]

    if "id_field" not in config and len(pks) == 1:
        config["id_field"] = pks[0]
    elif "id_field" not in config:
        raise ReconcileError("Could not determine an ID field to use")
    if "name_field" not in config:
        raise ReconcileError("Name field must be defined to activate reconciliation")
    if "type_field" not in config and "type_default" not in config:
        config["type_default"] = [DEFAULT_TYPE]
    if "max_limit" in config and not isinstance(config["max_limit"], int):
        raise TypeError("max_limit in reconciliation config must be an integer")
    if "type_default" in config:
        if not isinstance(config["type_default"], list):
            raise ReconcileError("type_default should be a list of objects")
        for t in config["type_default"]:
            if not isinstance(t, dict):
                raise ReconcileError("type_default values should be objects")
            if not isinstance(t.get("id"), str):
                raise ReconcileError("type_default 'id' values should be strings")
            if not isinstance(t.get("name"), str):
                raise ReconcileError("type_default 'name' values should be strings")

    config["fts_table"] = await db.fts_table(table)

    # let's show a warning if sqlite3 version is less than 3.30.0
    # full text search results will fail for < 3.30.0 if the table
    # name contains special characters
    if config["fts_table"] and (
        (sqlite3.sqlite_version_info[0] == 3 and sqlite3.sqlite_version_info[1] < 30)
        or sqlite3.sqlite_version_info[0] < 3
    ):
        warnings.warn(
            "Full Text Search queries for sqlite3 version < 3.30.0 wil fail if table name contains special characters"
        )

    return config


def get_select_fields(config):
    select_fields = [config["id_field"], config["name_field"]] + config.get(
        "additional_fields", []
    )
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
        return "{}{}-{}/{}/{}".format(
            base_url, database, db.hash[:HASH_LENGTH], table, id_str
        )
    else:
        return "{}{}/{}/{}".format(base_url, database, table, id_str)
