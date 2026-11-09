"""Điểm chạy chính: python run_project.py --sizes 100000 500000 1000000."""
import argparse
from src.prepare import prepare_source, generate


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sizes', nargs='+', type=int, default=[100_000, 500_000, 1_000_000])
    p.add_argument('--repeats', type=int, default=3)
    p.add_argument('--chunksize', type=int, default=50_000)
    p.add_argument('--skip-generate', action='store_true', help='Dùng lại dữ liệu mô phỏng đã tạo')
    a = p.parse_args()
    if min(a.sizes) < 1 or a.repeats < 1 or a.chunksize < 1:
        p.error('Các kích thước và số lần lặp phải dương.')
    from src.benchmark import benchmark
    from src.deliverables import build_deliverables
    base, metadata = prepare_source()
    if not a.skip_generate:
        generate(base, sorted(set(a.sizes)))
    benchmark(sorted(set(a.sizes)), a.repeats, a.chunksize)
    build_deliverables()
    print('Hoàn tất. Mở report/bao_cao.html và report/thuyet_trinh.html.')


if __name__ == '__main__':
    main()
