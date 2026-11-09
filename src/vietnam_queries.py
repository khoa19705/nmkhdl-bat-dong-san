"""Truy vấn Việt Nam có điều kiện chung cho Pandas, chunk và DuckDB."""
import math
import pandas as pd

DEFAULT_FILTERS = dict(area_min=50., area_max=150., price_min=1., price_max=10_000_000_000.,
                       province=None, property_type=None)
GROUPS = {'province':'province_name', 'month':'published_month', 'top_types':'property_type_name',
          'province_type':('province_name','property_type_name'),'top100':('source_shard','source_row')}
TOP_COLUMNS=['source_shard','source_row','province_name','property_type_name','price_vnd','area_m2']


def validate_filters(filters=None,query='province'):
    supplied = filters or {}
    if set(supplied)-set(DEFAULT_FILTERS):
        raise ValueError('Tên điều kiện không hợp lệ.')
    defaults=DEFAULT_FILTERS | dict(area_min=0.,area_max=1e308,price_min=0.,price_max=1e308) if query=='top100' else DEFAULT_FILTERS
    result = defaults | supplied
    for key in ['area_min','area_max','price_min','price_max']:
        result[key] = float(result[key])
        if not math.isfinite(result[key]) or result[key] < 0:
            raise ValueError(f'{key} phải là số hữu hạn không âm.')
    if result['area_min'] > result['area_max'] or result['price_min'] > result['price_max']:
        raise ValueError('Cận dưới phải nhỏ hơn hoặc bằng cận trên.')
    for key in ['province','property_type']:
        value=result[key]
        if value is not None and not isinstance(value,str):
            raise ValueError(f'{key} phải là chuỗi.')
        result[key] = (value.strip() or None) if value is not None else None
    return result


def sql_conditions(filters=None):
    f=validate_filters(filters)
    where=['area_m2 BETWEEN ? AND ?', 'price_vnd BETWEEN ? AND ?']
    params=[f['area_min'],f['area_max'],f['price_min'],f['price_max']]
    for key,column in [('province','province_name'),('property_type','property_type_name')]:
        if f[key] is not None:
            where.append(column+' = ?'); params.append(f[key])
    return ' AND '.join(where),params


def select_columns(query, filters):
    if query not in GROUPS:
        raise ValueError(f'Truy vấn không hợp lệ: {query}')
    groups=GROUPS[query]
    groups=list(groups) if isinstance(groups,tuple) else [groups]
    columns=TOP_COLUMNS.copy() if query=='top100' else ['price_vnd','area_m2']+groups
    for key,col in [('province','province_name'),('property_type','property_type_name')]:
        if filters[key] is not None:
            columns.append(col)
    return list(dict.fromkeys(columns))


def filtered(frame,filters=None):
    f=validate_filters(filters)
    mask=frame.area_m2.between(f['area_min'],f['area_max']) & frame.price_vnd.between(f['price_min'],f['price_max'])
    if f['province'] is not None:
        mask &= frame.province_name == f['province']
    if f['property_type'] is not None:
        mask &= frame.property_type_name == f['property_type']
    return frame.loc[mask]


def aggregate(frame, query='province', filters=None):
    groups=GROUPS[query]
    groups=list(groups) if isinstance(groups,tuple) else groups
    return filtered(frame,filters).groupby(groups, observed=True, dropna=True).agg(
        count=('price_vnd','size'),price_sum=('price_vnd','sum'))


def records(grouped, query='province'):
    group=GROUPS[query]
    keys=list(group) if isinstance(group,tuple) else [group]
    output=[]
    for label,row in grouped.iterrows():
        if int(row['count'])<=0: continue
        labels=label if isinstance(group,tuple) else (label,)
        output.append(dict(zip(keys,map(str,labels))) | dict(count=int(row['count']),price_sum=float(row.price_sum),mean_price=float(row.price_sum/row['count'])))
    return sorted(output,key=lambda x:(-x['count'],x[group]))[:3] if query=='top_types' else sorted(output,key=lambda x:tuple(x[key] for key in keys))


def top_rows(frame):
    frame=frame.copy()
    frame['source_shard']=frame.source_shard.astype('string')
    return frame.sort_values(['price_vnd','source_shard','source_row'],ascending=[False,True,True],kind='stable').head(100)


def run_query(method, csv_path, parquet_path, chunksize=50_000, *, query='province', filters=None,duckdb_memory_mb=1024):
    f=validate_filters(filters,query)
    columns=select_columns(query,f)
    dtypes={col:('int64' if col=='source_row' else 'string' if col=='source_shard' else 'float64' if col in ['price_vnd','area_m2'] else 'category') for col in columns}
    read_options=dict(float_precision='round_trip') if query=='top100' else {}
    if method=='csv_full':
        frame=pd.read_csv(csv_path,**read_options)
    elif method=='csv_columns':
        frame=pd.read_csv(csv_path,usecols=columns,**read_options)
    elif method=='csv_typed':
        frame=pd.read_csv(csv_path,usecols=columns,dtype=dtypes,**read_options)
    elif method=='csv_chunk':
        if chunksize < 1:
            raise ValueError('chunksize phải dương.')
        combined=None
        for part in pd.read_csv(csv_path,usecols=columns,dtype=dtypes,chunksize=chunksize,**read_options):
            if query=='top100':
                candidate=top_rows(filtered(part,f)[TOP_COLUMNS])
                combined=candidate if combined is None else top_rows(pd.concat([combined,candidate],ignore_index=True))
                continue
            grouped=aggregate(part,query,f)
            if isinstance(GROUPS[query],tuple):
                grouped.index=pd.MultiIndex.from_tuples([tuple(map(str,key)) for key in grouped.index],names=list(GROUPS[query]))
            else: grouped.index=grouped.index.astype(str)
            combined=grouped if combined is None else combined.add(grouped,fill_value=0)
        if query=='top100': return [] if combined is None else combined[TOP_COLUMNS].to_dict('records')
        return [] if combined is None else records(combined,query)
    elif method=='parquet_columns':
        frame=pd.read_parquet(parquet_path,columns=columns)
    elif method in ['duckdb_parquet','duckdb_csv']:
        import duckdb
        group=GROUPS[query]
        keys=list(group) if isinstance(group,tuple) else [group]
        where,params=sql_conditions(f)
        grouping=','.join(keys)
        ordering='count DESC, '+group+' ASC LIMIT 3' if query=='top_types' else grouping
        # Schema công khai cố định; không nội suy dữ liệu người dùng vào SQL.
        source='read_parquet(?)'
        source_path=parquet_path
        if method=='duckdb_csv':
            source_path=csv_path
            source="""read_csv(?,header=true,nullstr='',columns={
                'source_shard':'VARCHAR','source_row':'BIGINT','property_type_name':'VARCHAR',
                'province_name':'VARCHAR','district_name':'VARCHAR','price_vnd':'DOUBLE',
                'area_m2':'DOUBLE','floor_count':'DOUBLE','bedroom_count':'DOUBLE',
                'bathroom_count':'DOUBLE','published_at':'VARCHAR','published_month':'VARCHAR',
                'price_per_m2_vnd':'DOUBLE','extreme_value_flag':'BOOLEAN'})"""
        with duckdb.connect() as con:
            con.execute('SET threads=1'); con.execute(f"SET memory_limit='{int(duckdb_memory_mb)}MB'")
            if query=='top100':
                rows=con.execute('SELECT '+','.join(TOP_COLUMNS)+' FROM '+source+' WHERE '+where+
                                 ' ORDER BY price_vnd DESC,source_shard ASC,source_row ASC LIMIT 100',[str(source_path)]+params).fetchall()
                return [dict(zip(TOP_COLUMNS,row)) for row in rows]
            nonnull=' AND '.join(key+' IS NOT NULL' for key in keys)
            rows=con.execute(f'''SELECT {grouping}, COUNT(*) AS count, SUM(price_vnd) AS price_sum
                FROM {source} WHERE {where} AND {nonnull}
                GROUP BY {grouping} ORDER BY {ordering}''',[str(source_path)]+params).fetchall()
        return [dict(zip(keys,row[:-2])) | dict(count=int(row[-2]),price_sum=float(row[-1]),mean_price=float(row[-1]/row[-2])) for row in rows]
    else:
        raise ValueError(method)
    return top_rows(filtered(frame,f)[TOP_COLUMNS]).to_dict('records') if query=='top100' else records(aggregate(frame,query,f),query)
