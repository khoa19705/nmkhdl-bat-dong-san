"""Chạy phần kiểm chứng: workload mới, hạn mức commit và hòa vốn chuyển đổi."""
import argparse
from src.vietnam_data import ROOT
from src.benchmark import benchmark


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rows',type=int,default=1_000_000)
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--query-repeats',type=int,default=5)
    p.add_argument('--skip-workloads',action='store_true')
    p.add_argument('--skip-memory',action='store_true')
    p.add_argument('--skip-break-even',action='store_true')
    a=p.parse_args()
    if a.rows<1 or a.repeats<1 or a.query_repeats<1: p.error('Kích thước và số lần lặp phải dương.')
    if not a.skip_workloads:
        cases=[('province_type','province_type',None),('top100','top100',None),
               ('multi_filter','province',dict(province='Hà Nội',property_type='Nhà',area_min=50,area_max=100,price_min=1,price_max=5e9))]
        for label,query,filters in cases:
            benchmark([a.rows],a.repeats,directory=ROOT/'data/vietnam/benchmark',
                      output=ROOT/'results/vietnam/workloads'/label,dataset='vietnam',query=query,filters=filters)
    if not a.skip_memory:
        from src.controlled_study import run_memory_study
        run_memory_study(a.rows,a.repeats)
    if not a.skip_break_even:
        from src.break_even import run_break_even
        run_break_even(a.rows,a.query_repeats)
    from src.validation_report import build_validation_report
    build_validation_report()
    print('Hoàn tất. Xem report/kiem_chung_du_lieu_lon.html',flush=True)


if __name__=='__main__': main()
