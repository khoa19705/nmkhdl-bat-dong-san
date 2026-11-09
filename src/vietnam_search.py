"""Tra cứu có tham số và xuất CSV theo luồng trên bảng Parquet sạch."""
from pathlib import Path
import duckdb
import pyarrow as pa
import pyarrow.csv as arrow_csv
from src.vietnam_queries import sql_conditions

DISPLAY_COLUMNS=['source_shard','source_row','province_name','district_name','property_type_name',
                 'price_vnd','area_m2','price_per_m2_vnd','bedroom_count','published_at']


def search_data(parquet_path,filters=None,limit=20,export=None):
    if not 1<=limit<=1000: raise ValueError('Số dòng xem trước phải từ 1 đến 1.000.')
    where,params=sql_conditions(filters)
    parquet_path=Path(parquet_path)
    if not parquet_path.is_file(): raise FileNotFoundError('Chưa có bảng sạch; chạy run_vietnam.py để chuẩn bị dữ liệu.')
    with duckdb.connect(config={'memory_limit':'256MB','threads':1}) as con:
        count=con.execute('SELECT COUNT(*) FROM read_parquet(?) WHERE '+where,[str(parquet_path)]+params).fetchone()[0]
        sql='SELECT '+','.join(DISPLAY_COLUMNS)+' FROM read_parquet(?) WHERE '+where
        preview=con.execute(sql+' ORDER BY price_vnd,source_shard,source_row LIMIT ?',
                            [str(parquet_path)]+params+[limit]).to_arrow_table().to_pylist()
        exported=0
        if export is not None:
            target=Path(export); target.parent.mkdir(parents=True,exist_ok=True)
            if target.resolve()==parquet_path.resolve(): raise ValueError('File xuất trùng file nguồn.')
            temp=target.with_suffix(target.suffix+'.partial')
            reader=con.execute(sql,[str(parquet_path)]+params).to_arrow_reader(50_000)
            with pa.OSFile(str(temp),'wb') as stream:
                with arrow_csv.CSVWriter(stream,reader.schema) as writer:
                    for batch in reader:
                        writer.write_batch(batch); exported+=batch.num_rows
            reader.close()
            if exported!=count: raise AssertionError('Số hàng xuất khác kết quả đếm.')
            temp.replace(target)
    return dict(matched_rows=count,preview=preview,preview_order='price_vnd, source_shard, source_row tăng dần',
                exported_rows=exported,export_path=str(export) if export is not None else None)
