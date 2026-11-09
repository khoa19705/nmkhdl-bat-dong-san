"""Kiểm tra nguồn Việt Nam có đơn vị/truy vấn riêng và không tự bù dữ liệu thiếu."""
import tempfile
from pathlib import Path
import unittest
import pandas as pd
from src.benchmark import equivalent, measure
from src.queries import METHODS
from src.vietnam_data import COLUMNS
from src.vietnam_prepare import clean_vietnam
from src.vietnam_queries import run_query


class VietnamTests(unittest.TestCase):
    def test_measure_handles_json_larger_than_windows_pipe_buffer(self):
        count=120
        frame=pd.DataFrame({'province_name':[f'Tỉnh kiểm thử {i:03d}' for i in range(count)],
                            'price_vnd':[2e9]*count,'area_m2':[100.0]*count})
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            path=Path(directory)
            frame.to_csv(path/f'estate_{count}.csv',index=False)
            frame.to_parquet(path/f'estate_{count}.parquet',index=False)
            result=measure('csv_full',count,50,timeout=20,directory=path,dataset='vietnam')
            self.assertEqual(len(result['result']),count)
            self.assertGreater(result['peak_rss_mib'],0)

    def test_clean_keeps_optional_missing_and_traces_original_row(self):
        raw=pd.DataFrame([
            ['Nhà','Hà Nội',None,2e9,50,None,2,1,'2025-06-01T00:00:00'],
            ['Nhà','Hà Nội',None,None,50,None,2,1,'2025-06-01T00:00:00'],
            ['Đất','Hồ Chí Minh','1',1e9,-1,None,None,None,'2025-06-01T00:00:00'],
            ['Nhà','Hà Nội',None,5e9,100,2.5,-1,2,'bad-date'],
        ],columns=COLUMNS)
        cleaned,audit=clean_vietnam(raw,'shard_test.parquet')
        self.assertEqual(cleaned.source_row.tolist(),[0,3])
        self.assertEqual(audit['missing_core_rows'],1)
        self.assertEqual(audit['invalid_core_rows'],1)
        self.assertEqual(audit['invalid_publication_dates'],1)
        self.assertTrue(pd.isna(cleaned.loc[1,'floor_count']))
        self.assertEqual(cleaned.loc[0,'price_per_m2_vnd'],40_000_000)

    def test_vietnam_engines_unicode_boundaries_and_empty_chunks(self):
        frame=pd.DataFrame({'province_name':['Hà Nội','Huế','Hà Nội','Hồ Chí Minh','Huế','Hà Nội','Huế'],
                            'price_vnd':[20e9,1,10e9,3e9,2e9,0,1e9],
                            'area_m2':[50,49,150,50,100,100,151],
                            'property_type_name':['Nhà']*7})
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            csv=Path(directory)/'sample.csv'; pq=Path(directory)/'sample.parquet'
            frame.to_csv(csv,index=False); frame.to_parquet(pq,index=False)
            baseline=run_query('csv_full',csv,pq)
            self.assertEqual(sum(x['count'] for x in baseline),3)
            for method in METHODS:
                self.assertTrue(equivalent(baseline,run_query(method,csv,pq,2),'province_name'),method)
            frame['area_m2']=1
            frame.to_csv(csv,index=False); frame.to_parquet(pq,index=False)
            for method in METHODS:
                self.assertEqual(run_query(method,csv,pq,2),[])


if __name__=='__main__':
    unittest.main()
