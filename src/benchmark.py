"""Đo trong tiến trình riêng; kiểm tra cùng kết quả, ghi cả số đo thô."""
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import tempfile
import time
import shutil
import uuid
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import psutil
from src.prepare import ROOT
from src.queries import METHODS
from src.storage import sha256_file, write_json


def new_run_id():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]


def data_fingerprints(directory,sizes):
    import pyarrow.parquet as pq
    directory=Path(directory)
    manifest_path=directory/'manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else []
    output=[]
    for n in sizes:
        row=dict(rows=n)
        expected=next((m for m in manifest if m['rows']==n),{})
        for ext in ['csv','parquet']:
            path=directory/f'estate_{n}.{ext}'
            digest=sha256_file(path)
            if expected.get(ext+'_sha256',digest)!=digest:
                raise ValueError(f'Checksum tập benchmark thay đổi: {path.name}')
            row[ext]=dict(path=str(path),bytes=path.stat().st_size,sha256=digest)
        if pq.ParquetFile(directory/f'estate_{n}.parquet').metadata.num_rows!=n:
            raise ValueError('Số hàng Parquet không khớp nhãn mức dữ liệu.')
        output.append(row)
    return output


def archive_existing(output,directory,sizes):
    """Bảo toàn kết quả cũ một lần trước khi thay bộ mẫu đầu vào."""
    output=Path(output)
    if not (output/'runs.json').exists() or (output/'latest_run.json').exists() or (output/'.legacy_archived').exists():
        return
    archive=output/'history'/('legacy-'+new_run_id()); archive.mkdir(parents=True)
    for path in output.iterdir():
        if path.is_file() and not path.name.startswith('.'):
            shutil.copy2(path,archive/path.name)
    recorded=sorted(pd.read_csv(output/'summary.csv').rows.unique().astype(int).tolist()) if (output/'summary.csv').exists() else sizes
    try:
        fingerprints=data_fingerprints(directory,recorded)
    except (OSError,ValueError) as error:
        fingerprints=dict(unavailable=str(error))
    write_json(archive/'input_fingerprints.json',fingerprints)
    write_json(archive/'status.json',dict(status='ARCHIVED_LEGACY',note='Số đo có sẵn được bảo toàn; fingerprint chụp trước khi chuẩn bị lại dữ liệu.'))
    (output/'.legacy_archived').write_text(str(archive.relative_to(ROOT)),encoding='utf-8')


def equivalent(left, right, group_column='age_band'):
    if len(left) != len(right):
        return False
    keys=list(group_column) if isinstance(group_column,tuple) else [group_column]
    for a,b in zip(left,right):
        if set(a)!=set(b) or any(a[key]!=b[key] for key in keys): return False
        for key in a:
            if key in ['price_sum','mean_price','price_vnd','area_m2']:
                if not np.isclose(a[key],b[key],rtol=1e-9,atol=1e-6): return False
            elif a[key]!=b[key]: return False
    return True


def measure(method, n, chunksize, timeout=180, *, directory=None, dataset='uci', query='province', filters=None):
    directory = Path(directory) if directory is not None else ROOT / 'data/benchmark'
    cmd = [sys.executable, '-m', 'src.worker', '--method', method,
           '--csv', str(directory/f'estate_{n}.csv'),
           '--parquet', str(directory/f'estate_{n}.parquet'), '--chunksize', str(chunksize),
           '--dataset', dataset,'--query',query,'--filters-json',json.dumps(filters or {})]
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
               MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1', ARROW_NUM_THREADS='1')
    # Dùng file tạm thay PIPE: JSON nhiều nhóm có thể vượt pipe buffer và làm
    # worker kẹt khi parent còn đợi exit để đọc (đặc biệt trên Windows).
    with tempfile.TemporaryFile(mode='w+',encoding='utf-8',dir=ROOT/'results') as out_file, \
         tempfile.TemporaryFile(mode='w+',encoding='utf-8',dir=ROOT/'results') as err_file:
        process = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=out_file, stderr=err_file)
        monitor = psutil.Process(process.pid)
        peak, began = 0, time.monotonic()
        try:
            while process.poll() is None:
                try:
                    info = monitor.memory_info()
                    peak = max(peak, info.rss, getattr(info, 'peak_wset', 0))
                except psutil.NoSuchProcess:
                    pass
                if time.monotonic()-began > timeout or peak > 4*1024**3:
                    raise RuntimeError(f'{method}: vượt {timeout} giây hoặc 4 GiB; giảm kích thước dữ liệu.')
                time.sleep(.005)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
        out_file.seek(0); err_file.seek(0)
        stdout, stderr = out_file.read(), err_file.read()
        if process.returncode:
            raise RuntimeError(f'{method}: {stderr}')
    result = json.loads(stdout)
    result['peak_rss_mib'] = max(peak, result.pop('os_peak_bytes')) / 1024**2
    result['idle_rss_mib'] = result.pop('idle_rss_bytes') / 1024**2
    return result


def benchmark(sizes, repeats=3, chunksize=50_000, *, directory=None, output=None, dataset='uci',
              query='province',filters=None,methods=None):
    if repeats < 1 or chunksize < 1:
        raise ValueError('repeats và chunksize phải dương.')
    output = Path(output) if output is not None else ROOT / 'results'
    output.mkdir(parents=True, exist_ok=True)
    directory=Path(directory) if directory is not None else ROOT/'data/benchmark'
    methods=list(methods or METHODS)
    if 'csv_full' not in methods or set(methods)-set(METHODS) or len(set(methods))!=len(methods):
        raise ValueError('Các phương pháp phải duy nhất, hợp lệ và có csv_full làm baseline.')
    if dataset=='vietnam':
        from src.vietnam_queries import validate_filters,GROUPS
        filters=validate_filters(filters,query)
        if query not in GROUPS: raise ValueError('Truy vấn không hợp lệ.')
    archive_existing(output,directory,sizes)
    run_id=new_run_id(); run_dir=output/'history'/run_id; run_dir.mkdir(parents=True)
    config=dict(run_id=run_id,dataset=dataset,query=query,filters=filters or {},sizes=sizes,
                repeats=repeats,chunksize=chunksize,methods=methods,inputs=data_fingerprints(directory,sizes))
    write_json(run_dir/'config.json',config)
    if (directory/'manifest.json').exists():
        shutil.copy2(directory/'manifest.json',run_dir/'sample_manifest.json')
    if dataset=='vietnam' and directory.resolve()==(ROOT/'data/vietnam/benchmark').resolve():
        for path in [ROOT/'data/vietnam/processed/profile.json',ROOT/'data/vietnam/raw/source_metadata.json']:
            if path.exists(): shutil.copy2(path,run_dir/path.name)
    write_json(run_dir/'status.json',dict(status='RUNNING',completed_measurements=0))
    runs, reference = [], {}
    rng = random.Random(42)
    try:
        for n in sizes:
            for repetition in range(1, repeats+1):
                order=methods.copy(); rng.shuffle(order)
                for method in order:
                    row=measure(method,n,chunksize,directory=directory,dataset=dataset,query=query,filters=filters)
                    row.update(rows=n,method=method,repetition=repetition)
                    runs.append(row)
                    if method=='csv_full' and n not in reference: reference[n]=row['result']
                    write_json(run_dir/'runs.json',runs)
                    write_json(run_dir/'status.json',dict(status='RUNNING',completed_measurements=len(runs)))
                    print(f'{n:,} | {query} | {repetition}/{repeats} | {method}: {row["elapsed_s"]:.4f}s, {row["peak_rss_mib"]:.1f} MiB',flush=True)
    except BaseException as error:
        write_json(run_dir/'status.json',dict(status='FAILED',completed_measurements=len(runs),error=type(error).__name__+': '+str(error)))
        raise
    for row in runs:
        row['correct'] = equivalent(reference[row['rows']], row['result'],
                                    group_column=GROUPS[query] if dataset == 'vietnam' else 'age_band')
    write_json(run_dir/'runs.json',runs)
    if not all(r['correct'] for r in runs):
        write_json(run_dir/'status.json',dict(status='FAILED',error='Kết quả khác baseline.'))
        raise AssertionError('Có phương pháp cho kết quả khác baseline; không xuất báo cáo kết luận.')
    flat = pd.DataFrame([{k:v for k,v in r.items() if k != 'result'} for r in runs])
    flat.to_csv(run_dir/'measurements.csv', index=False)
    summary = flat.groupby(['rows', 'method']).agg(
        median_s=('elapsed_s', 'median'), min_s=('elapsed_s', 'min'), max_s=('elapsed_s', 'max'),
        median_peak_mib=('peak_rss_mib', 'median'), correct=('correct', 'all'), repeats=('repetition', 'count')).reset_index()
    base = summary.loc[summary.method == 'csv_full', ['rows', 'median_s', 'median_peak_mib']]
    summary = summary.merge(base.rename(columns={'median_s':'baseline_s','median_peak_mib':'baseline_mib'}), on='rows')
    summary['speedup'] = summary.baseline_s / summary.median_s
    summary['ram_reduction_pct'] = (1-summary.median_peak_mib/summary.baseline_mib)*100
    summary.to_csv(run_dir/'summary.csv', index=False)
    environment = dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
                       processor=platform.processor(), logical_cpus=psutil.cpu_count(),
                       total_ram_gib=psutil.virtual_memory().total/1024**3,
                       packages={p:importlib.metadata.version(p) for p in ['pandas','numpy','pyarrow','duckdb','psutil','matplotlib','openpyxl']},
                       sizes=sizes, repeats=repeats, chunksize=chunksize, dataset=dataset,query=query,filters=filters or {},run_id=run_id,
                       measured_utc=pd.Timestamp.now(tz='UTC').isoformat(),
                       notes='Fresh process each run; query includes read and aggregation; excludes interpreter startup/import pandas. OS cache not cleared. DuckDB lazy import and connection included. Windows peak working set includes process startup/imports. Other platforms: RSS polling 5ms may miss short peaks. Thread environment set to 1; actual Arrow IO scheduling may differ.')
    write_json(run_dir/'environment.json',environment)
    write_json(run_dir/'status.json',dict(status='SUCCESS',completed_measurements=len(runs),all_correct=True))
    # Chỉ công bố kết quả mới sau khi mọi kiểm tra đạt. Các lần cũ ở history.
    for name in ['runs.json','measurements.csv','summary.csv','environment.json','config.json']:
        temporary=output/(name+'.partial'); shutil.copy2(run_dir/name,temporary); temporary.replace(output/name)
    write_json(output/'latest_run.json',dict(run_id=run_id,path=str(run_dir.relative_to(ROOT)),status='SUCCESS'))
    return summary
