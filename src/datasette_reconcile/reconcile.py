import json

from datasette.utils import escape_fts, escape_sqlite
from datasette.utils.asgi import Response
from fuzzywuzzy import fuzz

from datasette_reconcile.settings import (
    DEFAULT_IDENTIFER_SPACE,
    DEFAULT_LIMIT,
    DEFAULT_SCHEMA_SPACE,
    DEFAULT_TYPE,
)
from datasette_reconcile.utils import get_select_fields, get_view_url


class ReconcileAPI:
    api_version = "0.2"

    def __init__(self, config, database, table, datasette):
        self.config = config
        self.database = database
        self.db = datasette.get_database(database)
        self.table = table
        self.datasette = datasette

    def _get_headers(self):
        return {
            "Access-Control-Allow-Origin": "*",
        }

    async def get(self, request):
        # work out if we are looking for queries
        queries = await self.get_queries(request)
        if queries:
            return Response.json(
                {q[0]: {"result": q[1]} async for q in self.reconcile_queries(queries)},
                headers=self._get_headers(),
            )
        # if we're not then just return the service specification
        return Response.json(
            self.service_manifest(request),
            headers=self._get_headers(),
        )

    async def get_queries(self, request):
        post_vars = await request.post_vars()
        queries = post_vars.get("queries", request.args.get("queries"))
        if queries:
            return json.loads(queries)

    async def reconcile_queries(self, queries):
        select_fields = get_select_fields(self.config)
        for query_id, query in queries.items():
            limit = min(
                query.get("limit", self.config.get("max_limit", DEFAULT_LIMIT)),
                self.config.get("max_limit", DEFAULT_LIMIT),
            )

            where_clauses = ["1"]
            from_clause = escape_sqlite(self.table)
            order_by = ""
            params = {}
            if self.config["fts_table"]:
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
                """.format(  # noqa: S608
                    table=escape_sqlite(self.table),
                    fts_table=escape_sqlite(self.config["fts_table"]),
                )
                order_by = "order by a.rank"
                params["search_query"] = escape_fts(query["query"])
            else:
                where_clauses.append(
                    "{search_col} like :search_query".format(
                        search_col=escape_sqlite(self.config["name_field"]),
                    )
                )
                params["search_query"] = f"%{query['query']}%"

            query_sql = """
                SELECT {select_fields}
                FROM {from_clause}
                WHERE {where_clause} {order_by}
                LIMIT {limit}""".format(  # noqa: S608
                select_fields=",".join([escape_sqlite(f) for f in select_fields]),
                from_clause=from_clause,
                where_clause=" and ".join(where_clauses),
                order_by=order_by,
                limit=limit,
            )
            query_results = [self.get_query_result(r, query) for r in await self.db.execute(query_sql, params)]
            query_results = sorted(query_results, key=lambda x: -x["score"])
            yield query_id, query_results

    def get_query_result(self, row, query):
        name = str(row[self.config["name_field"]])
        name_match = str(name).lower().strip()
        query_match = str(query["query"]).lower().strip()
        type_ = self.config.get("type_default", [DEFAULT_TYPE])
        if self.config.get("type_field") and self.config["type_field"] in row:
            type_ = [row[self.config["type_field"]]]

        return {
            "id": str(row[self.config["id_field"]]),
            "name": name,
            "type": type_,
            "score": fuzz.ratio(name_match, query_match),
            "match": name_match == query_match,
        }

    def service_manifest(self, request):
        # @todo: if type_field is set then get a list of types to use in the "defaultTypes" item below.
        view_url = self.config.get("view_url")
        if not view_url:
            view_url = self.datasette.absolute_url(request, get_view_url(self.datasette, self.database, self.table))
        return {
            "versions": ["0.1", "0.2"],
            "name": self.config.get(
                "service_name",
                f"{self.database} {self.table} reconciliation",
            ),
            "identifierSpace": self.config.get("identifierSpace", DEFAULT_IDENTIFER_SPACE),
            "schemaSpace": self.config.get("schemaSpace", DEFAULT_SCHEMA_SPACE),
            "defaultTypes": self.config.get("type_default", [DEFAULT_TYPE]),
            "view": {"url": view_url},
        }
