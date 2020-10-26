import html
import json
import sqlite3
import warnings

from datasette import hookimpl
from datasette.utils import escape_fts, escape_sqlite
from datasette.utils.asgi import Forbidden, NotFound, Response
from fuzzywuzzy import fuzz

DEFAULT_LIMIT = 5
DEFAULT_TYPE = "Object"


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
        config["type_default"] = DEFAULT_TYPE

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


async def reconcile(request, datasette):
    database = request.url_vars["db_name"]
    table = request.url_vars["db_table"]
    db = datasette.get_database(database)

    config = datasette.plugin_config(
        "datasette-reconcile", database=database, table=table
    )
    config = await check_config(config, db, table)

    await check_permissions(
        request,
        [
            ("view-table", (database, table)),
            ("view-database", database),
            "view-instance",
        ],
        datasette,
    )

    print(request.args)
    post_vars = await request.post_vars()
    queries = post_vars.get("queries", request.args.get("queries"))
    if queries:
        queries = json.loads(queries)
        return Response.json(
            {q[0]: q[1] async for q in reconcile_queries(queries, config, db, table)}
        )

    return Response.json(
        {
            "name": "VIAF",
            "identifierSpace": "http://vocab.getty.edu/doc/#GVP_URLs_and_Prefixes",
            "schemaSpace": "http://vocab.getty.edu/doc/#The_Getty_Vocabularies_and_LOD",
        }
    )


def get_select_fields(config):
    select_fields = [config["id_field"], config["name_field"]] + config.get(
        "additional_fields", []
    )
    if config.get("type_field"):
        select_fields.append(config["type_field"])
    return select_fields


async def reconcile_queries(queries, config, db, table):
    select_fields = get_select_fields(config)
    queries_results = {}
    for query_id, query in queries.items():
        limit = min(
            query.get("limit", config.get("max_limit", DEFAULT_LIMIT)),
            config.get("max_limit", DEFAULT_LIMIT),
        )

        where_clauses = ["1"]
        from_clause = escape_sqlite(table)
        order_by = ""
        params = {}
        if config["fts_table"]:
            # NB this will fail if the table name has non-alphanumeric
            # characters in and sqlite3 version < 3.30.0
            # see: https://www.sqlite.org/src/info/00e9a8f2730eb723
            from_clause = """
            {table} 
            inner join (
                    SELECT "rowid", "rank"
                    FROM {fts_table} 
                    WHERE {fts_table} MATCH :search_query
            ) as "a" on {table}."rowid" = a."rowid"
            """.format(
                table=escape_sqlite(table),
                fts_table=escape_sqlite(config["fts_table"]),
            )
            order_by = "order by a.rank"
            params["search_query"] = escape_fts(query["query"])
        else:
            where_clauses.append(
                "{search_col} like :search_query".format(
                    search_col=escape_sqlite(config["name_field"]),
                )
            )
            params["search_query"] = f"%{query['query']}%"

        query_sql = "select {select_fields} from {from_clause} where {where_clause} {order_by} limit {limit}".format(
            select_fields=",".join([escape_sqlite(f) for f in select_fields]),
            from_clause=from_clause,
            where_clause=" and ".join(where_clauses),
            order_by=order_by,
            limit=limit,
        )
        query_sql = " ".join([s.strip() for s in query_sql.splitlines()])
        query_results = [
            {
                "id": r[config["id_field"]],
                "name": r[config["name_field"]],
                "type": r[config["type_field"]]
                if config.get("type_field") and config["type_field"] in r
                else config["type_default"],
                "score": fuzz.ratio(
                    str(r[config["name_field"]]).lower(), str(query["query"]).lower()
                ),
                "match": query["query"].lower().strip()
                == config["name_field"].lower().strip(),
            }
            for r in await db.execute(query_sql, params)
        ]
        query_results = sorted(query_results, key=lambda x: -x["score"])
        yield query_id, query_results


@hookimpl
def register_routes():
    return [(r"/(?P<db_name>[^/]+)/(?P<db_table>[^/]+?)/reconcile$", reconcile)]
