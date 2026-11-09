"""Demo nhanh một truy vấn, không chạy lại toàn bộ benchmark."""
import argparse
import json
import time
from src.prepare import ROOT
from src.queries import METHODS, run_query

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--method', choices=METHODS+['duckdb_csv'], default='duckdb_parquet')
p.add_argument('--rows', type=int, default=1_000_000)
p.add_argument('--dataset', choices=['uci','vietnam'], default='uci')
p.add_argument('--query',choices=['province','month','top_types','province_type','top100'],default='province')
p.add_argument('--province'); p.add_argument('--property-type')
p.add_argument('--area-min',type=float); p.add_argument('--area-max',type=float)
p.add_argument('--price-min',type=float); p.add_argument('--price-max',type=float)
a=p.parse_args()
filters={key:getattr(a,key) for key in ['province','property_type','area_min','area_max','price_min','price_max'] if getattr(a,key) is not None}
if a.dataset=='uci' and (filters or a.query!='province' or a.method=='duckdb_csv'):
    p.error('Các điều kiện tùy chọn và truy vấn mới dành cho --dataset vietnam.')
directory=ROOT/('data/vietnam/benchmark' if a.dataset == 'vietnam' else 'data/benchmark')
csv_path=directory/f'estate_{a.rows}.csv'
parquet_path=directory/f'estate_{a.rows}.parquet'
if not csv_path.exists() or not parquet_path.exists():
    runner='run_vietnam.py' if a.dataset == 'vietnam' else 'run_project.py'
    p.error(f'Chưa có dữ liệu mức này. Chạy {runner} --sizes <số dòng> trước.')
query=run_query
if a.dataset == 'vietnam':
    from src.vietnam_queries import run_query as query
    from src.vietnam_queries import validate_filters
    try: filters=validate_filters(filters,a.query)
    except ValueError as error: p.error(str(error))
start=time.perf_counter()
kwargs=dict(query=a.query,filters=filters) if a.dataset=='vietnam' else {}
result=query(a.method,csv_path,parquet_path,**kwargs)
print(json.dumps(result,ensure_ascii=False,indent=2))
print(f'Thoi gian doc va truy van: {time.perf_counter()-start:.4f} giay')
