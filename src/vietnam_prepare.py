"""Làm sạch theo Arrow batch; lấy mẫu và tổng hợp bằng DuckDB có vùng tràn đĩa."""
import json
import tempfile
import time
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from src.vietnam_data import ROOT, COLUMNS
from src.storage import sha256_file, write_json

RENAMES={'price':'price_vnd','area':'area_m2'}
OPTIONAL=['floor_count','bedroom_count','bathroom_count']


def clean_vietnam(frame,source_shard,row_offset=0,return_rejected=False):
    original=frame.copy().reset_index(drop=True)
    raw=original.copy()
    core=['price','area','province_name','property_type_name']
    for col in ['price','area']+OPTIONAL:
        raw[col]=pd.to_numeric(raw[col],errors='coerce')
    for col in ['province_name','property_type_name','district_name']:
        raw[col]=raw[col].astype('string').str.strip().replace('',pd.NA)
    missing=raw[core].isna().any(axis=1)
    invalid=(~np.isfinite(raw.price)|~np.isfinite(raw.area)|(raw.price<=0)|(raw.area<=0)) & ~missing
    optional_bad=pd.DataFrame({col:(~np.isfinite(raw[col])|(raw[col]<0)|(raw[col]%1!=0)) & raw[col].notna() for col in OPTIONAL})
    for col in OPTIONAL:
        raw.loc[optional_bad[col],col]=np.nan
    raw.insert(0,'source_row',np.arange(row_offset,row_offset+len(raw),dtype='int64'))
    raw.insert(0,'source_shard',source_shard)
    good=raw.loc[~(missing|invalid)].rename(columns=RENAMES).copy()
    dates=pd.to_datetime(good.published_at,format='ISO8601',errors='coerce')
    good['published_month']=dates.dt.strftime('%Y-%m').astype('string')
    good['price_per_m2_vnd']=good.price_vnd/good.area_m2
    good['extreme_value_flag']=(good.price_vnd>1e12)|(good.area_m2>10000)
    audit=dict(source_shard=source_shard,raw_rows=len(raw),missing_core_rows=int(missing.sum()),
               invalid_core_rows=int(invalid.sum()),optional_values_set_null=int(optional_bad.to_numpy().sum()),
               clean_rows=len(good),invalid_publication_dates=int(dates.isna().sum()),extreme_value_flags=int(good.extreme_value_flag.sum()))
    if not return_rejected:
        return good.reset_index(drop=True),audit
    reasons=pd.Series('',index=raw.index,dtype='string')
    for col in core:
        mask=raw[col].isna()
        reasons.loc[mask] += 'missing_or_unparseable:'+col+';'
    for col in ['price','area']:
        mask=raw[col].notna() & (~np.isfinite(raw[col])|(raw[col]<=0))
        reasons.loc[mask] += 'non_positive_or_non_finite:'+col+';'
    rejected=original.loc[missing|invalid].copy()
    rejected.insert(0,'source_row',raw.loc[missing|invalid,'source_row'])
    rejected.insert(0,'source_shard',source_shard)
    rejected['rejection_reason']=reasons.loc[missing|invalid].str.rstrip(';')
    return good.reset_index(drop=True),audit,rejected


def database(temp_dir,memory_mb=256):
    return duckdb.connect(config={'memory_limit':f'{memory_mb}MB','threads':1,'temp_directory':str(temp_dir)})


def write_samples(clean_path,out_dir,sizes,seed=42,batch_size=50_000,memory_mb=256):
    """Thứ tự băm xác định theo ID nguồn; các mẫu là tiền tố không hoàn lại.

    Không nạp bảng sạch hoặc toàn bộ mẫu vào DataFrame. DuckDB có thể tràn
    các trung gian ORDER BY ra đĩa; Arrow chuyển tối đa batch_size hàng mỗi lần.
    """
    out_dir=Path(out_dir); out_dir.mkdir(parents=True,exist_ok=True)
    sizes=sorted(set(sizes))
    if not sizes or min(sizes)<1 or batch_size<1:
        raise ValueError('Kích thước mẫu và batch phải dương.')
    with tempfile.TemporaryDirectory(dir=out_dir,prefix='sample-') as temp:
        with database(Path(temp)/'spill',memory_mb) as con:
            count=con.execute('SELECT COUNT(*) FROM read_parquet(?)',[str(clean_path)]).fetchone()[0]
            if count<max(sizes):
                raise ValueError(f'Chỉ có {count:,} hàng sạch; không sinh dữ liệu bù.')
            reader=con.execute('''SELECT * FROM read_parquet(?)
                ORDER BY hash(source_shard,source_row,CAST(? AS BIGINT)),source_shard,source_row LIMIT ?''',
                [str(clean_path),seed,max(sizes)]).to_arrow_reader(batch_size)
            writers={}; timings={n:[0.,0.] for n in sizes}; position=0
            try:
                for batch in reader:
                    frame=batch.to_pandas()
                    for n in sizes:
                        take=min(len(frame),max(0,n-position))
                        if not take: continue
                        csv=Path(temp)/f'estate_{n}.csv'; parquet=Path(temp)/f'estate_{n}.parquet'
                        start=time.perf_counter()
                        frame.iloc[:take].to_csv(csv,index=False,mode='w' if position==0 else 'a',header=position==0)
                        timings[n][0]+=time.perf_counter()-start
                        start=time.perf_counter()
                        table=pa.Table.from_batches([batch.slice(0,take)])
                        if n not in writers:
                            writers[n]=pq.ParquetWriter(parquet,table.schema,compression='snappy')
                        writers[n].write_table(table,row_group_size=batch_size)
                        timings[n][1]+=time.perf_counter()-start
                    position+=len(frame)
            finally:
                for n,writer in writers.items():
                    start=time.perf_counter(); writer.close(); timings[n][1]+=time.perf_counter()-start
        manifest=[]
        for n in sizes:
            csv=Path(temp)/f'estate_{n}.csv'; parquet=Path(temp)/f'estate_{n}.parquet'
            if pq.ParquetFile(parquet).metadata.num_rows!=n:
                raise AssertionError('Mẫu không đủ số hàng.')
            manifest.append(dict(rows=n,csv_bytes=csv.stat().st_size,parquet_bytes=parquet.stat().st_size,
                                 csv_write_s=timings[n][0],parquet_write_s=timings[n][1],seed=seed,
                                 sampler='duckdb_hash_order_v1',duckdb_version=duckdb.__version__,batch_size=batch_size,
                                 csv_sha256=sha256_file(csv),parquet_sha256=sha256_file(parquet)))
        for item in manifest:
            for ext in ['csv','parquet']:
                name=f'estate_{item["rows"]}.{ext}'
                (Path(temp)/name).replace(out_dir/name)
        write_json(out_dir/'manifest.json',manifest)
    return manifest


def prepare_vietnam(sizes=(100_000,500_000,1_000_000),seed=42,batch_size=50_000,memory_mb=256):
    if not sizes or min(sizes)<1 or batch_size<1 or memory_mb<64:
        raise ValueError('Mẫu/batch phải dương; ngân sách DuckDB tối thiểu 64 MB.')
    raw_dir=ROOT/'data/vietnam/raw'; files=sorted(raw_dir.glob('projection_*.parquet'))
    if not files: raise FileNotFoundError('Tải nguồn bằng python -m src.vietnam_data --shards 4 trước.')
    source=json.loads((raw_dir/'source_metadata.json').read_text(encoding='utf-8'))
    clean_dir=ROOT/'data/vietnam/processed'; clean_dir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=clean_dir,prefix='prepare-') as temporary:
        stage=Path(temporary); clean_path=stage/'vietnam_clean.parquet'
        writer=None; audits=[]; before=dict.fromkeys(COLUMNS,0); after={}; error_header=True; preview_remaining=1000
        try:
            for path in files:
                entry=next((x for x in source['shards'] if x['file']==path.name),None)
                if not entry or sha256_file(path)!=entry['sha256']:
                    raise ValueError(f'Checksum không khớp: {path.name}')
                parquet=pq.ParquetFile(path)
                missing=set(COLUMNS)-set(parquet.schema_arrow.names)
                if missing: raise ValueError(f'Thiếu cột trong {path.name}: {missing}')
                offset=0; total_audit=None
                for batch in parquet.iter_batches(batch_size=batch_size,columns=COLUMNS,use_threads=False):
                    raw=batch.to_pandas()
                    for col in COLUMNS: before[col]+=int(raw[col].isna().sum())
                    good,audit,rejected=clean_vietnam(raw,entry['source_file'],offset,True)
                    offset+=len(raw)
                    if total_audit is None: total_audit=audit.copy()
                    else:
                        for key in audit:
                            if key!='source_shard': total_audit[key]+=audit[key]
                    for col in good.columns: after[col]=after.get(col,0)+int(good[col].isna().sum())
                    if len(good):
                        table=pa.Table.from_pandas(good,preserve_index=False)
                        if writer is None: writer=pq.ParquetWriter(clean_path,table.schema,compression='snappy')
                        writer.write_table(table,row_group_size=batch_size)
                        if preview_remaining:
                            take=min(preview_remaining,len(good))
                            good.head(take).to_csv(stage/'vietnam_preview_1000.csv',index=False,mode='w' if preview_remaining==1000 else 'a',header=preview_remaining==1000,encoding='utf-8-sig' if preview_remaining==1000 else 'utf-8')
                            preview_remaining-=take
                    # Ghi cả header khi chưa có lỗi, để đầu ra luôn có schema.
                    if error_header or len(rejected):
                        rejected.to_csv(stage/'rejected_rows.csv',index=False,mode='w' if error_header else 'a',header=error_header,encoding='utf-8-sig' if error_header else 'utf-8')
                        error_header=False
                audits.append(total_audit)
                print(f'{path.name}: {offset:,} → {total_audit["clean_rows"]:,} hàng, batch={batch_size:,}.',flush=True)
        finally:
            if writer is not None: writer.close()
        count=sum(a['clean_rows'] for a in audits)
        if count<max(sizes): raise ValueError(f'Chỉ có {count:,} hàng sạch; giảm mức mẫu hoặc tải thêm nguồn.')
        with database(stage/'spill',memory_mb) as con:
            fields=['property_type_name','province_name','district_name','price_vnd','area_m2']+OPTIONAL+['published_at']
            duplicate=int(con.execute('SELECT COALESCE(SUM(n-1),0) FROM (SELECT COUNT(*) n FROM read_parquet(?) GROUP BY '+','.join(fields)+')',[str(clean_path)]).fetchone()[0])
            types=dict(con.execute('SELECT property_type_name,COUNT(*) FROM read_parquet(?) GROUP BY 1',[str(clean_path)]).fetchall())
            labels,first,last=con.execute('SELECT COUNT(DISTINCT province_name),MIN(published_month),MAX(published_month) FROM read_parquet(?)',[str(clean_path)]).fetchone()
            # Chỉ kết quả nhóm nhỏ được fetchdf, không phải bảng dữ liệu nguồn.
            con.execute('SELECT province_name,property_type_name,COUNT(*) listing_rows FROM read_parquet(?) GROUP BY 1,2 ORDER BY 1,2',[str(clean_path)]).fetchdf().to_csv(stage/'listing_counts.csv',index=False,encoding='utf-8-sig')
        profile=dict(raw_rows=sum(a['raw_rows'] for a in audits),clean_rows=count,
                     removed_missing_core=sum(a['missing_core_rows'] for a in audits),removed_invalid_core=sum(a['invalid_core_rows'] for a in audits),
                     missing_by_column=before,missing_after=after,duplicate_projection_rows=duplicate,
                     duplicate_policy='Giữ chữ ký 9 cột lặp vì không có ID tin/bất động sản để xác nhận trùng.',
                     province_labels=labels,property_types=types,first_month=first,last_month=last,per_shard=audits,
                     benchmark_seed=seed,benchmark_sizes=list(sizes),batch_size=batch_size,duckdb_memory_mb=memory_mb,
                     sampler='duckdb_hash_order_v1',preparation='Arrow batch + DuckDB với vùng tràn đĩa; không nạp toàn bảng sạch vào Pandas.',
                     scope='Các shard theo thứ tự tên; mẫu benchmark theo thứ tự hash của ID hàng nguồn và seed, không hoàn lại.')
        quality=[]
        for col in COLUMNS:
            target=RENAMES.get(col,col)
            quality.append(dict(source_column=col,clean_column=target,raw_rows=profile['raw_rows'],clean_rows=count,
                                missing_before=before[col],missing_after=after.get(target,0),
                                missing_before_pct=100*before[col]/profile['raw_rows'],missing_after_pct=100*after.get(target,0)/count))
        pd.DataFrame(quality).to_csv(stage/'quality_before_after.csv',index=False,encoding='utf-8-sig')
        write_json(stage/'profile.json',profile)
        write_samples(clean_path,ROOT/'data/vietnam/benchmark',sizes,seed,batch_size,memory_mb)
        for name in ['vietnam_clean.parquet','vietnam_preview_1000.csv','listing_counts.csv','rejected_rows.csv','quality_before_after.csv','profile.json']:
            (stage/name).replace(clean_dir/name)
    return profile
