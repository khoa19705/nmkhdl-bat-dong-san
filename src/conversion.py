"""Đo CSV → Parquet với schema phân tích có sẵn, đọc/ghi theo luồng."""
import pyarrow as pa
import pyarrow.csv as csv
import pyarrow.parquet as pq

SCHEMA=pa.schema([
    ('source_shard',pa.string()),('source_row',pa.int64()),('property_type_name',pa.string()),
    ('province_name',pa.string()),('district_name',pa.string()),('price_vnd',pa.float64()),
    ('area_m2',pa.float64()),('floor_count',pa.float64()),('bedroom_count',pa.float64()),
    ('bathroom_count',pa.float64()),('published_at',pa.string()),('published_month',pa.string()),
    ('price_per_m2_vnd',pa.float64()),('extreme_value_flag',pa.bool_())])


def convert_csv(csv_path,parquet_path):
    reader=csv.open_csv(csv_path,read_options=csv.ReadOptions(block_size=8*1024**2,use_threads=False),
                        convert_options=csv.ConvertOptions(column_types=SCHEMA,strings_can_be_null=True,null_values=['']))
    if reader.schema.names!=SCHEMA.names:
        reader.close(); raise ValueError('CSV không khớp schema phân tích 14 cột.')
    count=0
    try:
        with pq.ParquetWriter(parquet_path,reader.schema,compression='snappy') as writer:
            for batch in reader:
                writer.write_batch(batch,row_group_size=50_000); count+=batch.num_rows
    finally: reader.close()
    return count


if __name__=='__main__':
    import argparse,json,time
    p=argparse.ArgumentParser(); p.add_argument('--csv',required=True); p.add_argument('--output',required=True)
    a=p.parse_args(); start=time.perf_counter(); rows=convert_csv(a.csv,a.output)
    print(json.dumps(dict(rows=rows,conversion_s=time.perf_counter()-start)))
