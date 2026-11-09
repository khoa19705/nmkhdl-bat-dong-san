"""Báo cáo chức năng mới và thí nghiệm mở rộng, đọc trực tiếp kết quả thật."""
import base64
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from src.vietnam_data import ROOT
from src.deliverables import STYLE,table
from src.queries import LABELS


def build_upgrade_report():
    processed=ROOT/'data/vietnam/processed'
    profile=json.loads((processed/'profile.json').read_text(encoding='utf-8'))
    quality=pd.read_csv(processed/'quality_before_after.csv')
    # Chụp tài liệu của đúng mẫu đã đo, kể cả phiên chạy bắt đầu trước khi mã
    # lưu snapshot được nạp. Chỉ ghép nếu checksum config trùng manifest hiện tại.
    manifest=json.loads((ROOT/'data/vietnam/benchmark/manifest.json').read_text(encoding='utf-8'))
    lookup={row['rows']:row for row in manifest}
    import shutil
    for pointer in (ROOT/'results/vietnam').rglob('latest_run.json'):
        latest=json.loads(pointer.read_text(encoding='utf-8'))
        directory=ROOT/latest['path']
        config=json.loads((directory/'config.json').read_text(encoding='utf-8'))
        if config.get('dataset')!='vietnam': continue
        matches=all(item['rows'] in lookup and all(item[ext]['sha256']==lookup[item['rows']][ext+'_sha256'] for ext in ['csv','parquet']) for item in config['inputs'])
        if matches:
            for source in [processed/'profile.json',ROOT/'data/vietnam/raw/source_metadata.json',ROOT/'data/vietnam/benchmark/manifest.json']:
                target_name='sample_manifest.json' if source.name=='manifest.json' else source.name
                if not (directory/target_name).exists(): shutil.copy2(source,directory/target_name)
    body=f'''<p class="eyebrow">BẢN NÂNG CẤP CHỨC NĂNG</p><h1>Xử lý theo khối, tra cứu và thí nghiệm mở rộng</h1>
    <p><a href="bao_cao.html">Báo cáo chính</a> · <a href="bo_sung_du_lieu_viet_nam.html">Dữ liệu Việt Nam</a></p>
    <h2>1. Chuẩn bị dữ liệu theo khối</h2><p>Đọc từng Arrow batch tối đa {profile['batch_size']:,} hàng,
    làm sạch và ghi Parquet theo khối. Không có bước nạp toàn bộ bảng sạch hoặc toàn bộ mẫu vào Pandas.
    Các phép nhóm, đếm trùng và sắp xếp chọn mẫu dùng DuckDB với ngân sách bộ quản lý bộ nhớ {profile['duckdb_memory_mb']} MB
    cùng thư mục tràn đĩa. Ngân sách này không phải giới hạn cứng RAM toàn tiến trình.</p>
    <p>Lấy mẫu không hoàn lại bằng thứ tự hash của source_shard, source_row và seed, phá hòa bằng ID nguồn;
    các mức nhỏ là tiền tố của mức lớn. Đây là thứ tự giả ngẫu nhiên xác định, không phải mẫu phân tầng.
    Thuật toán lấy mẫu thay đổi so với bản đầu; các số đo được chạy lại trên bộ mẫu mới.
    Phiên bản DuckDB được ghim vì hàm hash có thể thay đổi giữa các phiên bản.</p>
    <h2>2. Báo cáo chất lượng và hàng bị loại</h2><p>{profile['raw_rows']:,} hàng nguồn → {profile['clean_rows']:,} hàng đạt quy tắc.
    Tệp <code>data/vietnam/processed/rejected_rows.csv</code> ghi hàng gốc, source_shard, source_row và từng lý do loại.
    Lỗi số phòng/tầng được đổi thành thiếu; không tự điền trung bình hoặc tự nhận dạng tin bán/thuê.</p>{table(quality)}
    <h2>3. Tra cứu và xuất kết quả</h2><p>Chọn tỉnh, loại nhà, khoảng giá và diện tích; xem trước 1–1.000 hàng,
    đếm toàn bộ hàng khớp và xuất CSV theo khối. Xem trước được sắp theo giá đăng và ID hàng nguồn;
    CSV xuất toàn bộ hàng khớp không cam kết cùng thứ tự. Giá là giá đăng, không xác nhận giá giao dịch.</p>
    <pre>python search_vietnam.py --province "Hà Nội" --property-type "Nhà" --area-min 50 --area-max 100 --price-max 5000000000 --limit 10 --export results/ha_noi.csv</pre>
    <h2>4. Ba tải truy vấn</h2><ul><li>province: lọc rồi nhóm theo tỉnh, count/sum/mean.</li>
    <li>month: cùng điều kiện lọc, nhóm theo tháng đăng; bỏ nhóm tháng thiếu.</li>
    <li>top_types: nhóm theo loại bất động sản, lấy 3 loại có nhiều bản ghi nhất; hòa thì theo tên loại tăng dần.</li></ul>
    <p>Cả sáu phương pháp dùng cùng điều kiện và quy tắc sắp xếp của từng truy vấn.
    Chunk gộp toàn bộ count/sum trước khi lấy top 3, không lấy top từng khối rồi bỏ các nhóm khác.</p>
    <h2>5. Lịch sử phép đo và tính tái lập</h2><p>Mỗi lần đo có run_id, cấu hình, checksum CSV/Parquet,
    trạng thái RUNNING/FAILED/SUCCESS và số đo thô trong <code>results/vietnam/history/</code> hoặc history của từng thí nghiệm.
    Chỉ công bố bộ kết quả mới sau khi kiểm tra tương đương đạt; lượt thất bại không ghi đè bảng kết quả thành công gần nhất.
    Bản đo cũ trước nâng cấp được giữ trong thư mục legacy.</p>'''
    preparation=ROOT/'results/vietnam/preparation_measurement.json'
    if preparation.exists():
        measure=json.loads(preparation.read_text(encoding='utf-8'))
        body+=f'''<h2>6. Số đo bước chuẩn bị</h2><p>Thời gian: {measure['elapsed_s']:.2f} giây.
        Peak working set tiến trình đến hết bước chuẩn bị trên Windows: {measure['peak_process_mib']:.1f} MiB,
        gồm runtime và thư viện từ lúc khởi động. Chưa có đối chứng đo lại bộ chuẩn bị cũ nên không công bố tỷ lệ giảm RAM của bước này.</p>'''
    expanded=ROOT/'results/vietnam/experiments/expanded_summary.csv'
    if expanded.exists():
        summary=pd.read_csv(expanded)
        if not summary.correct.all(): raise AssertionError('Thí nghiệm mở rộng có kết quả không khớp.')
        chunks=summary[(summary.experiment=='chunk_size') & (summary.method=='csv_chunk')].sort_values('chunksize')
        figure,axes=plt.subplots(1,2,figsize=(10,4))
        for ax,metric,label in zip(axes,['median_s','median_peak_mib'],['Trung vị thời gian (s)','Peak working set (MiB)']):
            ax.bar(chunks.chunksize.astype(str),chunks[metric],color='#07858c'); ax.set(xlabel='Số hàng / chunk',ylabel=label); ax.set_ylim(bottom=0)
        figure.tight_layout(); path=ROOT/'results/vietnam/experiments/chunk_sizes.png'; figure.savefig(path,dpi=160); plt.close(figure)
        encoded=base64.b64encode(path.read_bytes()).decode()
        count=int(summary.repeats.sum())
        show=summary[['experiment','query','chunksize','method','median_s','min_s','max_s','median_peak_mib','correct']].copy()
        show['method']=show.method.map(LABELS)
        best_time=chunks.loc[chunks.median_s.idxmin()]; best_ram=chunks.loc[chunks.median_peak_mib.idxmin()]
        body+=f'''<h2>7. Kết quả mở rộng đã chạy</h2><p>{count} lượt đo mở rộng, tất cả thống kê khớp baseline của từng truy vấn.
        Với các mức đã thử, chunk {int(best_time.chunksize):,} có thời gian trung vị thấp nhất;
        chunk {int(best_ram.chunksize):,} có peak RAM trung vị thấp nhất. Đây là kết quả trên bộ mẫu, máy và tải hiện tại.</p>
        <img alt="So sánh kích thước chunk" src="data:image/png;base64,{encoded}">{table(show)}
        <p>Các lượt đo chunk có baseline riêng và chạy tại các thời điểm khác nhau; không so khác biệt rất nhỏ như bằng chứng có ý nghĩa thống kê.
        Mỗi cấu hình lặp ba lần mặc định, không xóa cache hệ điều hành. Không suy ra xử lý ngoài RAM chỉ từ giới hạn bộ nhớ DuckDB.</p>'''
    body+='''<h2>8. Chạy lại</h2><pre>python run_vietnam.py --extended
python run_vietnam.py --skip-prepare --extended
python run_vietnam.py --only-extended
python -m unittest discover -s tests -v</pre><p>Dùng Python trong .venv theo README. Thí nghiệm mở rộng mặc định ở mức dữ liệu lớn nhất.
    Các tính năng được cung cấp qua CLI; báo cáo HTML là đầu ra đọc, không phải giao diện web thao tác.</p>'''
    target=ROOT/'report/nang_cap_he_thong.html'
    target.write_text('<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nâng cấp đồ án</title><style>'+STYLE+'</style><main>'+body+'</main></html>',encoding='utf-8')
    attach_upgrade_files()


def attach_upgrade_files():
    import re
    for name in ['bao_cao.html','bo_sung_du_lieu_viet_nam.html']:
        path=ROOT/'report'/name
        text=path.read_text(encoding='utf-8')
        marker='<aside id="upgrade-link" class="note">'
        text=re.sub(r'<aside id="upgrade-link".*?</aside>','',text,flags=re.S)
        banner=marker+'<strong>Đã nâng cấp:</strong> chuẩn bị theo khối, lọc tùy chọn, hàng lỗi và thí nghiệm mở rộng. <a href="nang_cap_he_thong.html">Xem chức năng và kết quả mới</a>.</aside>'
        path.write_text(text.replace('<main>','<main>'+banner,1),encoding='utf-8')
    path=ROOT/'report/thuyet_trinh.html'
    text=path.read_text(encoding='utf-8')
    text=re.sub(r'<!--validation-slides-start-->.*?<!--validation-slides-end-->','',text,flags=re.S)
    text=re.sub(r'<!--upgrade-slides-start-->.*?<!--upgrade-slides-end-->','',text,flags=re.S)
    count=text.count('class="slide"'); total=count+2
    image_path=ROOT/'results/vietnam/experiments/chunk_sizes.png'
    chart='<p>Xem báo cáo nâng cấp để đọc kết quả mở rộng.</p>'
    if image_path.exists():
        chart='<img alt="Khảo sát chunk size" src="data:image/png;base64,'+base64.b64encode(image_path.read_bytes()).decode()+'">'
    extra=f'''<!--upgrade-slides-start--><section class="slide" id="s{count+1}"><h1>Chức năng đã hoàn thiện</h1>
    <ul><li>Chuẩn bị dữ liệu theo Arrow batch, DuckDB có thư mục tràn đĩa.</li>
    <li>Lọc theo tỉnh, loại nhà, giá và diện tích; xuất CSV theo khối.</li>
    <li>Lưu hàng bị loại kèm lý do và chất lượng trước–sau.</li>
    <li>Mỗi lần đo có cấu hình, checksum, trạng thái và lịch sử riêng.</li></ul>
    <p><a href="nang_cap_he_thong.html">Báo cáo chức năng mới</a></p><span class="num">{count+1}/{total}</span></section>
    <section class="slide" id="s{count+2}"><h1>Khảo sát kích thước chunk</h1>{chart}
    <p>10.000 / 50.000 / 100.000 hàng; cùng truy vấn, ba lần lặp mỗi cấu hình. Thêm tải nhóm theo tháng và top 3 loại tin.</p>
    <span class="num">{count+2}/{total}</span></section><!--upgrade-slides-end-->'''
    text=text.replace('</main>',extra+'</main>',1)
    text=re.sub(r'(<span class="num">\d+)/\d+(</span>)',lambda m:m[1]+f'/{total}'+m[2],text)
    text=re.sub(r'Math\.min\(\d+,i\+',f'Math.min({total},i+',text)
    path.write_text(text,encoding='utf-8')
    notebook_path=ROOT/'notebooks/01_do_an.ipynb'
    notebook=json.loads(notebook_path.read_text(encoding='utf-8'))
    notebook['cells']=[c for c in notebook['cells'] if not c['id'].startswith('upgrade-')]
    notebook['cells'].extend([
        dict(cell_type='markdown',id='upgrade-intro',metadata={},source=['## 7. Chất lượng trước–sau và thí nghiệm mở rộng\n','Bước chuẩn bị dùng Arrow batch và thứ tự hash xác định; số đo mới không dùng bộ mẫu NumPy của phiên cũ. Đọc báo cáo nâng cấp để hiểu giới hạn RAM và cách tra cứu.']),
        dict(cell_type='code',id='upgrade-quality',metadata={},execution_count=None,outputs=[],source=['quality = pd.read_csv(ROOT / "data/vietnam/processed/quality_before_after.csv")\n','quality']),
        dict(cell_type='code',id='upgrade-experiments',metadata={},execution_count=None,outputs=[],source=['extra_path = ROOT / "results/vietnam/experiments/expanded_summary.csv"\n','if extra_path.exists():\n','    extra = pd.read_csv(extra_path)\n','    assert extra.correct.all()\n','    print(extra[["query", "chunksize", "method", "median_s", "median_peak_mib"]].to_string(index=False))'])])
    notebook_path.write_text(json.dumps(notebook,ensure_ascii=False,indent=2),encoding='utf-8')
    if (ROOT/'report/kiem_chung_du_lieu_lon.html').exists():
        from src.validation_report import attach_validation_files
        attach_validation_files()
