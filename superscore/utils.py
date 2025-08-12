import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

SUPERSCORE_SOURCE_PATH = Path(__file__).parent


def utcnow():
    return datetime.now(timezone.utc)


def build_abs_path(basedir: str, path: str) -> str:
    """
    Builds an abs path starting at basedir if path is not already absolute.
    ~ and ~user constructions will be expanded, so ~/path is considered absolute.
    If path is absolute already, this function returns path without modification.
    Parameters
    ----------
    basedir : str
        If path is not absolute already, build an abspath
        with path starting here.
    path : str
        The path to convert to absolute.
    """
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    if not os.path.isabs(path):
        return os.path.abspath(os.path.join(basedir, path))
    return path


def parse_csv_to_dict(csv_file_path: str) -> List[Dict[str, Any]]:
    """
    Parse CSV using the csv module with better column handling.
    """
    result = []

    with open(csv_file_path, 'r', newline='', encoding='utf-8') as csvfile:
        csvfile.seek(0)

        reader = csv.reader(csvfile)
        headers = next(reader)

        cleaned_headers = []
        header_mapping = {}

        for i, header in enumerate(headers):
            cleaned_header = str(header).strip()
            if cleaned_header:
                cleaned_headers.append(cleaned_header)
                header_mapping[cleaned_header] = i

        pv_column = 'PV' if 'PV' in cleaned_headers else None
        description_column = 'Description' if 'Description' in cleaned_headers else None

        if pv_column is None:
            raise ValueError(f"No 'PV' column found. Available columns: {cleaned_headers}")

        if description_column is None:
            raise ValueError(f"No 'Description' column found. Available columns: {cleaned_headers}")

        group_columns = [col for col in cleaned_headers if col not in [pv_column, description_column]]

        for row_num, row in enumerate(reader, start=2):
            try:
                pv_index = header_mapping[pv_column]
                pv_value = row[pv_index].strip() if pv_index < len(row) else ''

                if not pv_value:
                    continue

                desc_index = header_mapping[description_column]
                desc_value = row[desc_index].strip() if desc_index < len(row) else ''

                row_dict = {
                    'PV': pv_value,
                    'Description': desc_value,
                    'groups': {}
                }

                for group_name in group_columns:
                    group_index = header_mapping[group_name]
                    cell_value = row[group_index].strip() if group_index < len(row) else ''

                    if cell_value and cell_value.lower() not in ['nan', 'none']:
                        values = [val.strip() for val in cell_value.split(',') if val.strip()]
                        row_dict['groups'][group_name] = values
                    else:
                        row_dict['groups'][group_name] = []

                result.append(row_dict)

            except (IndexError, KeyError) as e:
                print(f"Warning: Could not process row {row_num}: {e}")
                continue

    return result
