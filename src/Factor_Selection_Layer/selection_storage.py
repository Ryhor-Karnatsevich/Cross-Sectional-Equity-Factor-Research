import hashlib
import json
import os

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from selection_config import (
    FACTOR_MATRIX_DIR,
    FACTOR_METADATA_PATH,
    FORWARD_RETURN_MATRIX_DIR,
    DAILY_QUANTILE_RESULTS_PATH,
    FORWARD_HORIZONS,
    MEMBERSHIP_PATH,
    MIN_ASSETS,
    QUANTILE_COUNT,
    QUANTILE_RUN_METADATA_PATH,
    RESEARCH_END_DATE,
    RESEARCH_START_DATE,
    SELECTION_CACHE_DIR,
    SELECTION_DATA_DIR,
    SELECTION_FIGURES_DIR,
    SELECTION_RESULTS_DIR,
    SIGNAL_LAG,
)


# -------------------------
# DIRECTORIES
def prepare_selection_directories():
    for directory in (
        SELECTION_DATA_DIR,
        SELECTION_CACHE_DIR,
        SELECTION_RESULTS_DIR,
        SELECTION_FIGURES_DIR,
    ):
        os.makedirs(directory, exist_ok=True)


# -------------------------
# FILE NAMES
def safe_factor_name(family, variant):
    return f"{family}__{variant}".replace("/", "-").replace(" ", "_")


def factor_matrix_path(family, variant):
    return os.path.join(
        FACTOR_MATRIX_DIR,
        f"{safe_factor_name(family, variant)}.parquet",
    )


def forward_return_matrix_path(horizon):
    return os.path.join(
        FORWARD_RETURN_MATRIX_DIR,
        f"forward_returns_h{int(horizon)}.parquet",
    )


# -------------------------
# FACTOR LAYER INPUTS
def load_factor_metadata():
    metadata = pd.read_csv(FACTOR_METADATA_PATH)
    required = {"key", "family", "variant", "parameters", "path"}
    missing = sorted(required.difference(metadata.columns))

    if missing:
        raise ValueError(
            "Factor metadata is incompatible. Missing columns: "
            + ", ".join(missing)
        )
    if len(metadata) != 56 or metadata["key"].duplicated().any():
        raise ValueError("Factor metadata must contain 56 unique matrices")

    return metadata


def load_membership():
    membership = pd.read_parquet(MEMBERSHIP_PATH).sort_index().astype(bool)

    if not membership.index.is_unique or not membership.index.is_monotonic_increasing:
        raise ValueError("Membership must have unique sorted dates")
    if not membership.columns.is_unique:
        raise ValueError("Membership must have unique ticker columns")

    return membership


def validate_matrix_axes(matrix, reference, name):
    if not matrix.index.equals(reference.index):
        raise ValueError(f"{name} dates do not match membership")
    if not matrix.columns.equals(reference.columns):
        raise ValueError(f"{name} ticker columns do not match membership")


def load_factor_matrix(family, variant, membership):
    path = factor_matrix_path(family, variant)
    factor = pd.read_parquet(path).sort_index()
    validate_matrix_axes(factor, membership, f"Factor {family}|{variant}")
    return factor


def load_forward_return_matrices(horizons, membership):
    matrices = {}

    for horizon in horizons:
        path = forward_return_matrix_path(horizon)
        matrix = pd.read_parquet(path).sort_index()
        validate_matrix_axes(matrix, membership, f"Forward return h{horizon}")
        matrices[int(horizon)] = matrix

    return matrices


# -------------------------
# QUANTILE CACHE VALIDATION
def file_state(path):
    state = os.stat(path)
    return {"size": state.st_size, "modified_ns": state.st_mtime_ns}


def quantile_cache_signature():
    metadata = load_factor_metadata()
    input_paths = [
        FACTOR_METADATA_PATH,
        MEMBERSHIP_PATH,
        *[
            factor_matrix_path(row.family, row.variant)
            for row in metadata.itertuples(index=False)
        ],
        *[forward_return_matrix_path(horizon) for horizon in FORWARD_HORIZONS],
    ]
    source_directory = os.path.dirname(__file__)
    source_hashes = {}
    for name in ("quantile_analysis.py", "selection_storage.py"):
        with open(os.path.join(source_directory, name), "rb") as source:
            source_hashes[name] = hashlib.sha256(source.read()).hexdigest()

    payload = {
        "version": 1,
        "inputs": {path: file_state(path) for path in input_paths},
        "source_hashes": source_hashes,
        "settings": {
            "forward_horizons": list(FORWARD_HORIZONS),
            "signal_lag": SIGNAL_LAG,
            "quantiles": QUANTILE_COUNT,
            "minimum_assets": MIN_ASSETS,
            "research_start": RESEARCH_START_DATE,
            "research_end": RESEARCH_END_DATE,
        },
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def quantile_cache_is_valid():
    try:
        with open(QUANTILE_RUN_METADATA_PATH, "r", encoding="utf-8") as file:
            metadata = json.load(file)
        return (
            metadata.get("cache_signature") == quantile_cache_signature()
            and metadata.get("result_file_state")
            == file_state(DAILY_QUANTILE_RESULTS_PATH)
            and metadata.get("result_rows")
            == pq.ParquetFile(DAILY_QUANTILE_RESULTS_PATH).metadata.num_rows
        )
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def load_factor_quantile_results(factor_key, columns):
    if not os.path.exists(DAILY_QUANTILE_RESULTS_PATH):
        raise FileNotFoundError(
            "Run quantile_analysis.py before factor classification"
        )

    table = pq.read_table(
        DAILY_QUANTILE_RESULTS_PATH,
        columns=columns,
        filters=[("factor_key", "=", factor_key)],
    )
    result = table.to_pandas().sort_values(["horizon_days", "date"])

    if result.empty:
        raise ValueError(f"Factor not found in quantile data: {factor_key}")

    return result


# -------------------------
# ATOMIC SAVING
def temporary_path(path):
    root, extension = os.path.splitext(path)
    return f"{root}.temporary{extension}"


def save_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = temporary_path(path)

    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

    os.replace(temporary, path)


def save_csv(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = temporary_path(path)
    data.to_csv(temporary, index=False)
    os.replace(temporary, path)


def save_parquet(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = temporary_path(path)
    data.to_parquet(temporary, index=False, compression="zstd")
    os.replace(temporary, path)


def save_text(text, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = temporary_path(path)

    with open(temporary, "w", encoding="utf-8") as file:
        file.write(text)

    os.replace(temporary, path)


def save_parquet_chunks(chunks, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = temporary_path(path)

    if os.path.exists(temporary):
        os.remove(temporary)

    writer = None
    row_count = 0
    chunk_count = 0

    try:
        for chunk in chunks:
            table = pa.Table.from_pandas(chunk, preserve_index=False)

            if writer is None:
                writer = pq.ParquetWriter(
                    temporary,
                    table.schema,
                    compression="zstd",
                    use_dictionary=True,
                )

            writer.write_table(table)
            row_count += len(chunk)
            chunk_count += 1

        if writer is None:
            raise ValueError("No quantile-result chunks were created")
    except BaseException:
        if writer is not None:
            writer.close()
        if os.path.exists(temporary):
            os.remove(temporary)
        raise
    else:
        writer.close()
        os.replace(temporary, path)

    return row_count, chunk_count
