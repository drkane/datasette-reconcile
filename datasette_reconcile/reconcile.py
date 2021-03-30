from datasette.utils import escape_fts, escape_sqlite
from fuzzywuzzy import fuzz

from datasette_reconcile.settings import (
    DEFAULT_IDENTIFER_SPACE,
    DEFAULT_LIMIT,
    DEFAULT_SCHEMA_SPACE,
    DEFAULT_TYPE,
)
from datasette_reconcile.utils import get_select_fields, get_view_url


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
        query_results = [
            get_query_result(r, config, query)
            for r in await db.execute(query_sql, params)
        ]
        query_results = sorted(query_results, key=lambda x: -x["score"])
        yield query_id, query_results


def get_query_result(row, config, query):
    name = str(row[config["name_field"]])
    name_match = str(name).lower().strip()
    query_match = str(query["query"]).lower().strip()
    type_ = config.get("type_default", [DEFAULT_TYPE])
    if config.get("type_field") and config["type_field"] in row:
        type_ = [row[config["type_field"]]]

    return {
        "id": str(row[config["id_field"]]),
        "name": name,
        "type": type_,
        "score": fuzz.ratio(name_match, query_match),
        "match": name_match == query_match,
    }


def service_manifest(config, database, table, datasette, request):
    # @todo: if type_field is set then get a list of types to use in the "defaultTypes" item below.
    return {
        "versions": ["0.1", "0.2"],
        "name": config.get(
            "service_name",
            "{database} {table} reconciliation".format(
                database=database,
                table=table,
            ),
        ),
        "identifierSpace": config.get("identifierSpace", DEFAULT_IDENTIFER_SPACE),
        "schemaSpace": config.get("schemaSpace", DEFAULT_SCHEMA_SPACE),
        "defaultTypes": config.get("type_default", [DEFAULT_TYPE]),
        "view": {
            "url": datasette.absolute_url(
                request, get_view_url(datasette, database, table)
            )
        },
    }
