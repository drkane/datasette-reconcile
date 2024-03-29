from datasette_reconcile.utils import get_select_fields


def test_get_select_fields():
    config = {
        "id_field": "id",
        "name_field": "name",
        "type_field": "type",
        "type_default": [{"id": "default", "name": "Default"}],
    }
    assert get_select_fields(config) == ["id", "name", "type"]


def test_get_select_fields_description():
    config = {
        "id_field": "id",
        "name_field": "name",
        "type_field": "type",
        "description_field": "description",
        "type_default": [{"id": "default", "name": "Default"}],
    }
    assert get_select_fields(config) == ["id", "name", "type", "description"]
