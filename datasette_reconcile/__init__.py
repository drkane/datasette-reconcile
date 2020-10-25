from datasette.utils.asgi import Response, NotFound, Forbidden
from datasette.utils import escape_sqlite
from datasette import hookimpl
import html
import json


DEFAULT_LIMIT = 5
DEFAULT_TYPE = 'Object'

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
        raise ReconcileError("Table not found: {}".format(table))

    if not config:
        raise ReconcileError("datasette-reconcile not configured for table {} in database {}".format(table, str(db)))
    
    pks = await db.primary_keys(table)
    if not pks:
        pks = ['rowid']

    if "id_field" not in config and len(pks) == 1:
        config['id_field'] = pks[0]
    elif "id_field" not in config:
        raise ReconcileError("Could not determine an ID field to use")
    if "name_field" not in config:
        raise ReconcileError("Name field must be defined to activate reconciliation")
    if "type_field" not in config and "type_default" not in config:
        config['type_default'] = DEFAULT_TYPE
    
    config['fts_table'] = await db.fts_table(table)
    
    return config


async def reconcile(request, datasette):
    database = request.url_vars["db_name"]
    table = request.url_vars["db_table"]
    db = datasette.get_database(database)

    config = datasette.plugin_config(
        "datasette-reconcile",
        database=database,
        table=table
    )
    config = await check_config(config, db, table)

    await check_permissions(
        request,
        [
            ("view-table", (database, table)),
            ("view-database", database),
            "view-instance",
        ],
        datasette
    )

    if request.args.get("queries"):
        queries = json.loads(request.args["queries"])
        return Response.json({
            q[0]: q[1] async for q in reconcile_queries(queries, config, db, table)
        })

    return Response.json({
        "name": "VIAF",
        "identifierSpace": "http://vocab.getty.edu/doc/#GVP_URLs_and_Prefixes",
        "schemaSpace": "http://vocab.getty.edu/doc/#The_Getty_Vocabularies_and_LOD"
    })


def get_select_fields(config):
    select_fields = [
        config['id_field'],
        config['name_field']
    ] + config.get('additional_fields', [])
    if config.get('type_field'):
        select_fields.append(config['type_field'])
    return select_fields


async def reconcile_queries(queries, config, db, table):
    select_fields = get_select_fields(config)
    queries_results = {}
    for query_id, query in queries.items():
        limit = min(
            query.get('limit', config.get('max_limit', DEFAULT_LIMIT)),
            config.get('max_limit', DEFAULT_LIMIT)
        )

        where_clauses = []
        params = {}
        if config['fts_table']:
            where_clauses.append(
                "rowid in (select rowid from {fts_table} where {fts_table} match :search_query)".format(
                    fts_table=escape_sqlite(config['fts_table']),
                    match_clause=":search_query",
                )
            )
            params["search_query"] = query['query']
        else:
            where_clauses.append(
                "{search_col} like :search_query".format(
                    search_col=escape_sqlite(config['name_field']),
                )
            )
            params["search_query"] = f"%{query['query']}%"

        query_results = await db.execute(
            "select {} from {} where {} limit {}".format(
                ",".join([escape_sqlite(f) for f in select_fields]),
                escape_sqlite(table),
                " and ".join(where_clauses),
                limit,
            ),
            params
        )
        yield query_id, [{
            "id": r[config['id_field']],
            "name": r[config['name_field']],
            "type": r[config['type_field']] if config.get('type_field') and config['type_field'] in r else config['type_default'],
            "score": 100,
            "match": query['query'] == config['name_field'],
        } for r in query_results]


@hookimpl
def register_routes():
    return [
        (r"/(?P<db_name>[^/]+)/(?P<db_table>[^/]+?)/reconcile$", reconcile)
    ]
