"""Gắn giới hạn trước khi import thư viện dữ liệu; chỉ giới hạn tiến trình con."""
import argparse
import gc
import json
import time


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--limit-mib',type=int,required=True)
    p.add_argument('--probe-mib',type=int)
    p.add_argument('--method'); p.add_argument('--csv'); p.add_argument('--parquet')
    p.add_argument('--query',default='province'); p.add_argument('--chunksize',type=int,default=50_000)
    p.add_argument('--filters-json',default='{}')
    a=p.parse_args(); phase='limit_setup'; limiter=None; reserve=None; started=None
    result=dict(limit_mib=a.limit_mib,query=a.query,method=a.method)
    try:
        from src.windows_limit import ProcessCommitLimit
        limiter=ProcessCommitLimit(a.limit_mib)
        result['limit_verified']=limiter.snapshot()
        reserve=bytearray(2*1024**2)
        if a.probe_mib is not None:
            phase='probe'
            allocation=bytearray(a.probe_mib*1024**2)
            result.update(status='SUCCESS',allocated_mib=len(allocation)/1024**2)
        else:
            phase='imports'
            import psutil
            from src.vietnam_queries import run_query
            result['idle_rss_mib']=psutil.Process().memory_info().rss/1024**2
            phase='query'; started=time.perf_counter()
            rows=run_query(a.method,a.csv,a.parquet,a.chunksize,query=a.query,filters=json.loads(a.filters_json),
                           duckdb_memory_mb=max(32,a.limit_mib//2))
            result.update(status='SUCCESS',elapsed_s=time.perf_counter()-started,result=rows)
            info=psutil.Process().memory_info()
            result['peak_rss_mib']=info.peak_wset/1024**2
            result['peak_private_commit_mib']=info.peak_pagefile/1024**2
    except Exception as error:
        reserve=None; gc.collect()
        message=str(error)[:1200]; name=type(error).__name__
        oom=isinstance(error,MemoryError) or name in ['ArrowMemoryError','OutOfMemoryException'] or any(
            phrase in message.lower() for phrase in ['out of memory','cannot allocate memory','not enough memory','failed to allocate'])
        result.update(status='OOM' if oom else 'SETUP_ERROR' if phase=='limit_setup' else 'ERROR',
                      phase=phase,error_type=name,error=message)
        if started is not None: result['failed_elapsed_s']=time.perf_counter()-started
    finally:
        reserve=None
        if limiter is not None: result['limit_verified']=limiter.snapshot()
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__': main()
