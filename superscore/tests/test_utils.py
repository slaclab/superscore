import csv

import pytest

from superscore.utils import parse_csv_to_dict


def write_csv(tmp_path, headers, rows, name="input.csv"):
    """Create a test csv file and return the path to it. Will automatically clean itself up after the test is run."""
    file_path = tmp_path / name
    with file_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    return file_path


def test_parse_correctly_formatted_csv_file(tmp_path):
    """Verify that a csv file in the correct format is parsed correctly"""

    # Mimic a csv file that looks like:
    # PV,Description,Area,Subsystem
    # LASR:GUNB:TEST1,First LASR pv in GUNB,IN20, GUNB,Laser
    # MGNT:GUNB:TEST0,Only MGNT pv in GUNB,IN20,Magnet

    headers = ["PV", "Description", "Area", "Subsystem"]
    rows = [
        ["LASR:GUNB:TEST1", "First LASR pv in GUNB", "IN20, GUNB", "Laser"],
        ["MGNT:GUNB:TEST0", "Only MGNT pv in GUNB", "IN20", "Magnet"],
    ]
    path = write_csv(tmp_path, headers, rows)

    # Parse the temporary csv file and confirm everything looks ok
    output = parse_csv_to_dict(str(path))
    assert len(output) == 2

    first_row = output[0]
    assert first_row["PV"] == "LASR:GUNB:TEST1"
    assert first_row["Description"] == "First LASR pv in GUNB"
    assert first_row["groups"]["Area"] == ["IN20", "GUNB"]
    assert first_row["groups"]["Subsystem"] == ["Laser"]

    second_row = output[1]
    assert second_row["PV"] == "MGNT:GUNB:TEST0"
    assert second_row["Description"] == "Only MGNT pv in GUNB"
    assert second_row["groups"]["Area"] == ["IN20"]
    assert second_row["groups"]["Subsystem"] == ["Magnet"]


def test_parse_csv_without_required_columns(tmp_path):
    """Ensure the correct errors are raised when required columns are missing"""
    # Missing PV
    headers = ["Description", "Area"]
    rows = [["Test description", "IN20"]]
    path = write_csv(tmp_path, headers, rows)
    with pytest.raises(ValueError) as e:
        parse_csv_to_dict(str(path))
    assert "No 'PV' column" in str(e.value)

    # Missing Description
    headers2 = ["PV", "Area"]
    rows = [["TEST:PV", "IN20"]]
    path = write_csv(tmp_path, headers2, rows, name="input2.csv")
    with pytest.raises(ValueError) as e:
        parse_csv_to_dict(str(path))
    assert "No 'Description' column" in str(e.value)


def test_parse_csv_with_missing_or_bad_data(tmp_path):
    """When non-required data is missing or invalid, ensured it is handled correctly"""
    headers = ["PV", "Description", "Value1", "Value2", "Value3"]
    rows = [["TEST:PV", "Test description", "NaN", "none", ""]]
    path = write_csv(tmp_path, headers, rows)
    output = parse_csv_to_dict(str(path))
    parsed_row = output[0]

    assert parsed_row["PV"] == "TEST:PV"
    assert parsed_row["Description"] == "Test description"
    assert parsed_row["groups"]["Value1"] == []
    assert parsed_row["groups"]["Value2"] == []
    assert parsed_row["groups"]["Value3"] == []
