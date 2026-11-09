"""Kiểm tra làm sạch và phép gộp theo khối tại biên lọc, không dùng số đo giả."""
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pandas as pd
from src.prepare import COLS, clean, age_band
from src.queries import METHODS, run_query
from src.benchmark import equivalent


class ProjectTests(unittest.TestCase):
    def test_clean_rejects_missing_invalid_duplicate_but_keeps_price_outlier(self):
        rows=[[1,2013.25,10,100,2,24.9,121.5,30],
              [1,2013.25,10,100,2,24.9,121.5,30],
              [2,2013.25,-1,100,2,24.9,121.5,30],
              [3,2013.25,10,100,2,24.9,121.5,None],
              [4,2013.25,10,100,2,24.9,121.5,10000],
              [5,2013.25,10,100,2.5,24.9,121.5,30],
              [6,2013.25,10,float('inf'),2,24.9,121.5,30]]
        result,audit=clean(pd.DataFrame(rows,columns=COLS))
        self.assertEqual(result.source_id.tolist(),[1,4])
        self.assertEqual(audit['missing_rows'],1)
        self.assertEqual(audit['invalid_rows'],3)
        self.assertEqual(audit['duplicate_id_rows'],1)
        self.assertAlmostEqual(result.iloc[0].price_twd_per_m2,30*10000/3.3)

    def test_all_engines_boundaries_empty_chunks_and_weighted_mean(self):
        # Khối đầu không hàng nào được chọn; giá khác nhau để bắt lỗi mean-of-means.
        frame=pd.DataFrame({'house_age':[31,40,10,10.01,30,30.01,5,0,7],
                            'mrt_distance_m':[10,20,1000,999,0,0,1001,50,1],
                            'price_10k_twd_per_ping':[5,9,1,100,2,8,3,10,80]})
        frame['age_band']=age_band(frame.house_age)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            csv=Path(directory)/'tiny.csv'; pq=Path(directory)/'tiny.parquet'
            frame.to_csv(csv,index=False); frame.to_parquet(pq,index=False)
            baseline=run_query('csv_full',csv,pq)
            self.assertEqual(sum(x['count'] for x in baseline),5)
            for method in METHODS:
                with self.subTest(method=method):
                    self.assertTrue(equivalent(baseline,run_query(method,csv,pq,chunksize=2)))
            frame['house_age']=99
            frame.to_csv(csv,index=False); frame.to_parquet(pq,index=False)
            for method in METHODS:
                self.assertEqual(run_query(method,csv,pq,chunksize=2),[])

    def test_equivalence_detects_wrong_count_or_mean(self):
        a=[dict(age_band='0-10',count=2,price_sum=10.,mean_price=5.)]
        self.assertFalse(equivalent(a,[dict(age_band='0-10',count=3,price_sum=10.,mean_price=5.)]))
        self.assertFalse(equivalent(a,[dict(age_band='0-10',count=2,price_sum=10.,mean_price=4.)]))


if __name__ == '__main__':
    unittest.main()
