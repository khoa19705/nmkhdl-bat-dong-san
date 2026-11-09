"""Báo cáo bổ sung từ dữ liệu và phép đo Việt Nam đã chạy thực tế."""
import base64
import html
import json
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from src.vietnam_data import ROOT, SOURCE, COLUMNS
from src.queries import LABELS, METHODS
from src.deliverables import STYLE, table


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def embed(name):
    data=base64.b64encode((ROOT/'results/vietnam'/name).read_bytes()).decode()
    return f'<img alt="{html.escape(name)}" src="data:image/png;base64,{data}">'


def make_plots(summary, counts):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,
                         'axes.spines.top':False,'axes.spines.right':False})
    figure,axes=plt.subplots(1,2,figsize=(12,4.8))
    colors=['#64748b','#a16207','#8b5cf6','#0284c7','#0d9488','#e05d38']
    for method,color in zip(METHODS,colors):
        sub=summary[summary.method==method].sort_values('rows')
        for ax,metric in zip(axes,['median_s','median_peak_mib']):
            ax.plot(sub.rows/1000,sub[metric],marker='o',label=LABELS[method],color=color)
    axes[0].set(xlabel='Số bản ghi tin đăng (nghìn)',ylabel='Trung vị (giây)',title='Đọc + lọc + tổng hợp trên dữ liệu Việt Nam')
    axes[1].set(xlabel='Số bản ghi tin đăng (nghìn)',ylabel='Peak working set (MiB)',title='Bộ nhớ cao nhất của tiến trình')
    for ax in axes:
        ax.set_ylim(bottom=0); ax.grid(alpha=.15)
    handles,labels=axes[0].get_legend_handles_labels()
    figure.legend(handles,labels,loc='lower center',ncol=3,fontsize=9)
    figure.tight_layout(rect=[0,.16,1,1]); figure.savefig(ROOT/'results/vietnam/performance.png',dpi=160); plt.close(figure)
    figure,ax=plt.subplots(figsize=(9,4.5))
    top=counts.groupby('province_name').listing_rows.sum().sort_values().tail(10)
    top.plot.barh(ax=ax,color='#07858c')
    ax.set(xlabel='Số hàng tin đăng trong phần đã tải và làm sạch',ylabel='',title='10 nhãn tỉnh/thành có nhiều hàng nhất trong phần đã tải')
    figure.tight_layout(); figure.savefig(ROOT/'results/vietnam/listing_counts.png',dpi=160); plt.close(figure)


def build_report():
    source=read_json(ROOT/'data/vietnam/raw/source_metadata.json')
    profile=read_json(ROOT/'data/vietnam/processed/profile.json')
    env=read_json(ROOT/'results/vietnam/environment.json')
    summary=pd.read_csv(ROOT/'results/vietnam/summary.csv')
    counts=pd.read_csv(ROOT/'data/vietnam/processed/listing_counts.csv')
    manifest=pd.DataFrame(read_json(ROOT/'data/vietnam/benchmark/manifest.json'))
    if not summary.correct.all():
        raise AssertionError('Không xuất kết luận vì có kết quả truy vấn không khớp.')
    make_plots(summary,counts)
    largest=int(summary.rows.max())
    big=summary.loc[summary.rows==largest]
    fastest=big.loc[big.median_s.idxmin()]
    leanest=big.loc[big.median_peak_mib.idxmin()]
    comparison=summary[['rows','method','median_s','min_s','max_s','median_peak_mib','speedup','correct']].copy()
    comparison['method']=comparison.method.map(LABELS)
    comparison.columns=['Số dòng','Phương pháp','Trung vị (s)','Min (s)','Max (s)','Peak RAM (MiB)','Tăng tốc (lần)','Khớp']
    shards=pd.DataFrame(source['shards'])[['source_file','rows','transferred_bytes','bytes']]
    shards['transferred_bytes']/=1024**2; shards['bytes']/=1024**2
    shards.columns=['Shard nguồn','Hàng nguồn đã trích','Dữ liệu tải (MiB)','File trích cột (MiB)']
    missing=pd.DataFrame([dict(column=key,missing=value,pct=100*value/profile['raw_rows']) for key,value in profile['missing_by_column'].items()])
    sizes=manifest[['rows','csv_bytes','parquet_bytes','csv_write_s','parquet_write_s']].copy()
    sizes['csv_bytes']/=1024**2; sizes['parquet_bytes']/=1024**2
    sizes.columns=['Dòng','CSV (MiB)','Parquet (MiB)','Ghi CSV (s)','Ghi Parquet (s)']
    body=f'''<p class="eyebrow">BỔ SUNG NGUỒN DỮ LIỆU & THỰC NGHIỆM ĐỘC LẬP</p>
    <h1>Dữ liệu tin đăng bất động sản Việt Nam</h1>
    <p class="lead">Bùi Kiếm Khoa — n23dcn029<br>Lương Võ Hân Hân — n23dccn017</p>
    <p><a href="bao_cao.html">Quay lại báo cáo chính và thí nghiệm UCI</a> · <a href="thuyet_trinh.html">Mở thuyết trình đã bổ sung</a></p>
    <div class="cards"><div class="card"><strong>{profile['raw_rows']:,}</strong>hàng nguồn đã trích cột</div>
    <div class="card"><strong>{profile['clean_rows']:,}</strong>hàng đạt điều kiện phân tích</div>
    <div class="card"><strong>{largest:,}</strong>hàng tin đăng trong mức benchmark lớn nhất</div></div>
    <h2>1. Nguồn và phạm vi</h2>
    <p>Nhóm bổ sung dữ liệu từ <a href="{SOURCE}">TiniX AI — Vietnam Real Estate Listings</a>,
    phiên bản ghim tại commit <code>{source['revision']}</code>. Nhà phát hành công bố toàn bộ nguồn có
    {source['source_reported_rows']:,} hàng. Đồ án đã trích {len(source['shards'])} shard, tổng cộng {profile['raw_rows']:,} hàng;
    không tuyên bố đã tải toàn bộ nguồn. Đây là dữ liệu do bên thứ ba công bố, nhóm không trực tiếp thu thập hoặc xác minh từng tin.</p>
    <p>Giấy phép của nguồn: <a href="{source['license_url']}">CC BY-NC 4.0</a>; ghi công TiniX AI,
    giữ mục đích học tập phi thương mại. Các thay đổi của nhóm: trích cột, chuẩn hóa tên/kiểu,
    kiểm tra chất lượng, thêm cột nguồn/giá đơn vị/tháng/cờ giá trị lớn và lấy mẫu phục vụ benchmark.</p>
    <p class="note">Tin đăng không tương đương giao dịch đã chốt. Nguồn mô tả có cả tin bán và cho thuê,
    nhưng schema trích không có nhãn phân biệt. Không diễn giải trung bình price_vnd thành giá bán thị trường.
    Các bản ghi có thể trùng tin hoặc cùng bất động sản; không gọi số hàng là số căn nhà duy nhất.</p>
    {table(shards)}
    <p>Chỉ tải 9 cột có cấu trúc bằng HTTP Range của file Parquet; bỏ tiêu đề, mô tả và địa chỉ chi tiết.
    Mỗi dải byte được kiểm tra Content-Range và số byte; số hàng trích phải bằng metadata Parquet.
    SHA-256 của từng bản trích được lưu để kiểm tra lại. Bản trích không phải bản sao đầy đủ 19 cột của shard.</p>
    <p>Chọn shard theo thứ tự tên nên phần đã tải không phải mẫu ngẫu nhiên của toàn nguồn.
    Tháng quan sát trong phần sạch: {profile['first_month']} đến {profile['last_month']}.
    Giữ nhãn địa phương của nguồn, không tự đổi sang đơn vị hành chính mới.</p>
    <h2>2. Các cột và ý nghĩa</h2>
    <ul><li><code>province_name, district_name, property_type_name</code>: địa phương và loại bất động sản do nguồn ghi.</li>
    <li><code>price_vnd, area_m2</code>: giá đăng bằng VND và diện tích m²; giữ float64.</li>
    <li><code>floor_count, bedroom_count, bathroom_count</code>: số tầng/phòng; có thể thiếu.</li>
    <li><code>published_at, published_month</code>: thời điểm gốc và tháng suy ra.</li>
    <li><code>source_shard, source_row</code>: định vị hàng gốc trong phiên bản đã ghim, không phải ID bất động sản.</li>
    <li><code>price_per_m2_vnd, extreme_value_flag</code>: giá đăng chia diện tích và cờ giá &gt; 1.000 tỷ hoặc diện tích &gt; 10.000 m².
    Cờ chỉ để xem xét, không tự xóa hàng.</li></ul>
    <h2>3. Chất lượng dữ liệu</h2>
    <p>Loại {profile['removed_missing_core']:,} hàng thiếu giá/diện tích/tỉnh/loại nhà;
    loại thêm {profile['removed_invalid_core']:,} hàng có giá hoặc diện tích không dương/không hữu hạn.
    Thiếu số phòng hoặc số tầng không làm loại hàng. Số tầng/phòng âm hoặc không nguyên được chuyển thành thiếu;
    số 0 vẫn giữ vì có thể chỉ không có phòng/tầng loại đó.</p>
    {table(missing)}
    <p>Có {profile['duplicate_projection_rows']:,} hàng lặp theo chữ ký 9 cột đã trích sau làm sạch.
    Nhóm giữ các hàng này vì mất các cột khác và không có ID tin để xác nhận trùng. Các số đếm vì thế là số bản ghi trong nguồn.
    Đếm trùng này không xác nhận nguồn có bấy nhiêu tin trùng thực sự.</p>
    <h2>4. Khám phá phần dữ liệu đã tải</h2>{embed('listing_counts.png')}
    <p>Biểu đồ mô tả phân bố nhãn trong phần đã tải và qua quy tắc lọc, không đo tổng cung thị trường hay số giao dịch.
    Phân bố có thể bị lệch bởi shard được chọn, lịch thu thập và tin lặp.
    Nhóm tránh diễn giải giá bán trung bình theo vùng khi thiếu nhãn bán/thuê.</p>
    <h2>5. Thiết kế benchmark mới</h2>
    <p>Lấy mẫu không hoàn lại từ {profile['clean_rows']:,} hàng sạch theo thứ tự hash của ID hàng nguồn và seed 42,
    với phiên bản DuckDB được ghim.
    Các mức nhỏ là tập con của mức lớn trong cùng thứ tự lấy mẫu; không sao chép hoặc thêm nhiễu để đủ số dòng.
    Nếu số hàng sạch không đủ, chương trình báo lỗi và yêu cầu giảm kích thước hoặc tải thêm shard.</p>
    <pre>SELECT province_name, COUNT(*) AS count, SUM(price_vnd) AS price_sum
FROM read_parquet(?)
WHERE area_m2 BETWEEN 50 AND 150
  AND price_vnd BETWEEN 1 AND 10000000000
GROUP BY province_name ORDER BY province_name;</pre>
    <p>Giới hạn giá và diện tích là định nghĩa tải truy vấn, không phải quy tắc kết luận tin thật/giả.
    Tổng và mean giá trong truy vấn là kết quả tính toán để đối chiếu engine; không được báo như thống kê giá bán thị trường.
    Thí nghiệm dùng cùng sáu phương pháp như UCI nhưng có truy vấn và schema riêng.</p>
    <p>Mỗi mức/phương pháp có {env['repeats']} lần đo trong tiến trình riêng, thứ tự xáo bằng seed 42.
    Thời gian tính đọc, lọc, tổng hợp; loại khởi động Python và import Pandas. Import lười DuckDB và mở kết nối vẫn được tính.
    RAM là peak working set toàn tiến trình trên Windows. Cache hệ điều hành không xóa; threads DuckDB=1,
    memory_limit=1GB; các biến môi trường luồng đặt 1 nhưng IO scheduling thư viện có thể khác.</p>
    <p>Nhóm và count phải khớp chính xác; sum/mean dùng rtol=10⁻⁹, atol=10⁻⁶.
    Môi trường: {html.escape(env['platform'])}, Python {env['python'].split()[0]}, RAM {env['total_ram_gib']:.2f} GiB.
    Toàn bộ phiên bản thư viện được lưu trong results/vietnam/environment.json.</p>
    <h2>6. Kết quả thực tế trên tin đăng Việt Nam</h2>{embed('performance.png')}{table(comparison)}
    <p>Ở {largest:,} dòng, {LABELS[fastest.method]} nhanh nhất với trung vị {fastest.median_s:.4f} giây,
    bằng {fastest.speedup:.2f} lần baseline; {LABELS[leanest.method]} có peak RAM trung vị thấp nhất
    ({leanest.median_peak_mib:.1f} MiB). Tất cả {len(summary)*env['repeats']} lượt đo cho thống kê khớp với CSV toàn bộ.</p>
    <p>Kết quả này độc lập với số đo UCI mô phỏng. Hai truy vấn khác nhau nên không lấy tỷ số thời gian giữa hai nguồn
    để kết luận bên nào là nguồn dữ liệu dễ xử lý hơn. Xem min/max để nhận biết dao động của từng phương pháp.</p>
    <h2>7. Dung lượng và chi phí chuẩn bị</h2>{table(sizes)}
    <p>Thời gian ghi được đo riêng, không cộng vào thời gian truy vấn. Chưa đo chuyển đổi CSV sang Parquet hoặc hòa vốn.
    Lợi ích tải ít cột qua HTTP Range chỉ là cách tiếp nhận dữ liệu của bản bổ sung, không nằm trong biểu đồ benchmark cục bộ.</p>
    <h2>8. Kết luận bổ sung và giới hạn</h2>
    <p>Đồ án đã có thêm nguồn bản ghi tin đăng Việt Nam có quy mô lớn hơn mẫu UCI và có thử nghiệm trên hàng nguồn thực,
    thay cho việc chỉ thử tải bằng mô phỏng. Kết quả vẫn chỉ áp dụng cho phần đã tải, truy vấn và môi trường này.</p>
    <p>Mức một triệu hàng chưa vượt RAM 16 GB. Chưa chứng minh xử lý ngoài RAM hay hệ phân tán.
    Dữ liệu do bên thứ ba xử lý; không có kiểm định độc lập độ xác thực của từng tin, tính đầy đủ của nguồn,
    nhãn bán/thuê hoặc tính duy nhất của bất động sản. Chỉ có ba lần lặp mặc định, chưa có khoảng tin cậy.</p>
    <h2>9. Chạy lại</h2><pre>python -m src.vietnam_data --shards 4
python run_vietnam.py
python run_vietnam.py --skip-prepare
python -m unittest discover -s tests -v</pre>
    <p>Lệnh đầu cần mạng; các lệnh sau dùng bản trích đã kèm. Chạy bằng Python trong môi trường .venv của bài theo README.
    Đọc source_metadata.json và profile.json để kiểm tra phiên bản, số hàng và quy tắc lọc.</p>
    <h2>10. Nguồn</h2><p>TiniX AI (2026). <a href="{SOURCE}">Tinix Vietnam Real Estate Listings 2025–2026</a>.
    Bản commit {source['revision']}. <a href="{source['license_url']}">CC BY-NC 4.0</a>.
    Các kỹ thuật dùng theo <a href="https://pandas.pydata.org/docs/user_guide/scale.html">tài liệu Pandas</a>
    và <a href="https://duckdb.org/docs/current/data/parquet/overview">tài liệu DuckDB/Parquet</a>.</p>'''
    (ROOT/'report/bo_sung_du_lieu_viet_nam.html').write_text('<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Dữ liệu Việt Nam — bổ sung đồ án</title><style>'+STYLE+'</style><main>'+body+'</main></html>',encoding='utf-8')
    attach_main_files()


def attach_main_files():
    """Gắn liên kết và hai trang bổ sung, có thể gọi lại mà không lặp nội dung."""
    if not (ROOT/'report/bo_sung_du_lieu_viet_nam.html').exists():
        return
    profile=read_json(ROOT/'data/vietnam/processed/profile.json')
    main_path=ROOT/'report/bao_cao.html'
    text=main_path.read_text(encoding='utf-8')
    text=re.sub(r'<!--vietnam-update-start-->.*?<!--vietnam-update-end-->','',text,flags=re.S)
    banner=f'''<!--vietnam-update-start--><aside class="note"><strong>Bản mở rộng đã có thêm dữ liệu Việt Nam:</strong>
    {profile['raw_rows']:,} hàng nguồn đã trích, {profile['clean_rows']:,} hàng đạt quy tắc lọc.
    <a href="bo_sung_du_lieu_viet_nam.html">Đọc báo cáo bổ sung và số đo trên tin đăng Việt Nam</a>.
    Phần bên dưới trình bày thí nghiệm UCI ban đầu; hai nguồn được đánh giá riêng.</aside><!--vietnam-update-end-->'''
    main_path.write_text(text.replace('<main>','<main>'+banner,1),encoding='utf-8')
    slides_path=ROOT/'report/thuyet_trinh.html'
    slides=slides_path.read_text(encoding='utf-8')
    slides=re.sub(r'<!--validation-slides-start-->.*?<!--validation-slides-end-->','',slides,flags=re.S)
    slides=re.sub(r'<!--vietnam-slides-start-->.*?<!--vietnam-slides-end-->','',slides,flags=re.S)
    slides=re.sub(r'<!--upgrade-slides-start-->.*?<!--upgrade-slides-end-->','',slides,flags=re.S)
    extra=f'''<!--vietnam-slides-start--><section class="slide" id="s13"><h1>Bổ sung nguồn Việt Nam</h1>
    <p class="lead">{profile['raw_rows']:,} hàng nguồn → {profile['clean_rows']:,} hàng đạt quy tắc lọc.</p>
    <p>Nguồn TiniX AI, CC BY-NC 4.0. Trích 9 cột của {len(profile['per_shard'])} shard, giữ dấu vết hàng gốc; không tạo thêm hàng mô phỏng.</p>
    <p>Tin đăng khác giao dịch đã chốt. Thiếu nhãn bán/thuê, có thể lặp tin. Không coi giá trung bình là giá bán thị trường.</p>
    <p><a href="bo_sung_du_lieu_viet_nam.html">Báo cáo và nguồn của phần bổ sung</a></p><span class="num">13/14</span></section>
    <section class="slide" id="s14"><h1>Benchmark trên hàng tin đăng nguồn</h1>{embed('performance.png')}
    <p>Truy vấn riêng: diện tích 50–150 m², giá 1 VND–10 tỷ VND; nhóm theo tỉnh. Kiểm tra thống kê giữa sáu cách xử lý.</p>
    <span class="num">14/14</span></section><!--vietnam-slides-end-->'''
    slides=slides.replace('</main>',extra+'</main>',1)
    slides=re.sub(r'(<span class="num">\d+)/\d+(</span>)',r'\1/14\2',slides)
    slides=slides.replace('Math.min(12,i+', 'Math.min(14,i+')
    slides_path.write_text(slides,encoding='utf-8')
    notebook_path=ROOT/'notebooks/01_do_an.ipynb'
    notebook=read_json(notebook_path)
    notebook['cells']=[c for c in notebook['cells'] if not c['id'].startswith('vietnam-')]
    notebook['cells'].extend([
        dict(cell_type='markdown',id='vietnam-intro',metadata={},source=['## 6. Nguồn Việt Nam bổ sung\n','Dữ liệu tin đăng bên thứ ba, không phải giao dịch xác minh. Số đo nằm riêng trong `results/vietnam/`. Không trộn đơn vị với UCI.']),
        dict(cell_type='code',id='vietnam-data',metadata={},execution_count=None,outputs=[],source=['vn_profile = json.loads((ROOT / "data/vietnam/processed/profile.json").read_text(encoding="utf-8"))\n','print("Hàng nguồn:", vn_profile["raw_rows"], "Hàng sạch:", vn_profile["clean_rows"])\n','vn_summary = pd.read_csv(ROOT / "results/vietnam/summary.csv")\n','assert vn_summary.correct.all()\n','vn_summary[["rows", "method", "median_s", "median_peak_mib", "speedup"]]'])])
    notebook_path.write_text(json.dumps(notebook,ensure_ascii=False,indent=2),encoding='utf-8')
    if (ROOT/'report/nang_cap_he_thong.html').exists():
        from src.upgrade_report import attach_upgrade_files
        attach_upgrade_files()
