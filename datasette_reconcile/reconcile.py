from datasette.utils import escape_fts, escape_sqlite
from fuzzywuzzy import fuzz

from datasette_reconcile.settings import DEFAULT_LIMIT
from datasette_reconcile.utils import get_select_fields


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
