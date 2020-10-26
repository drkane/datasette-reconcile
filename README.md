# datasette-reconcile

[![PyPI](https://img.shields.io/pypi/v/datasette-reconcile.svg)](https://pypi.org/project/datasette-reconcile/)
[![Changelog](https://img.shields.io/github/v/release/drkane/datasette-reconcile?include_prereleases&label=changelog)](https://github.com/drkane/datasette-reconcile/releases)
[![Tests](https://github.com/drkane/datasette-reconcile/workflows/Test/badge.svg)](https://github.com/drkane/datasette-reconcile/actions?query=workflow%3ATest)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/drkane/datasette-reconcile/blob/main/LICENSE)

Adds a reconciliation API endpoint to [Datasette](https://docs.datasette.io/en/stable/), based on the [Reconciliation Service API](https://reconciliation-api.github.io/specs/latest/) specification.

The reconciliation API is used to match a set of strings to their correct identifiers, to help with disambiguation and consistency in large datasets. For example, the strings "United Kingdom", "United Kingdom of Great Britain and Northern Ireland" and "UK" could all be used to identify the country which has the ISO country code `GB`. It is particularly implemented in [OpenRefine](https://openrefine.org/).

The plugin adds a `/reconcile` endpoint to a table served by datasette, which responds based on the Reconciliation Service API specification. In order to activate this endpoint you need to configure the reconciliation service, as dscribed in the [usage](#usage) section.

## Installation

Install this plugin in the same environment as Datasette.

    $ datasette install datasette-reconcile

## Usage

### Plugin configuration

The plugin should be configured using Datasette's [`metadata.json`](https://docs.datasette.io/en/stable/metadata.html) file. The configuration can be put at the root, database or table layer of `metadata.json`, for most use cases it will make most sense to configure at the table level.

Add a `datasette-reconcile` object under `plugins` in `metadata.json`. This should look something like:

```json
{
    "databases": {
        "sf-trees": {
            "tables": {
                "Street_Tree_List": {
                    "plugins": {
                        "datasette-reconcile": {
                            "id_field": "id",
                            "name_field": "name",
                            "type_field": "type",
                            "type_default": "Tree",
                            "max_limit": 5,
                            "service_name": "Tree reconciliation"
                        }
                    }
                }
            }
        }
    }
}
```

The only required item in the configuration is `name_field`. This refers to the field in the table which will be searched to match the query text.

The rest of the configuration items are optional, and are as follows:

- `id_field`: The field containing the identifier for this entity. If not provided, and there is a primary key set, then the primary key will be used. A primary key of more than one field will give an error.
- `type_field`: If provided, this field will be used to determine the type of the entity. If not provided, then the `type_default` setting will be used instead.
- `type_default`: If provided, this value will be used as the type of every entity returned. If not provided the default of `Object` will be used for every entity.
- `max_limit`: The maximum number of records that a query can request to return. This is 5 by default. A individual query can request fewer results than this, but it cannot request more.
- `service_name`: The name of the reconciliation service that will appear in the service manifest. If not provided it will take the form `<database name> <table name> reconciliation`.
- `identifierSpace`: [Identifier space](https://reconciliation-api.github.io/specs/latest/#identifier-and-schema-spaces) given in the service manifest. If not provided a default of `http://rdf.freebase.com/ns/type.object.id` is used.
- `schemaSpace`: [Schema space](https://reconciliation-api.github.io/specs/latest/#identifier-and-schema-spaces) given in the service manifest. If not provided a default of `http://rdf.freebase.com/ns/type.object.id` is used.

### Using the endpoint

Once the plugin is configured for a particular database or table, you can access the reconciliation endpoint using the url `/<db_name>/<table>/reconcile`.

A simple GET request to `/<db_name>/<table>/reconcile` will return the [Service Manifest](https://reconciliation-api.github.io/specs/latest/#service-manifest) as JSON which reconciliation clients can use to determine how the service is set up.

A POST request to the same url with the `queries` argument set will trigger the reconciliation process. The `queries` parameter should be a json object in the format described in [the specification](https://reconciliation-api.github.io/specs/latest/#reconciliation-queries). An example set of two queries would look like:

```json
{
  "q1": {
    "query": "Hans-Eberhard Urbaniak"
  },
  "q2": {
    "query": "Ernst Schwanhold"
  }
}
```

The query can optionally be encoded as a `queries` parameter in a GET request. For example:

```
/<db_name>/<table>/reconcile?queries={"q1":{"query":"Hans-Eberhard Urbaniak"},"q2":{"query": "Ernst Schwanhold"}}
```

Various options are available in the query object. Current the only ones implemented in datasette-reconcile are the mandatory `query` string, and the `limit` option, which must be less than or equal to the value in the `max_limit` configration option.

### Returned value

The result of the GET or POST `queries` requests described above is a json object describing potential [reconciliation candidates](https://reconciliation-api.github.io/specs/latest/#reconciliation-query-responses) for each of the queries specified. The result will look something like:

```json
{
  "q1": {
    "result": [
      {
        "id": "120333937",
        "name": "Urbaniak, Regina",
        "score": 53.015232,
        "match": false,
        "type": "Person"
      },
      {
        "id": "1127147390",
        "name": "Urbaniak, Jan",
        "score": 52.357353,
        "match": false,
        "type": "Person"
      }
    ]
  },
  "q2": {
    "result": [
      {
        "id": "123064325",
        "name": "Schwanhold, Ernst",
        "score": 86.43497,
        "match": true,
        "type": "Person"
      },
      {
        "id": "116362988X",
        "name": "Schwanhold, Nadine",
        "score": 62.04763,
        "match": false,
        "type": "Person"
      }
    ]
  }
}
```

## Development

To set up this plugin locally, first checkout the code. Then create a new virtual environment:

    cd datasette-reconcile
    python3 -mvenv venv
    source venv/bin/activate

Or if you are using `pipenv`:

    pipenv shell

Now install the dependencies and tests:

    pip install -e '.[test]'

To run the tests:

    pytest
