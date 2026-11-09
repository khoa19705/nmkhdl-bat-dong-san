import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import pandas as pd
import pyarrow.parquet as pq
from src.vietnam_queries import run_query,GROUPS,TOP_COLUMNS
from src.benchmark import equivalent
from src.queries import METHODS
from src.conversion import convert_csv
from src.break_even import first_profitable_query,content_fingerprint
from src.controlled_study import summarize_runs
import test_upgrades


class ValidationTests(unittest.TestCase):
    def test_top100_ties_across_chunks_and_large_prices(self):
        frame=pd.DataFrame([dict(source_shard='b.parquet' if i%2 else 'a.parquet',source_row=i//2,
            province_name='Hà Nội',property_type_name='Nhà',price_vnd=float(1e18+(i%7)*1024),area_m2=50.)
            for i in range(250)])
        expected=sorted(frame.to_dict('records'),key=lambda r:(-r['price_vnd'],r['source_shard'],r['source_row']))[:100]
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            csv=Path(tmp)/'test.csv'; parquet=Path(tmp)/'test.parquet'
            frame.to_csv(csv,index=False); frame.to_parquet(parquet,index=False)
            for method in METHODS:
                with self.subTest(method=method):
                    actual=run_query(method,csv,parquet,13,query='top100')
                    self.assertTrue(equivalent(expected,actual,GROUPS['top100']))
                    self.assertEqual([(r['source_shard'],r['source_row']) for r in actual],
                                     [(r['source_shard'],r['source_row']) for r in expected])

    def test_conversion_preserves_all_columns_and_nulls(self):
        frame=test_upgrades.UpgradeTests().fixture()
        frame.loc[0,'district_name']='NA'
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            root=Path(tmp); frame.to_csv(root/'test.csv',index=False); frame.to_parquet(root/'original.parquet',index=False)
            count=convert_csv(root/'test.csv',root/'converted.parquet')
            self.assertEqual(count,len(frame))
            self.assertEqual(content_fingerprint(root/'original.parquet'),content_fingerprint(root/'converted.parquet'))
            self.assertEqual(pq.ParquetFile(root/'converted.parquet').metadata.num_rows,len(frame))

    def test_break_even_is_strict_and_handles_no_advantage(self):
        self.assertEqual(first_profitable_query(10.,3.,1.),6)
        self.assertEqual(first_profitable_query(0.,3.,1.),1)
        self.assertIsNone(first_profitable_query(10.,1.,1.))
        self.assertIsNone(first_profitable_query(10.,1.,2.))
        with self.assertRaises(ValueError): first_profitable_query(-1,2,1)

    def test_duckdb_csv_matches_parquet_for_all_workloads(self):
        frame=test_upgrades.UpgradeTests().fixture()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            root=Path(tmp); frame.to_csv(root/'test.csv',index=False); frame.to_parquet(root/'test.parquet',index=False)
            for query in GROUPS:
                with self.subTest(query=query):
                    expected=run_query('duckdb_parquet',root/'test.csv',root/'test.parquet',query=query)
                    actual=run_query('duckdb_csv',root/'test.csv',root/'test.parquet',query=query)
                    self.assertTrue(equivalent(expected,actual,GROUPS[query]))

    def test_memory_summary_does_not_promote_crash_samples_to_verified_peaks(self):
        common=dict(limit_mib=256,query='top100',method='csv_full')
        runs=[common | dict(status='NATIVE_ERROR',peak_rss_mib=4.,observed_peak_commit_mib=2.),
              common | dict(status='OOM',peak_rss_mib=5.,elapsed_s=None,
                            limit_verified=dict(peak_commit_bytes=255*1024**2))]
        row=summarize_runs(runs).iloc[0]
        self.assertEqual(row.success,0)
        self.assertEqual(row.oom,1)
        self.assertEqual(row.other_errors,1)
        self.assertTrue(pd.isna(row.max_success_peak_rss_mib))
        self.assertEqual(row.verified_commit_cases,1)
        self.assertEqual(row.max_verified_peak_commit_mib,255.)

    @unittest.skipUnless(os.name=='nt','Windows Job Object only')
    def test_os_limit_accepts_small_and_rejects_oversized_commit(self):
        for allocation,status in [(16,'SUCCESS'),(96,'OOM')]:
            completed=subprocess.run([sys.executable,'-m','src.limited_worker','--limit-mib','64',
                                       '--probe-mib',str(allocation)],capture_output=True,text=True,check=True,timeout=15)
            result=json.loads(completed.stdout)
            self.assertEqual(result['status'],status)
            self.assertTrue(result['limit_verified']['enabled'])
            self.assertEqual(result['limit_verified']['limit_bytes'],64*1024**2)
