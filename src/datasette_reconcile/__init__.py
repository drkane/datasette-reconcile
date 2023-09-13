from datasette import hookimpl

from datasette_reconcile.reconcile import ReconcileAPI
from datasette_reconcile.utils import check_config, check_permissions


async def reconcile(request, datasette):
    database = request.url_vars["db_name"]
    table = request.url_vars["db_table"]
    db = datasette.get_database(database)

    # get plugin configuration
    config = datasette.plugin_config("datasette-reconcile", database=database, table=table)
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

    # get the reconciliation API and call it
    reconcile_api = ReconcileAPI(config, database, table, datasette)
    return await reconcile_api.get(request)


@hookimpl
def register_routes():
    return [(r"/(?P<db_name>[^/]+)/(?P<db_table>[^/]+?)/-/reconcile$", reconcile)]
