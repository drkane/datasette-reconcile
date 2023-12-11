import json

from datasette.utils import escape_fts, escape_sqlite
from datasette.utils.asgi import Response
from fuzzywuzzy import fuzz

from datasette_reconcile.settings import (
    DEFAULT_IDENTIFER_SPACE,
    DEFAULT_LIMIT,
    DEFAULT_SCHEMA_SPACE,
    DEFAULT_TYPE,
    DEFAULT_PROPERTY_SETTINGS,
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
    
    async def reconcile(self, request):
        """
        Takes a request and returns a response based on the queries.
        """
        # work out if we are looking for queries
        post_vars = await request.post_vars()
        queries = post_vars.get("queries", request.args.get("queries"))
        extend = post_vars.get("extend", request.args.get("extend"))

        if queries:
            return self._response({q[0]: {"result": q[1]} async for q in self._reconcile_queries(json.loads(queries))})
        elif extend:
            response = await self._extend(json.loads(extend))
            return self._response(response)
        else:
        # if we're not then just return the service specification
            return self._response(self._service_manifest(request))


    async def properties(self, request):
        limit = request.args.get('limit', DEFAULT_LIMIT)
        type = request.args.get('type', None)

        properties = self.config.get("properties", DEFAULT_PROPERTY_SETTINGS)

        return self._response({
            "limit": limit,
            "type": type,
            "properties": [{"id": p.get('name'), "name": p.get('label')} for p in properties]
        })

    def _response(self, response):
        return Response.json(
            response,
            headers={
                "Access-Control-Allow-Origin": "*",
            },
        )
        
    async def _extend(self, data):
        ids = data['ids']
        data_properties = data['properties']
        properties = self.config.get("properties", DEFAULT_PROPERTY_SETTINGS)
        PROPERTIES = {p['name']: p for p in properties}
        id_field = self.config.get("id_field", "id")

        select_fields = [id_field] + [p['id'] for p in data_properties]

        query_sql = """
            select {fields}
            from {table}
            where {where_clause}
        """.format(
            table=escape_sqlite(self.table),
            where_clause=f'{escape_sqlite(id_field)} in ({",".join(ids)})',
            fields=','.join([escape_sqlite(f) for f in select_fields])
        )
        params = {}
        query_results = await self.db.execute(query_sql, params)

        rows = {}
        for row in query_results:
            values = {}
            for p in data_properties:
                values[p['id']] = [
                    {
                        "str": row[p['id']]
                    }
                ]

            rows[row[id_field]] = values

        response = {
            'meta': [{"id": p['id'], 'name': PROPERTIES[p['id']]['label']} for p in data_properties],
            'rows': rows
        }

        return response

    async def _reconcile_queries(self, queries):
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
            query_results = [self._get_query_result(r, query) for r in await self.db.execute(query_sql, params)]
            query_results = sorted(query_results, key=lambda x: -x["score"])
            yield query_id, query_results

    def _get_query_result(self, row, query):
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

    def _service_manifest(self, request):
        # @todo: if type_field is set then get a list of types to use in the "defaultTypes" item below.
        # handle X-FORWARDED-PROTO in Datasette: https://github.com/simonw/datasette/issues/2215
        scheme = request.scheme
        if 'x-forwarded-proto' in request.headers:
            scheme = request.headers.get('x-forwarded-proto')
        
        view_url = self.config.get("view_url")
        if not view_url:
            view_url = f"{scheme}://{request.host}{get_view_url(self.datasette, self.database, self.table)}"

        properties = self.config.get("properties", DEFAULT_PROPERTY_SETTINGS)

        manifest = {
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
    
        if properties:
            manifest["extend"] = {
                "propose_properties": {
                    "service_url": f'{scheme}://{request.host}{self.datasette.setting("base_url")}',
                    "service_path": f'{self.database}/{self.table}/-/reconcile/properties'
                },
                "property_settings": self.config.get("properties", DEFAULT_PROPERTY_SETTINGS)
            }

        return manifest