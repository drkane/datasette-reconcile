# datasette-reconcile

[![PyPI - Version](https://img.shields.io/pypi/v/datasette-reconcile.svg)](https://pypi.org/project/datasette-reconcile)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/datasette-reconcile.svg)](https://pypi.org/project/datasette-reconcile)
[![Changelog](https://img.shields.io/github/v/release/drkane/datasette-reconcile?include_prereleases&label=changelog)](https://github.com/drkane/datasette-reconcile/releases)
[![Tests](https://github.com/drkane/datasette-reconcile/workflows/Test/badge.svg)](https://github.com/drkane/datasette-reconcile/actions?query=workflow%3ATest)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/drkane/datasette-reconcile/blob/main/LICENSE)

Adds a reconciliation API endpoint to [Datasette](https://docs.datasette.io/en/stable/), based on the [Reconciliation Service API](https://reconciliation-api.github.io/specs/latest/) specification.

The reconciliation API is used to match a set of strings to their correct identifiers, to help with disambiguation and consistency in large datasets. For example, the strings "United Kingdom", "United Kingdom of Great Britain and Northern Ireland" and "UK" could all be used to identify the country which has the ISO country code `GB`. It is particularly implemented in [OpenRefine](https://openrefine.org/).

The plugin adds a `/-/reconcile` endpoint to a table served by datasette, which responds based on the Reconciliation Service API specification. In order to activate this endpoint you need to configure the reconciliation service, as dscribed in the [usage](#usage) section.

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
              "type_default": [
                {
                  "id": "tree",
                  "name": "Tree"
                }
              ],
              "max_limit": 5,
              "service_name": "Tree reconciliation",
              "view_url": "https://example.com/trees/{{id}}"
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
- `view_url`: [URL for a view of an individual entity](https://reconciliation-api.github.io/specs/latest/#dfn-view-template). It must contain the string `{{id}}` which will be replaced with the ID of the entity. If not provided it will use the default datasette view for the entity record (something like `/<db_name>/<table>/{{id}}`).

### Using the endpoint

Once the plugin is configured for a particular database or table, you can access the reconciliation endpoint using the url `/<db_name>/<table>/-/reconcile`.

A simple GET request to `/<db_name>/<table>/-/reconcile` will return the [Service Manifest](https://reconciliation-api.github.io/specs/latest/#service-manifest) as JSON which reconciliation clients can use to determine how the service is set up.

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
/<db_name>/<table>/-/reconcile?queries={"q1":{"query":"Hans-Eberhard Urbaniak"},"q2":{"query": "Ernst Schwanhold"}}
```

Various options are available in the query object. Current the only ones implemented in datasette-reconcile are the mandatory `query` string, and the `limit` option, which must be less than or equal to the value in the `max_limit` configration option.

All endpoints that start with `/<db_name>/<table>/-/reconcile` are configured to send an `Access-Control-Allow-Origin: *` CORS header to allow access [as described in the specification](https://reconciliation-api.github.io/specs/latest/#cross-origin-access).

JSONP output is not yet supported.

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
        "type": [
          {
            "id": "person",
            "name": "Person"
          }
        ]
      },
      {
        "id": "1127147390",
        "name": "Urbaniak, Jan",
        "score": 52.357353,
        "match": false,
        "type": [
          {
            "id": "person",
            "name": "Person"
          }
        ]
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
        "type": [
          {
            "id": "person",
            "name": "Person"
          }
        ]
      },
      {
        "id": "116362988X",
        "name": "Schwanhold, Nadine",
        "score": 62.04763,
        "match": false,
        "type": [
          {
            "id": "person",
            "name": "Person"
          }
        ]
      }
    ]
  }
}
```

### Behind the scenes

The reconcile engine works by performing an SQL query against the `name_field` within the specified database table. Where that table has a full text search index implemented, the search will be performed against that index.

When a full text search index is present on the table, the SQL query takes the form (based on the search query `test`, note that double quotes are added to facilitate searching - these are not present in the original query):

```sql
select <id_field>, <name_field>
from <table>
  inner join (
    select "rowid", "rank"
    from <fts_table>
    where <fts_table> MATCH '"test"'
  ) as "a" on <table>."rowid" = a."rowid"
order by a.rank
limit 5
```

If a full text search index is not present, the query looks like this (note that the wildcard `%` is added to either side of the query - these are not present in the original query):

```sql
select <id_field>, <name_field>
from <table>
where <name_field> like '%test%'
limit 5
```

### Extend endpoint

You can also use the reconciliation API [Data extension service](https://www.w3.org/community/reports/reconciliation/CG-FINAL-specs-0.2-20230410/#data-extension-service) to find additional properties for a set of entities, given an ID.

Send a GET request to the `/<db_name>/<table>/-/reconcile/extend/propose` endpoint to find a list of the possible properties you can select. The properties are all the columns in the table (excluding any that have been hidden). An example response would look like:

```json
{
  "limit": 5,
  "type": "Person",
  "properties": [
    {
      "id": "preferredName",
      "name": "preferredName"
    },
    {
      "id": "professionOrOccupation",
      "name": "professionOrOccupation"
    },
    {
      "id": "wikidataId",
      "name": "wikidataId"
    }
  ]
}
```

Then send a POST request to the `/<db_name>/<table>/-/reconcile` endpoint with an `extend` argument. The `extend` argument should be a JSON object with a set of `ids` to lookup and `properties` to return. For example:

```json
{
  "ids": ["10662041X", "1064905412"],
  "properties": [
    {
      "id": "professionOrOccupation"
    },
    {
      "id": "wikidataId"
    }
  ]
}
```

The endpoint will return a result that looks like:

```json
{
  "meta": [
    {
      "id": "professionOrOccupation",
      "name": "professionOrOccupation"
    },
    {
      "id": "wikidataId",
      "name": "wikidataId"
    }
  ],
  "rows": {
    "10662041X": {
      "professionOrOccupation": [
        {
          "str": "Doctor"
        }
      ],
      "wikidataId": [
        {
          "str": "Q3874347"
        }
      ]
    },
    "1064905412": {
      "professionOrOccupation": [
        {
          "str": "Architect"
        }
      ],
      "wikidataId": [
        {
          "str": "Q3874347"
        }
      ]
    }
  }
}
```

### Suggest endpoints

You can also use the [suggest endpoints](https://www.w3.org/community/reports/reconciliation/CG-FINAL-specs-0.2-20230410/#suggest-services) to get quick suggestions, for example for an auto-complete dropdown menu. The following endpoints are available:

- `/<db_name>/<table>/-/reconcile/suggest/property` - looks up in a list of table columns
- `/<db_name>/<table>/-/reconcile/suggest/entity` - looks up in a list of table rows
- `/<db_name>/<table>/-/reconcile/suggest/type` - not currently implemented

Each endpoint takes a `prefix` argument which can be used in a GET request. For example, the GET request `/<db_name>/<table>/-/reconcile/suggest/entity?prefix=abc` will produce a response such as:

```json
{
  "result": [
    {
      "name": "abc company limited",
      "id": "Q123456"
    },
    {
      "name": "abc other company limited",
      "id": "Q123457"
    }
  ]
}
```

## Development

This plugin uses hatch for build and testing. To set up this plugin locally, first checkout the code.

You'll need to fetch the git submodules for the tests too:

    git submodule init
    git submodule update

To run the tests:

    hatch run test

Run tests then report on coverage

    hatch run cov

Run tests then run a server showing where coverage is missing

    hatch run cov-html

### Linting/formatting

Black and ruff should be run before committing any changes.

To check for any changes needed:

    hatch run lint:style

To run any autoformatting possible:

    hatch run lint:fmt

### Publish to pypi

    hatch build
    hatch publish
    git tag v<VERSION_NUMBER>
    git push origin v<VERSION_NUMBER>

## Acknowledgements

Thanks for [@simonw](https://github.com/simonw/) for developing datasette and the datasette ecosystem.

Other contributions from:

- [@JBPressac](https://github.com/JBPressac/)
- [@nicokant](https://github.com/nicokant/) - implementation of extend service
