"""Mở rộng workload và chunk size; mọi phép đo dùng lại cơ chế đối chiếu."""
import pandas as pd
from src.benchmark import benchmark
from src.vietnam_data import ROOT


def expanded_experiments(rows=1_000_000,repeats=3,chunk_sizes=(10_000,50_000,100_000)):
    directory=ROOT/'data/vietnam/benchmark'; output=ROOT/'results/vietnam/experiments'
    summaries=[]
    for query in ['month','top_types']:
        summary=benchmark([rows],repeats,directory=directory,output=output/query,dataset='vietnam',query=query)
        summaries.append(summary.assign(experiment='workload',query=query,chunksize=50_000))
    for chunk in chunk_sizes:
        summary=benchmark([rows],repeats,chunk,directory=directory,output=output/f'chunk_{chunk}',
                          dataset='vietnam',query='province',methods=['csv_full','csv_chunk'])
        summaries.append(summary.assign(experiment='chunk_size',query='province',chunksize=chunk))
    combined=pd.concat(summaries,ignore_index=True)
    temp=output/'expanded_summary.csv.partial'; combined.to_csv(temp,index=False); temp.replace(output/'expanded_summary.csv')
    return combined
