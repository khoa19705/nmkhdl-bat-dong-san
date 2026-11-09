"""Mỗi phép đo chạy trong tiến trình mới; stdout chỉ chứa một JSON."""
import argparse
import json
import time
import psutil
from src.queries import run_query


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--method', required=True)
    p.add_argument('--csv', required=True)
    p.add_argument('--parquet', required=True)
    p.add_argument('--chunksize', type=int, default=50_000)
    p.add_argument('--dataset', choices=['uci', 'vietnam'], default='uci')
    p.add_argument('--query', default='province')
    p.add_argument('--filters-json', default='{}')
    a = p.parse_args()
    query = run_query
    if a.dataset == 'vietnam':
        from src.vietnam_queries import run_query as query
    process = psutil.Process()
    idle = process.memory_info().rss
    start = time.perf_counter()
    kwargs=dict(query=a.query,filters=json.loads(a.filters_json)) if a.dataset=='vietnam' else {}
    result = query(a.method, a.csv, a.parquet, a.chunksize, **kwargs)
    elapsed = time.perf_counter()-start
    info = process.memory_info()
    print(json.dumps(dict(elapsed_s=elapsed, idle_rss_bytes=idle,
                         os_peak_bytes=getattr(info, 'peak_wset', 0), result=result)))


if __name__ == '__main__':
    main()
