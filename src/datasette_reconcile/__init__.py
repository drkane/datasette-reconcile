from datasette import hookimpl

from datasette_reconcile.reconcile import ReconcileAPI
from datasette_reconcile.utils import check_config, check_permissions


async def get_api(request, datasette):
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
    return ReconcileAPI(config, database, table, datasette)


async def reconcile(request, datasette):
    reconcile_api = await get_api(request, datasette)
    return await reconcile_api.reconcile(request)


async def properties(request, datasette):
    reconcile_api = await get_api(request, datasette)
    return await reconcile_api.properties(request)


async def suggest_entity(request, datasette):
    reconcile_api = await get_api(request, datasette)
    return await reconcile_api.suggest_entity(request)


async def suggest_property(request, datasette):
    reconcile_api = await get_api(request, datasette)
    return await reconcile_api.suggest_property(request)


async def suggest_type(request, datasette):
    reconcile_api = await get_api(request, datasette)
    return await reconcile_api.suggest_type(request)


@hookimpl
def register_routes():
    return [
        (r"/(?P<db_name>[^/]+)/(?P<db_table>[^/]+?)/-/reconcile$", reconcile),
        (r"/(?P<db_name>[^/]+)/(?P<db_table>[^/]+?)/-/reconcile/extend/propose$", properties),
        (r"/(?P<db_name>[^/]+)/(?P<db_table>[^/]+?)/-/reconcile/suggest/entity$", suggest_entity),
        (r"/(?P<db_name>[^/]+)/(?P<db_table>[^/]+?)/-/reconcile/suggest/property$", suggest_property),
        (r"/(?P<db_name>[^/]+)/(?P<db_table>[^/]+?)/-/reconcile/suggest/type$", suggest_type),
    ]
