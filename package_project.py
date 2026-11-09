"""Đóng gói bài nộp, bỏ môi trường Python và file tạm."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parent
out=ROOT/'dist'
out.mkdir(exist_ok=True)
target=out/'DoAn_BatDongSan_Khoa_HanHan.zip'
folders=['src','tests','data','results','report','notebooks']
files=[ROOT/name for name in ['README.md','requirements.txt','run_project.py','run_vietnam.py','run_validation.py','search_vietnam.py','demo.py','package_project.py']]
for folder in folders:
    files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
with ZipFile(target,'w',compression=ZIP_DEFLATED,compresslevel=3) as z:
    for path in sorted(files):
        z.write(path,arcname=str(Path('DoAn_BatDongSan')/path.relative_to(ROOT)))
with ZipFile(target) as z:
    bad=z.testzip()
    if bad:
        raise RuntimeError(f'File nén lỗi ở {bad}')
print(f'{target} ({target.stat().st_size/1024**2:.1f} MiB; {len(files)} files)')
