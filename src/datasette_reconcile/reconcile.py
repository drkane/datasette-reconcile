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
            return self._response(await self._service_manifest(request))

    async def properties(self, request):
        limit = request.args.get("limit", DEFAULT_LIMIT)
        type_ = request.args.get("type", DEFAULT_TYPE)

        return self._response(
            {
                "limit": limit,
                "type": type_,
                "properties": [{"id": p["id"], "name": p["name"]} async for p in self._get_properties()],
            }
        )

    async def suggest_entity(self, request):
        prefix = request.args.get("prefix")
        cursor = int(request.args.get("cursor", 0))

        name_field = self.config["name_field"]
        id_field = self.config.get("id_field", "id")
        query_sql = f"""
            select {escape_sqlite(id_field)} as id, {escape_sqlite(name_field)} as name
            from {escape_sqlite(self.table)}
            where {escape_sqlite(name_field)} like :search_query
            limit {DEFAULT_LIMIT} offset {cursor}
        """  # noqa: S608
        params = {"search_query": f"{prefix}%"}

        return self._response(
            {"result": [{"id": r["id"], "name": r["name"]} for r in await self.db.execute(query_sql, params)]}
        )

    async def suggest_property(self, request):
        prefix = request.args.get("prefix")
        cursor = request.args.get("cursor", 0)

        properties = [
            {"id": p["id"], "name": p["name"]}
            async for p in self._get_properties()
            if p["name"].startswith(prefix) or p["id"].startswith(prefix)
        ][cursor : cursor + DEFAULT_LIMIT]

        return self._response({"result": properties})

    async def suggest_type(self, request):
        prefix = request.args.get("prefix")

        default_type = self.config.get("type_default", [DEFAULT_TYPE])
        type_field = self.config.get("type_field")
        if type_field:
            query_sql = """
                SELECT CASE WHEN {type_field} IS NULL THEN '{default_type}' ELSE {type_field} END as type
                FROM {from_clause}
                GROUP BY type
                """.format(  # noqa: S608
                type_field=escape_sqlite(type_field),
                default_type=default_type[0]["id"],
                from_clause=escape_sqlite(self.table),
            )
            types = [
                {
                    "id": r["type"],
                    "name": r["type"],
                }
                for r in await self.db.execute(query_sql)
            ]
        else:
            types = default_type

        return self._response(
            {
                "result": [
                    type_ for type_ in types if prefix.lower() in type_["id"] or prefix.lower() in type_["name"]
                ][:DEFAULT_LIMIT]
            }
        )

    async def _get_properties(self):
        column_descriptions = self.datasette.table_metadata(self.database, self.table).get("columns") or {}
        for column in await self.db.table_column_details(self.table):
            yield {
                "id": column.name,
                "name": column_descriptions.get(column.name, column.name),
                "type": column.type,
            }

    def _response(self, response):
        return Response.json(
            response,
            headers={
                "Access-Control-Allow-Origin": "*",
            },
        )

    async def _extend(self, data):
        ids = data["ids"]
        data_properties = data["properties"]
        properties = {p["name"]: p async for p in self._get_properties()}
        id_field = self.config.get("id_field", "id")

        select_fields = [id_field] + [p["id"] for p in data_properties]

        query_sql = """
            select {fields}
            from {table}
            where {where_clause}
        """.format(  # noqa: S608
            table=escape_sqlite(self.table),
            where_clause=f"{escape_sqlite(id_field)} in ({','.join(['?'] * len(ids))})",
            fields=",".join([escape_sqlite(f) for f in select_fields]),
        )
        query_results = await self.db.execute(query_sql, ids)

        rows = {}
        for row in query_results:
            values = {}
            for p in data_properties:
                property_ = properties[p["id"]]
                if property_["type"] == "INTEGER":
                    values[p["id"]] = [{"int": row[p["id"]]}]
                elif property_["type"] == "FLOAT":
                    values[p["id"]] = [{"float": row[p["id"]]}]
                else:
                    values[p["id"]] = [{"str": row[p["id"]]}]

            rows[row[id_field]] = values

        response = {
            "meta": [{"id": p["id"], "name": properties[p["id"]]["name"]} for p in data_properties],
            "rows": rows,
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

            types = query.get("type", [])
            if not isinstance(types, list) and types:
                types = [types]
            type_field = self.config.get("type_field")
            if types and type_field:
                where_clauses.append(
                    "{type_field} in ({types})".format(
                        type_field=escape_sqlite(type_field),
                        types=",".join([f"'{t}'" for t in types]),
                    )
                )

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
        type_field = self.config.get("type_field")
        if type_field and type_field in dict(row):
            type_ = [
                {
                    "id": row[type_field],
                    "name": row[type_field],
                }
            ]

        result = {
            "id": str(row[self.config["id_field"]]),
            "name": name,
            "type": type_,
            "score": fuzz.ratio(name_match, query_match),
            "match": name_match == query_match,
        }
        if self.config["description_field"]:
            result["description"] = str(row[self.config["description_field"]])
        return result

    async def _service_manifest(self, request):
        # @todo: if type_field is set then get a list of types to use in the "defaultTypes" item below.
        # handle X-FORWARDED-PROTO in Datasette: https://github.com/simonw/datasette/issues/2215
        scheme = request.scheme
        if "x-forwarded-proto" in request.headers:
            scheme = request.headers.get("x-forwarded-proto")

        base_url = f'{scheme}://{request.host}{self.datasette.setting("base_url")}'
        if not base_url.endswith("/"):
            base_url += "/"

        service_url = f"{base_url}{self.database}/{self.table}/-/reconcile"

        view_url = self.config.get("view_url")
        if not view_url:
            view_url = f"{scheme}://{request.host}{get_view_url(self.datasette, self.database, self.table)}"

        properties = self._get_properties()

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
            "extend": {
                "propose_properties": (
                    {
                        "service_url": service_url,
                        "service_path": "/extend/propose",
                    }
                    if self.api_version in ["0.1", "0.2"]
                    else True
                ),
                "property_settings": [
                    {
                        "name": p["id"],
                        "label": p["name"],
                        "type": "number" if p["type"] in ["INTEGER", "FLOAT"] else "text",
                    }
                    async for p in properties
                ],
            },
            "suggest": {
                "entity": (
                    {
                        "service_url": service_url,
                        "service_path": "/suggest/entity",
                    }
                    if self.api_version in ["0.1", "0.2"]
                    else True
                ),
                "type": (
                    {
                        "service_url": service_url,
                        "service_path": "/suggest/type",
                    }
                    if self.api_version in ["0.1", "0.2"]
                    else True
                ),
                "property": (
                    {
                        "service_url": service_url,
                        "service_path": "/suggest/property",
                    }
                    if self.api_version in ["0.1", "0.2"]
                    else True
                ),
            },
        }

        return manifest
