"""CSV parsing and validation for batch call uploads."""

import csv
from typing import IO


class CsvValidationError(ValueError):
    pass


def validate_and_parse_csv(file: IO[str], required_input_params: list[str]) -> list[dict]:
    reader = csv.DictReader(file)
    headers = reader.fieldnames or []

    if "phone_number" not in headers:
        raise CsvValidationError("CSV must include a 'phone_number' column.")

    missing = [p for p in required_input_params if p not in headers]
    if missing:
        raise CsvValidationError(f"CSV is missing required columns: {', '.join(missing)}")

    rows: list[dict] = []
    for idx, row in enumerate(reader, start=2):
        phone = (row.get("phone_number") or "").strip()
        if not phone:
            raise CsvValidationError(f"Row {idx}: phone_number is empty.")
        input_params = {p: (row.get(p) or "").strip() for p in required_input_params}
        rows.append({"phone_number": phone, "input_params": input_params})

    return rows
