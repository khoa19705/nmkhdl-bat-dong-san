"""Đo chi phí chuyển đổi và truy vấn lặp, sau đó mô hình hóa điểm hòa vốn."""
import importlib.metadata
import json
import math
from pathlib import Path
import random
import platform
import shutil
import subprocess
import sys
import time
import duckdb
import pandas as pd
import pyarrow as pa
import psutil
from src.vietnam_data import ROOT
from src.vietnam_queries import run_query,GROUPS,validate_filters
from src.benchmark import new_run_id,data_fingerprints,equivalent
from src.storage import write_json,sha256_file
from src.conversion import SCHEMA


def first_profitable_query(conversion_s,csv_s,target_s):
    if any(not math.isfinite(value) or value<0 for value in [conversion_s,csv_s,target_s]):
        raise ValueError('Các thời gian phải hữu hạn và không âm.')
    saving=csv_s-target_s
    return math.floor(conversion_s/saving)+1 if saving>0 else None


def content_fingerprint(path):
    # Hash trên kiểu phân tích chuẩn, tránh so hash int(50) với double(50.0).
    def sql_type(field):
        return 'BIGINT' if pa.types.is_integer(field.type) else 'DOUBLE' if pa.types.is_floating(field.type) else 'BOOLEAN' if pa.types.is_boolean(field.type) else 'VARCHAR'
    fields=','.join(f'CAST({field.name} AS {sql_type(field)})' for field in SCHEMA)
    with duckdb.connect(config={'threads':1,'memory_limit':'256MB'}) as con:
        return con.execute(f'SELECT COUNT(*),bit_xor(hash({fields})) FROM read_parquet(?)',[str(path)]).fetchone()


def run_break_even(rows=1_000_000,repeats=5,conversion_repeats=3):
    base=ROOT/'results/vietnam/break_even'; run=base/'history'/new_run_id(); run.mkdir(parents=True)
    directory=ROOT/'data/vietnam/benchmark'; csv=directory/f'estate_{rows}.csv'; original=directory/f'estate_{rows}.parquet'
    write_json(run/'config.json',dict(rows=rows,query_repeats=repeats,conversion_repeats=conversion_repeats,
        python=sys.version,platform=platform.platform(),total_ram_gib=psutil.virtual_memory().total/1024**3,
        inputs=data_fingerprints(directory,[rows]),queries=['province','top100'],
        packages={name:importlib.metadata.version(name) for name in ['pandas','pyarrow','duckdb']},
        timing='Conversion includes open/read CSV, typed parse, Snappy Parquet write and writer close; excludes Python startup/imports and correctness validation. Known analytic schema. No fsync or cold-cache guarantee.',
        session='One discarded warmup per method/query, then interleaved repetitions in one process. Rereads files per query, does not cache a DataFrame; connection creation included.'))
    write_json(run/'status.json',dict(status='RUNNING'))
    try:
        conversions=[]; expected=content_fingerprint(original)
        for rep in range(1,conversion_repeats+1):
            target=run/'converted.parquet'
            completed=subprocess.run([sys.executable,'-m','src.conversion','--csv',str(csv),'--output',str(target)],
                                     cwd=ROOT,capture_output=True,text=True,check=True,timeout=180)
            result=json.loads(completed.stdout)
            if result['rows']!=rows or content_fingerprint(target)!=expected:
                raise AssertionError('Chuyển đổi không giữ nội dung của 14 cột.')
            conversions.append(result|dict(repetition=rep,content_fingerprint=list(expected),correct=True))
            write_json(run/'conversions.json',conversions)
            print(f'CSV → Parquet {rep}/{conversion_repeats}: {result["conversion_s"]:.4f}s',flush=True)
        costs=pd.DataFrame(conversions); costs.to_csv(run/'conversion_cost.csv',index=False)
        conversion_s=float(costs.conversion_s.median())
        methods=['csv_columns','csv_typed','duckdb_csv','parquet_columns','duckdb_parquet']; measurements=[]
        rng=random.Random(42)
        for query in ['province','top100']:
            filters=validate_filters(None,query)
            reference=run_query('csv_full',csv,target,query=query,filters=filters)
            for method in methods:
                warm=run_query(method,csv,target,query=query,filters=filters)
                if not equivalent(reference,warm,GROUPS[query]): raise AssertionError('Warmup khác kết quả.')
            for rep in range(1,repeats+1):
                order=methods.copy(); rng.shuffle(order)
                for method in order:
                    start=time.perf_counter(); output=run_query(method,csv,target,query=query,filters=filters)
                    elapsed=time.perf_counter()-start
                    correct=equivalent(reference,output,GROUPS[query])
                    measurements.append(dict(query=query,method=method,repetition=rep,elapsed_s=elapsed,correct=correct))
                    if not correct: raise AssertionError('Truy vấn lặp khác kết quả.')
                print(f'Truy vấn lặp {query}: {rep}/{repeats}',flush=True)
        measured=pd.DataFrame(measurements); measured.to_csv(run/'query_measurements.csv',index=False)
        times=measured.groupby(['query','method']).agg(median_s=('elapsed_s','median'),min_s=('elapsed_s','min'),max_s=('elapsed_s','max'),repeats=('elapsed_s','size')).reset_index()
        times.to_csv(run/'query_times.csv',index=False)
        estimates=[]; models=[]
        for query in ['province','top100']:
            subset=times[times['query']==query].set_index('method')
            for csv_method in ['csv_columns','csv_typed','duckdb_csv']:
                csv_s=float(subset.loc[csv_method,'median_s'])
                for method in ['parquet_columns','duckdb_parquet']:
                    target_s=float(subset.loc[method,'median_s'])
                    first=first_profitable_query(conversion_s,csv_s,target_s)
                    estimates.append(dict(query=query,csv_baseline=csv_method,target=method,
                        conversion_s=conversion_s,csv_query_s=csv_s,target_query_s=target_s,
                        saved_s_per_query=csv_s-target_s,first_strictly_faster_n=first))
                    for n in [1,2,5,10,20,50]:
                        models.append(dict(query=query,csv_baseline=csv_method,target=method,n=n,
                                           modeled_csv_s=n*csv_s,modeled_converted_s=conversion_s+n*target_s))
        pd.DataFrame(estimates).to_csv(run/'break_even.csv',index=False)
        pd.DataFrame(models).to_csv(run/'modeled_totals.csv',index=False)
        write_json(run/'converted_file.json',dict(path=target.relative_to(ROOT).as_posix(),bytes=target.stat().st_size,
                                                 sha256=sha256_file(target),content_fingerprint=list(expected)))
        write_json(run/'status.json',dict(status='SUCCESS',all_correct=True,query_measurements=len(measurements)))
        for name in ['config.json','conversion_cost.csv','query_measurements.csv','query_times.csv','break_even.csv','modeled_totals.csv','converted_file.json']:
            temp=base/(name+'.partial'); shutil.copy2(run/name,temp); temp.replace(base/name)
        write_json(base/'latest_run.json',dict(path=run.relative_to(ROOT).as_posix(),status='SUCCESS'))
    except BaseException as error:
        write_json(run/'status.json',dict(status='FAILED',error=type(error).__name__+': '+str(error)))
        raise
    return pd.DataFrame(estimates)
