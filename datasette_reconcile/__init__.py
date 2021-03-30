import html
import json
import sqlite3
import warnings

from datasette import hookimpl
from datasette.utils.asgi import Response

from datasette_reconcile.reconcile import reconcile_queries, service_manifest
from datasette_reconcile.utils import check_config, check_permissions


async def reconcile(request, datasette):
    database = request.url_vars["db_name"]
    table = request.url_vars["db_table"]
    db = datasette.get_database(database)

    # get plugin configuration
    config = datasette.plugin_config(
        "datasette-reconcile", database=database, table=table
    )
    config = await check_config(config, db, table)

    # check user can at least view this table
    await check_permissions(
        request,
        [
            ("view-table", (database, table)),
            ("view-database", database),
            "view-instance",
        ],
        datasette,
    )

    # work out if we are looking for queries
    post_vars = await request.post_vars()
    queries = post_vars.get("queries", request.args.get("queries"))
    if queries:
        queries = json.loads(queries)
        return Response.json(
            {
                q[0]: {"result": q[1]}
                async for q in reconcile_queries(queries, config, db, table)
            },
            headers={
                "Access-Control-Allow-Origin": "*",
            },
        )

    # if we're not then just return the service specification
    return Response.json(
        service_manifest(config, database, table, datasette, request),
        headers={
            "Access-Control-Allow-Origin": "*",
        },
    )


@hookimpl
def register_routes():
    return [(r"/(?P<db_name>[^/]+)/(?P<db_table>[^/]+?)/-/reconcile$", reconcile)]
