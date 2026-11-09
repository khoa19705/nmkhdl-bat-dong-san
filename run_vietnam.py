"""Bổ sung dữ liệu Việt Nam; tách nguồn, truy vấn và kết quả khỏi thí nghiệm UCI."""
import argparse
import time
import psutil
from src.vietnam_data import ROOT, download
from src.vietnam_prepare import prepare_vietnam
from src.benchmark import benchmark,archive_existing


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--download',action='store_true',help='Tải các cột nguồn nếu chưa có; cần Internet')
    p.add_argument('--shards',type=int,default=4)
    p.add_argument('--sizes',type=int,nargs='+',default=[100_000,500_000,1_000_000])
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--skip-prepare',action='store_true',help='Dùng lại các tập benchmark đã chuẩn bị')
    p.add_argument('--chunksize',type=int,default=50_000)
    p.add_argument('--prepare-batch',type=int,default=50_000)
    p.add_argument('--prepare-memory-mb',type=int,default=256)
    p.add_argument('--extended',action='store_true',help='Thêm truy vấn theo tháng/top loại và khảo sát chunk size')
    p.add_argument('--only-extended',action='store_true',help='Chỉ chạy bộ mở rộng trên các tập đã chuẩn bị')
    a=p.parse_args()
    if min(a.sizes)<1 or a.repeats<1 or a.chunksize<1 or a.prepare_batch<1 or a.prepare_memory_mb<64:
        p.error('Số dòng và số lần lặp phải dương.')
    if a.download:
        download(a.shards)
    archive_existing(ROOT/'results/vietnam',ROOT/'data/vietnam/benchmark',a.sizes)
    if not a.skip_prepare and not a.only_extended:
        started=time.perf_counter()
        prepare_vietnam(a.sizes,batch_size=a.prepare_batch,memory_mb=a.prepare_memory_mb)
        from src.storage import write_json
        memory=psutil.Process().memory_info()
        write_json(ROOT/'results/vietnam/preparation_measurement.json',dict(
            elapsed_s=time.perf_counter()-started,peak_process_mib=getattr(memory,'peak_wset',memory.rss)/1024**2,
            batch_size=a.prepare_batch,duckdb_memory_mb=a.prepare_memory_mb,
            note='Windows: high-water working set tiến trình từ lúc khởi động đến hết chuẩn bị, gồm thư viện. Ngân sách DuckDB không phải giới hạn cứng toàn tiến trình. Nền tảng khác: RSS tại cuối bước, không phải đỉnh.'))
    if not a.only_extended:
        benchmark(sorted(set(a.sizes)),a.repeats,a.chunksize,directory=ROOT/'data/vietnam/benchmark',
                  output=ROOT/'results/vietnam',dataset='vietnam')
    if a.extended or a.only_extended:
        from src.experiments import expanded_experiments
        expanded_experiments(max(a.sizes),a.repeats)
    from src.vietnam_report import build_report
    build_report()
    from src.upgrade_report import build_upgrade_report
    build_upgrade_report()
    print('Hoàn tất. Xem report/bo_sung_du_lieu_viet_nam.html',flush=True)


if __name__=='__main__':
    main()
