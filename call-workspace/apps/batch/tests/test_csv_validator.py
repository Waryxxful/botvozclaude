import io

import pytest

from apps.batch.csv_validator import CsvValidationError, validate_and_parse_csv


def test_returns_rows_when_headers_match():
    csv_content = "phone_number,nombre,fecha\n+1,Juan,13/05\n+2,Maria,15/05\n"
    rows = validate_and_parse_csv(io.StringIO(csv_content), required_input_params=["nombre", "fecha"])
    assert rows == [
        {"phone_number": "+1", "input_params": {"nombre": "Juan", "fecha": "13/05"}},
        {"phone_number": "+2", "input_params": {"nombre": "Maria", "fecha": "15/05"}},
    ]


def test_missing_phone_number_column_raises():
    csv_content = "nombre,fecha\nJuan,13/05\n"
    with pytest.raises(CsvValidationError, match="phone_number"):
        validate_and_parse_csv(io.StringIO(csv_content), required_input_params=["nombre", "fecha"])


def test_missing_input_param_column_raises():
    csv_content = "phone_number,nombre\n+1,Juan\n"
    with pytest.raises(CsvValidationError, match="fecha"):
        validate_and_parse_csv(io.StringIO(csv_content), required_input_params=["nombre", "fecha"])


def test_empty_phone_number_row_raises():
    csv_content = "phone_number,nombre\n,Juan\n"
    with pytest.raises(CsvValidationError, match="empty"):
        validate_and_parse_csv(io.StringIO(csv_content), required_input_params=["nombre"])


def test_extra_columns_are_ignored():
    csv_content = "phone_number,nombre,extra\n+1,Juan,ignored\n"
    rows = validate_and_parse_csv(io.StringIO(csv_content), required_input_params=["nombre"])
    assert rows == [{"phone_number": "+1", "input_params": {"nombre": "Juan"}}]
