"""Lấy các cột có cấu trúc từ Parquet công khai bằng HTTP Range.

Không tải tiêu đề/mô tả/địa chỉ chi tiết; không sinh thêm bản ghi.
URL ghim commit để dữ liệu có thể tái lập. Mỗi file đầu ra là bản trích cột,
không được gọi là bản sao nguyên vẹn của shard nguồn.
"""
import argparse
import hashlib
import io
import json
import re
import time
import urllib.request
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
REPO = 'tinixai/vietnam-real-estates'
REVISION = 'ca3fedcbb089bf65f7e4cfb03316cce4bd0d779f'
SOURCE = f'https://huggingface.co/datasets/{REPO}'
COLUMNS = ['property_type_name', 'province_name', 'district_name', 'price', 'area',
           'floor_count', 'bedroom_count', 'bathroom_count', 'published_at']


class HTTPRangeReader(io.RawIOBase):
    """File seekable tối thiểu: chỉ nhận đúng dải byte, chặn tải cả file nhầm."""
    def __init__(self, url):
        self.url = url
        self.position = 0
        self.transferred = 0
        self.requests = 0
        # HEAD không gắn Range để URL CDN không bị giới hạn vào một dải đầu tiên.
        request = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(request, timeout=60) as response:
            self.size = int(response.headers['Content-Length'])
            self.cdn_url = response.geturl()

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.position

    def seek(self, offset, whence=io.SEEK_SET):
        point = offset if whence == io.SEEK_SET else self.position+offset if whence == io.SEEK_CUR else self.size+offset
        if point < 0:
            raise ValueError('Seek âm')
        self.position = point
        return point

    def read(self, size=-1):
        if size is None or size < 0:
            size = self.size-self.position
        size = min(size, self.size-self.position)
        if size <= 0:
            return b''
        start, end = self.position, self.position+size-1
        expected = f'bytes {start}-{end}/{self.size}'
        for attempt in range(3):
            try:
                print(f'  Đọc cột: {size/1024**2:.2f} MiB (yêu cầu {self.requests+1})', flush=True)
                request = urllib.request.Request(self.cdn_url, headers={'Range':f'bytes={start}-{end}'})
                with urllib.request.urlopen(request, timeout=30) as response:
                    if response.status != 206 or response.headers.get('Content-Range') != expected:
                        raise ValueError('Máy chủ không trả đúng HTTP Range; dừng để tránh tải toàn file.')
                    data = response.read(size+1)
                if len(data) != size:
                    raise IOError('Độ dài dải byte không khớp.')
                self.position += size
                self.transferred += len(data)
                self.requests += 1
                return data
            except (OSError, ValueError) as error:
                print(f'  Thử lại do {type(error).__name__}, lần {attempt+1}/3.', flush=True)
                if attempt == 2:
                    raise
                time.sleep(1+attempt)

    def readinto(self, buffer):
        content = self.read(len(buffer))
        buffer[:len(content)] = content
        return len(content)


def download(shards=10):
    if not 1 <= shards <= 10:
        raise ValueError('Chọn từ 1 đến 10 shard.')
    directory = ROOT/'data/vietnam/raw'
    directory.mkdir(parents=True, exist_ok=True)
    metadata_path = directory/'source_metadata.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.exists() else dict(
        source=SOURCE, publisher='TiniX AI', revision=REVISION, license='CC BY-NC 4.0',
        license_url='https://creativecommons.org/licenses/by-nc/4.0/', source_reported_rows=3_500_744,
        columns=COLUMNS, shards=[],
        note='Trích cột từ dữ liệu tin đăng do nhà phát hành công bố. Không phải dữ liệu giao dịch xác minh; không sinh dữ liệu. Nguồn có cả bán/cho thuê nhưng schema không có nhãn phân biệt.')
    if metadata['revision'] != REVISION or metadata['columns'] != COLUMNS:
        raise ValueError('Metadata khác cấu hình tải; kiểm tra trước khi ghi đè.')
    for i in range(shards):
        name = f'shard_{i:04d}.parquet'
        output = directory/f'projection_{i:04d}.parquet'
        existing = next((x for x in metadata['shards'] if x['file'] == output.name), None)
        if output.exists() and existing and hashlib.sha256(output.read_bytes()).hexdigest() == existing['sha256']:
            print(f'Dùng lại {output.name}: {existing["rows"]:,} dòng.', flush=True)
            continue
        url = f'https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{name}?download=true'
        start = time.perf_counter()
        with HTTPRangeReader(url) as reader:
            parquet = pq.ParquetFile(reader, pre_buffer=False)
            print(f'{name}: {parquet.metadata.num_rows:,} hàng, {parquet.num_row_groups} row group.', flush=True)
            missing = set(COLUMNS)-set(parquet.schema_arrow.names)
            if missing:
                raise ValueError(f'Thiếu cột: {missing}')
            projected = parquet.read(columns=COLUMNS, use_threads=False)
            if projected.num_rows != parquet.metadata.num_rows:
                raise ValueError('Trích cột bị thiếu hàng.')
            # Ghi tạm rồi thay thế để không dùng lại file tải dở.
            temporary = output.with_suffix('.partial')
            pq.write_table(projected, temporary, compression='snappy', row_group_size=100_000)
            temporary.replace(output)
            entry = dict(file=output.name, source_file=name, source_url=url,
                         source_file_bytes=reader.size, transferred_bytes=reader.transferred,
                         http_range_requests=reader.requests, rows=projected.num_rows,
                         bytes=output.stat().st_size, sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                         elapsed_s=time.perf_counter()-start)
        metadata['shards'] = [x for x in metadata['shards'] if x['file'] != output.name]+[entry]
        metadata['downloaded_rows'] = sum(x['rows'] for x in metadata['shards'])
        metadata['updated_utc'] = pd.Timestamp.now(tz='UTC').isoformat()
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Đã trích {name}: {entry["rows"]:,} hàng; tải {entry["transferred_bytes"]/1024**2:.1f} MiB / file nguồn {reader.size/1024**2:.1f} MiB.', flush=True)
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shards', type=int, default=10)
    args = parser.parse_args()
    download(args.shards)
