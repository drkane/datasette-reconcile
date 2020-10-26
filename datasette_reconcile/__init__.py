import html
import json
import sqlite3
import warnings

from datasette import hookimpl
from datasette.utils.asgi import Response

from datasette_reconcile.reconcile import reconcile_queries
from datasette_reconcile.utils import check_config, check_permissions


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


@hookimpl
def register_routes():
    return [(r"/(?P<db_name>[^/]+)/(?P<db_table>[^/]+?)/reconcile$", reconcile)]
