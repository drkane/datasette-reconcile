DEFAULT_LIMIT = 5


class Reconcile:
    def __init__(self):
        self.results = None

    @property
    def service_spec(self):
        return {
            "name": "VIAF",
            "identifierSpace": "http://vocab.getty.edu/doc/#GVP_URLs_and_Prefixes",
            "schemaSpace": "http://vocab.getty.edu/doc/#The_Getty_Vocabularies_and_LOD",
        }

    def get_results(self, queries):
        if not queries:
            return self.service_spec


class BadReconciliationQuery(Exception):
    """Incorrectly formatted query"""

    pass


class ReconciliationQuery:
    def __init__(
        self, query, type_=None, limit=DEFAULT_LIMIT, properties=None, type_strict=None
    ):
        if not isinstance(query, str):
            raise BadReconciliationQuery("Query must be a string")
        if not isinstance(limit, int):
            raise BadReconciliationQuery("Limit must be an integer")
        if type_ is None:
            type_ = []
        if not isinstance(type_, list):
            raise BadReconciliationQuery("Type must be a list")
        if properties is None:
            properties = {}
        if not isinstance(properties, dict):
            raise BadReconciliationQuery("Properties must be a dictionary")
        if type_strict and type_strict not in ["should", "all", "any"]:
            raise BadReconciliationQuery(
                "Type Strict should be 'should', 'all' or 'any'"
            )

        self.query = query
        self.type_ = type_
        self.limit = limit
        self.properties = properties
        self.type_strict = type_strict

    def run(self):
        pass


class ReconciliationCandidate:
    def __init__(self, id, name, type_, score, match):
        pass
