import json
import tempfile
from pathlib import Path
from unittest import TestCase, mock
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from src.vietnam_data import COLUMNS
from src.vietnam_prepare import clean_vietnam,write_samples
from src.vietnam_queries import run_query,validate_filters,GROUPS
from src.vietnam_search import search_data
from src.benchmark import equivalent,benchmark
from src.queries import METHODS

HERE=Path(__file__).resolve().parent


class UpgradeTests(TestCase):
    def fixture(self):
        raw=pd.DataFrame([
            ['Nhà','Hà Nội','A',2e9,50,2,2,1,'2025-06-01T00:00:00'],
            ['Đất','Huế','B',1e9,100,0,0,0,'2025-07-01T00:00:00'],
            ['Nhà','Hà Nội','A',5e9,150,3,3,2,'2025-07-02T00:00:00'],
            ['Căn hộ','Hà Nội','A',3e9,80,None,2,1,'2025-06-02T00:00:00'],
            ['Biệt thự','Huế','B',9e9,120,2,4,4,'2025-08-02T00:00:00'],
            ['Đất','Hà Nội','A',12e9,90,None,None,None,'2025-06-03T00:00:00'],
        ],columns=COLUMNS)
        return clean_vietnam(raw,'fixture.parquet')[0]

    def test_rejected_values_and_original_row_offset(self):
        raw=pd.DataFrame([
            ['Nhà','Hà Nội',None,None,50,None,2,1,'2025-06-01'],
            ['Đất','Huế','A',1e9,0,None,None,None,'2025-06-02'],
            ['Nhà','Huế','A',2e9,50,None,2,1,'2025-06-03'],
        ],columns=COLUMNS)
        good,audit,bad=clean_vietnam(raw,'part.parquet',row_offset=100,return_rejected=True)
        self.assertEqual(good.source_row.tolist(),[102])
        self.assertEqual(bad.source_row.tolist(),[100,101])
        self.assertIn('price',bad.iloc[0].rejection_reason)
        self.assertIn('area',bad.iloc[1].rejection_reason)
        self.assertEqual(len(good)+len(bad),audit['raw_rows'])

    def test_streaming_samples_nested_repeatable_and_no_full_pandas_read(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp); source=root/'clean.parquet'; self.fixture().to_parquet(source,index=False)
            with mock.patch('pandas.read_parquet',side_effect=AssertionError('Không được nạp toàn bảng')):
                write_samples(source,root/'a',[2,5],seed=42,batch_size=2,memory_mb=64)
                write_samples(source,root/'b',[2,5],seed=42,batch_size=3,memory_mb=64)
            small=pq.read_table(root/'a/estate_2.parquet').to_pandas()
            large=pq.read_table(root/'a/estate_5.parquet').to_pandas()
            repeat=pq.read_table(root/'b/estate_5.parquet').to_pandas()
            self.assertEqual(small.source_row.tolist(),large.source_row.head(2).tolist())
            self.assertEqual(large.source_row.tolist(),repeat.source_row.tolist())
            self.assertEqual(large.source_row.nunique(),5)
            pd.testing.assert_frame_equal(pd.read_csv(root/'a/estate_5.csv'),pd.read_csv(root/'b/estate_5.csv'))

    def test_three_queries_six_engines_and_user_filters(self):
        frame=self.fixture()
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            csv=Path(tmp)/'estate_6.csv'; parquet=Path(tmp)/'estate_6.parquet'
            frame.to_csv(csv,index=False); frame.to_parquet(parquet,index=False)
            for query in GROUPS:
                for filters in [None,{'province':'Hà Nội','property_type':'Nhà'}, {'province':'Không tồn tại'}]:
                    baseline=run_query('csv_full',csv,parquet,query=query,filters=filters)
                    for method in METHODS:
                        with self.subTest(query=query,method=method,filters=filters):
                            actual=run_query(method,csv,parquet,2,query=query,filters=filters)
                            self.assertTrue(equivalent(baseline,actual,GROUPS[query]))
            top=run_query('csv_chunk',csv,parquet,2,query='top_types')
            self.assertEqual([r['property_type_name'] for r in top],['Nhà','Biệt thự','Căn hộ'])

    def test_search_export_matches_filter_and_zero_rows_has_header(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp); parquet=root/'clean.parquet'; self.fixture().to_parquet(parquet,index=False)
            result=search_data(parquet,{'province':'Hà Nội','property_type':'Nhà'},1,root/'selected.csv')
            self.assertEqual(result['matched_rows'],2); self.assertEqual(len(result['preview']),1)
            exported=pd.read_csv(root/'selected.csv'); self.assertEqual(len(exported),2)
            self.assertEqual(set(exported.province_name),{'Hà Nội'})
            empty=search_data(parquet,{'province':'Không tồn tại'},1,root/'empty.csv')
            self.assertEqual(empty['matched_rows'],0); self.assertEqual(len(pd.read_csv(root/'empty.csv')),0)

    def test_filter_validation(self):
        for bad in [{'price_min':20,'price_max':10},{'area_min':-1},{'area_max':float('nan')},{'unknown':1}]:
            with self.assertRaises(ValueError): validate_filters(bad)

    def test_failed_run_preserves_last_success_and_history(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root=Path(tmp); n=6; frame=self.fixture()
            frame.to_csv(root/f'estate_{n}.csv',index=False); frame.to_parquet(root/f'estate_{n}.parquet',index=False)
            output=root/'output'
            benchmark([n],1,directory=root,output=output,dataset='vietnam',methods=['csv_full','csv_chunk'])
            published=(output/'summary.csv').read_bytes(); pointer=(output/'latest_run.json').read_bytes()
            with mock.patch('src.benchmark.measure',side_effect=RuntimeError('Lỗi kiểm thử chủ động')):
                with self.assertRaises(RuntimeError):
                    benchmark([n],1,directory=root,output=output,dataset='vietnam',methods=['csv_full','csv_chunk'])
            self.assertEqual(published,(output/'summary.csv').read_bytes())
            self.assertEqual(pointer,(output/'latest_run.json').read_bytes())
            statuses=[json.loads(p.read_text(encoding='utf-8'))['status'] for p in (output/'history').glob('*/status.json')]
            self.assertEqual(sorted(statuses),['FAILED','SUCCESS'])
