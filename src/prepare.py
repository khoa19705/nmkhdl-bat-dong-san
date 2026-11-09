"""Tải dữ liệu gốc, làm sạch và tạo dữ liệu mô phỏng theo từng khối."""
from pathlib import Path
import hashlib
import io
import json
import time
import urllib.request
import zipfile

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://archive.ics.uci.edu/static/public/477/real+estate+valuation+data+set.zip'
SOURCE = 'https://archive.ics.uci.edu/dataset/477/real+estate+valuation+data+set'
COLS = ['source_id', 'transaction_decimal', 'house_age', 'mrt_distance_m',
        'convenience_stores', 'latitude', 'longitude', 'price_10k_twd_per_ping']
NUMERIC = COLS[1:]


def age_band(age):
    return pd.cut(age, [-np.inf, 10, 30, np.inf],
                  labels=['0-10', '10-30', '30+'], right=True).astype(str)


def clean(frame):
    """Không cắt ngoại lệ giá chỉ vì khác số đông; kiểm tra miền và ID."""
    df = frame.copy()
    before = len(df)
    for col in COLS:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    missing = df[COLS].isna().any(axis=1)
    finite = pd.Series(np.isfinite(df[COLS].to_numpy()).all(axis=1), index=df.index)
    invalid = (~finite | (df.source_id <= 0) | (df.source_id % 1 != 0)
               | (df.house_age < 0) | (df.mrt_distance_m < 0)
               | (df.convenience_stores < 0) | (df.convenience_stores % 1 != 0)
               | ~df.latitude.between(-90, 90) | ~df.longitude.between(-180, 180)
               | (df.price_10k_twd_per_ping <= 0)
               | ~df.transaction_decimal.between(1900, 2100)) & ~missing
    df = df.loc[~(missing | invalid)].copy()
    duplicates = int(df.duplicated('source_id').sum())
    df = df.drop_duplicates('source_id', keep='first')
    df['source_id'] = df.source_id.astype('int32')
    df['convenience_stores'] = df.convenience_stores.astype('int16')
    df['age_band'] = age_band(df.house_age)
    # UCI quy ước 1 ping = 3.3 m²; đây là chuyển đổi xấp xỉ theo nguồn.
    df['price_twd_per_m2'] = df.price_10k_twd_per_ping * 10000 / 3.3
    q1, q3 = df.price_10k_twd_per_ping.quantile([.25, .75])
    df['price_iqr_flag'] = ~df.price_10k_twd_per_ping.between(q1-1.5*(q3-q1), q3+1.5*(q3-q1))
    audit = dict(input_rows=before, missing_rows=int(missing.sum()),
                 invalid_rows=int(invalid.sum()), duplicate_id_rows=duplicates,
                 output_rows=len(df), price_iqr_flags=int(df.price_iqr_flag.sum()))
    return df.reset_index(drop=True), audit


def prepare_source():
    raw = ROOT / 'data/raw'
    raw.mkdir(parents=True, exist_ok=True)
    archive = raw / 'uci_477.zip'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    with zipfile.ZipFile(archive) as z:
        names = [n for n in z.namelist() if n.endswith('.xlsx')]
        if len(names) != 1:
            raise ValueError('Cần đúng một file XLSX từ nguồn UCI.')
        contents = z.read(names[0])
    (raw / 'uci_477_original.xlsx').write_bytes(contents)
    df = pd.read_excel(io.BytesIO(contents))
    if len(df.columns) != len(COLS):
        raise ValueError('Schema nguồn thay đổi; cần kiểm tra trước khi đổi tên cột.')
    df.columns = COLS
    df.to_csv(raw / 'uci_477.csv', index=False)
    cleaned, audit = clean(df)
    out = ROOT / 'data/processed'
    out.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(out / 'real_estate_clean.csv', index=False)
    cleaned.to_parquet(out / 'real_estate_clean.parquet', index=False)
    metadata = dict(source=SOURCE, doi='10.24432/C5J30W', author='I-Cheng Yeh',
                    license='CC BY 4.0', downloaded_utc=pd.Timestamp.now(tz='UTC').isoformat(),
                    zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), audit=audit)
    (out / 'source_metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return cleaned, metadata


def generate(base, sizes, seed=42, chunksize=100_000):
    """Bootstrap nguyên hàng + nhiễu nhỏ; chỉ dùng để đo tải, không suy luận thị trường.

    Mỗi mức dùng cùng seed; cố định kích thước và chunksize để tái lập dữ liệu.
    Dữ liệu được ghi tuần tự, không cần giữ cả triệu hàng trong RAM.
    """
    out = ROOT / 'data/benchmark'
    out.mkdir(parents=True, exist_ok=True)
    metadata = []
    for n in sizes:
        if n <= 0:
            raise ValueError('Số dòng phải dương.')
        rng = np.random.default_rng(seed)
        csv_path, pq_path = out / f'estate_{n}.csv', out / f'estate_{n}.parquet'
        csv_s = parquet_s = 0.0
        writer = None
        try:
            for start in range(0, n, chunksize):
                count = min(chunksize, n-start)
                part = base.iloc[rng.integers(0, len(base), count)][COLS].copy().reset_index(drop=True)
                part.insert(0, 'record_id', np.arange(start+1, start+count+1, dtype='int64'))
                part['house_age'] = np.maximum(0, part.house_age + rng.normal(0, .5, count)).round(2)
                part['mrt_distance_m'] = np.maximum(0, part.mrt_distance_m * rng.lognormal(0, .03, count)).round(3)
                part['price_10k_twd_per_ping'] = (part.price_10k_twd_per_ping * rng.lognormal(0, .04, count)).round(2)
                part['age_band'] = age_band(part.house_age)
                part['price_twd_per_m2'] = (part.price_10k_twd_per_ping * 10000 / 3.3).round(4)
                part['is_synthetic'] = True
                t = time.perf_counter()
                part.to_csv(csv_path, mode='w' if start == 0 else 'a', header=start == 0, index=False)
                csv_s += time.perf_counter()-t
                t = time.perf_counter()
                table = pa.Table.from_pandas(part, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(pq_path, table.schema, compression='snappy')
                writer.write_table(table, row_group_size=chunksize)
                parquet_s += time.perf_counter()-t
        finally:
            if writer is not None:
                t = time.perf_counter()
                writer.close()
                parquet_s += time.perf_counter()-t
        metadata.append(dict(rows=n, seed=seed, chunksize=chunksize,
                             csv_bytes=csv_path.stat().st_size, parquet_bytes=pq_path.stat().st_size,
                             csv_write_s=csv_s, parquet_write_s=parquet_s))
        print(f'Đã tạo {n:,} dòng mô phỏng.', flush=True)
    (out / 'manifest.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return metadata
