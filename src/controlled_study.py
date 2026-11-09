"""Đo tiến trình với hạn mức commit Windows; lỗi là kết quả, không dừng cả bảng."""
import json
import os
from pathlib import Path
import random
import platform
import importlib.metadata
import shutil
import subprocess
import sys
import tempfile
import time
import pandas as pd
import psutil
from src.vietnam_data import ROOT
from src.vietnam_queries import GROUPS,validate_filters
from src.queries import METHODS
from src.benchmark import equivalent,data_fingerprints,new_run_id
from src.storage import write_json


def limited_call(arguments,timeout=60):
    env=dict(os.environ,PYTHONUTF8='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
             MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',ARROW_NUM_THREADS='1')
    with tempfile.TemporaryFile(mode='w+',encoding='utf-8',dir=ROOT/'results') as out, \
         tempfile.TemporaryFile(mode='w+',encoding='utf-8',dir=ROOT/'results') as err:
        process=subprocess.Popen([sys.executable,'-m','src.limited_worker']+arguments,cwd=ROOT,env=env,stdout=out,stderr=err)
        monitor=psutil.Process(process.pid); start=time.monotonic(); peak_rss=peak_private=0; timed_out=False
        try:
            while process.poll() is None:
                try:
                    info=monitor.memory_info()
                    peak_rss=max(peak_rss,info.rss,getattr(info,'peak_wset',0))
                    peak_private=max(peak_private,getattr(info,'peak_pagefile',getattr(info,'private',0)))
                except psutil.NoSuchProcess: pass
                if time.monotonic()-start>timeout:
                    timed_out=True; process.kill(); break
                time.sleep(.005)
        finally:
            if process.poll() is None: process.kill()
            process.wait()
        wall=time.monotonic()-start; out.seek(0); err.seek(0)
        stdout,stderr=out.read(),err.read()
    if timed_out: result=dict(status='TIMEOUT',error=f'Vượt {timeout} giây từ khởi động tiến trình.')
    elif process.returncode:
        result=dict(status='NATIVE_ERROR',exit_code=process.returncode,error=stderr[-2000:])
    else:
        try: result=json.loads(stdout)
        except json.JSONDecodeError: result=dict(status='INVALID_OUTPUT',error=stderr[-2000:] or stdout[-2000:])
    result['wall_s']=wall
    # Mẫu lấy từ tiến trình cha có thể bỏ lỡ đỉnh hoặc không đọc được lúc con crash.
    # Giữ riêng cận dưới quan sát được; chỉ con hoàn thành mới báo high-water RSS.
    result['sampled_peak_rss_lower_bound_mib']=peak_rss/1024**2
    result['sampled_peak_commit_lower_bound_mib']=peak_private/1024**2
    result['verified_peak_commit_mib']=result.get('limit_verified',{}).get('peak_commit_bytes',None)
    if result['verified_peak_commit_mib'] is not None: result['verified_peak_commit_mib']/=1024**2
    return result


def summarize_runs(runs):
    flat=pd.DataFrame([{k:v for k,v in row.items() if k not in ['result','limit_verified']} for row in runs])
    summaries=[]
    for (budget,query,method),group in flat.groupby(['limit_mib','query','method']):
        good=group[group.status=='SUCCESS']
        verified=[r['limit_verified']['peak_commit_bytes']/1024**2 for r in runs
                  if (r['limit_mib'],r['query'],r['method'])==(budget,query,method)
                  and 'peak_commit_bytes' in r.get('limit_verified',{})]
        summaries.append(dict(limit_mib=int(budget),query=query,method=method,attempts=len(group),
            success=len(good),oom=int((group.status=='OOM').sum()),timeout=int((group.status=='TIMEOUT').sum()),
            other_errors=int((~group.status.isin(['SUCCESS','OOM','TIMEOUT'])).sum()),
            median_success_s=float(good.elapsed_s.median()) if len(good) else None,
            max_success_peak_rss_mib=float(good.peak_rss_mib.max()) if len(good) else None,
            max_verified_peak_commit_mib=max(verified) if verified else None,
            verified_commit_cases=len(verified)))
    return pd.DataFrame(summaries)


def controls(budgets):
    results=[]
    for budget in budgets:
        for allocation,expected in [(32,'SUCCESS'),(budget+64,'OOM')]:
            result=limited_call(['--limit-mib',str(budget),'--probe-mib',str(allocation)])
            result.update(allocation_mib=allocation,expected=expected,limit_mib=budget)
            result['passed']=result['status']==expected and result.get('limit_verified',{}).get('enabled',False)
            results.append(result)
    if not all(r['passed'] for r in results):
        raise RuntimeError('Đối chứng giới hạn bộ nhớ không đạt: '+json.dumps(results,ensure_ascii=False))
    return results


def run_memory_study(rows=1_000_000,repeats=3,budgets=(256,512)):
    if os.name!='nt': raise NotImplementedError('Thí nghiệm commit Job Object cần Windows.')
    base=ROOT/'results/vietnam/memory_limits'; run=base/'history'/new_run_id(); run.mkdir(parents=True)
    directory=ROOT/'data/vietnam/benchmark'; inputs=data_fingerprints(directory,[rows])
    write_json(run/'config.json',dict(rows=rows,repeats=repeats,budgets_mib=list(budgets),inputs=inputs,
                python=sys.version,platform=platform.platform(),total_ram_gib=psutil.virtual_memory().total/1024**3,
                packages={name:importlib.metadata.version(name) for name in ['pandas','pyarrow','duckdb','psutil']},
                metric='OS-enforced per-process committed virtual memory, before data-library imports; includes runtime.',
                duckdb_internal_budget='floor(OS limit / 2) MB; threads=1; outer OS cap applies equally to all methods.',
                timeout_s=60,cache='OS cache not cleared',queries=['province','top100']))
    write_json(run/'status.json',dict(status='RUNNING'))
    try:
        checks=controls(budgets); write_json(run/'controls.json',checks)
        references={}
        for query,path in [('province',ROOT/'results/vietnam/runs.json'),
                           ('top100',ROOT/'results/vietnam/workloads/top100/runs.json')]:
            saved=json.loads(path.read_text(encoding='utf-8'))
            references[query]=next(x['result'] for x in saved if x['rows']==rows and x['method']=='csv_full')
        jobs=[(budget,query,rep,method) for budget in budgets for query in references for rep in range(1,repeats+1) for method in METHODS]
        random.Random(42).shuffle(jobs); runs=[]
        for budget,query,rep,method in jobs:
            filters=validate_filters(None,query)
            args=['--limit-mib',str(budget),'--query',query,'--method',method,
                  '--csv',str(directory/f'estate_{rows}.csv'),'--parquet',str(directory/f'estate_{rows}.parquet'),
                  '--filters-json',json.dumps(filters)]
            result=limited_call(args)
            result.update(limit_mib=budget,query=query,method=method,repetition=rep,rows=rows)
            if result['status']=='SUCCESS':
                result['correct']=equivalent(references[query],result['result'],GROUPS[query])
                if not result['correct']: result['status']='WRONG_RESULT'
            else: result['correct']=None
            runs.append(result); write_json(run/'runs.json',runs)
            write_json(run/'status.json',dict(status='RUNNING',completed=len(runs)))
            print(f'Commit {budget} MiB | {query} | {method} | {rep}/{repeats}: {result["status"]}',flush=True)
        flat=pd.DataFrame([{k:v for k,v in row.items() if k not in ['result','limit_verified']} for row in runs])
        flat.to_csv(run/'measurements.csv',index=False)
        summary=summarize_runs(runs)
        summary.to_csv(run/'summary.csv',index=False)
        if any(r['status'] in ['SETUP_ERROR','WRONG_RESULT','INVALID_OUTPUT'] for r in runs):
            raise RuntimeError('Có lỗi thiết lập hoặc tính đúng; không công bố kết luận thí nghiệm giới hạn.')
        write_json(run/'status.json',dict(status='SUCCESS',attempts=len(runs),controls_passed=True,
                                         note='OOM/TIMEOUT/NATIVE_ERROR là kết quả từng ca, không tự coi là sai dữ liệu.'))
        for name in ['config.json','controls.json','runs.json','measurements.csv','summary.csv']:
            temp=base/(name+'.partial'); shutil.copy2(run/name,temp); temp.replace(base/name)
        write_json(base/'latest_run.json',dict(path=run.relative_to(ROOT).as_posix(),status='SUCCESS'))
    except BaseException as error:
        write_json(run/'status.json',dict(status='FAILED',error=type(error).__name__+': '+str(error)))
        raise
    return summary
