"""Cùng một truy vấn cho mọi phương pháp: lọc, nhóm, đếm và tính trung bình."""
import pandas as pd

USECOLS = ['house_age', 'mrt_distance_m', 'age_band', 'price_10k_twd_per_ping']
DTYPES = {'house_age': 'float64', 'mrt_distance_m': 'float64',
          'age_band': 'category', 'price_10k_twd_per_ping': 'float64'}
METHODS = ['csv_full', 'csv_columns', 'csv_typed', 'csv_chunk', 'parquet_columns', 'duckdb_parquet']
LABELS = {'csv_full': 'CSV toàn bộ', 'csv_columns': 'CSV chọn cột',
          'csv_typed': 'CSV chọn cột + kiểu', 'csv_chunk': 'CSV từng khối',
          'parquet_columns': 'Parquet chọn cột', 'duckdb_parquet': 'DuckDB + Parquet',
          'duckdb_csv': 'DuckDB + CSV'}


def aggregate(df):
    chosen = df.loc[(df.house_age <= 30) & (df.mrt_distance_m <= 1000)]
    return chosen.groupby('age_band', observed=True).agg(
        count=('price_10k_twd_per_ping', 'size'),
        price_sum=('price_10k_twd_per_ping', 'sum'))


def records(grouped):
    out = []
    for band, row in grouped.sort_index().iterrows():
        if int(row['count']) == 0:
            continue
        out.append(dict(age_band=str(band), count=int(row['count']),
                        price_sum=float(row['price_sum']),
                        mean_price=float(row['price_sum']/row['count'])))
    return out


def run_query(method, csv_path, parquet_path, chunksize=50_000):
    if method == 'csv_full':
        df = pd.read_csv(csv_path)
    elif method == 'csv_columns':
        df = pd.read_csv(csv_path, usecols=USECOLS)
    elif method == 'csv_typed':
        df = pd.read_csv(csv_path, usecols=USECOLS, dtype=DTYPES)
    elif method == 'csv_chunk':
        combined = None
        for part in pd.read_csv(csv_path, usecols=USECOLS, dtype=DTYPES, chunksize=chunksize):
            grouped = aggregate(part)
            combined = grouped if combined is None else combined.add(grouped, fill_value=0)
        return [] if combined is None else records(combined)
    elif method == 'parquet_columns':
        df = pd.read_parquet(parquet_path, columns=USECOLS)
    elif method == 'duckdb_parquet':
        import duckdb
        with duckdb.connect() as con:
            con.execute("SET threads=1")
            con.execute("SET memory_limit='1GB'")
            result = con.execute('''SELECT age_band, COUNT(*) AS count,
                  SUM(price_10k_twd_per_ping) AS price_sum
                FROM read_parquet(?) WHERE house_age <= 30 AND mrt_distance_m <= 1000
                GROUP BY age_band ORDER BY age_band''', [str(parquet_path)]).fetchall()
        return [dict(age_band=b, count=int(c), price_sum=float(s), mean_price=float(s/c)) for b,c,s in result]
    else:
        raise ValueError(f'Phương pháp không hợp lệ: {method}')
    return records(aggregate(df))
