"""Tạo báo cáo và thuyết trình HTML từ số đo thật; không điền số minh họa."""
import base64
import html
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from src.prepare import ROOT, COLS
from src.queries import LABELS, METHODS

STYLE = '''
*{box-sizing:border-box}body{margin:0;background:#edf2f6;color:#172b42;font:16px/1.65 'Segoe UI',Arial,sans-serif}
main{max-width:1100px;margin:auto;background:white;padding:64px 72px}h1{font-size:38px;line-height:1.2;color:#103954}
h2{font-size:26px;color:#087d86;margin-top:40px}h3{color:#103954}p{margin:12px 0}small,.muted{color:#526477}
table{width:100%;border-collapse:collapse;font-size:13px;margin:20px 0}th{background:#103954;color:white;text-align:left}
th,td{padding:9px;border-bottom:1px solid #d9e2e9}tr:nth-child(even){background:#f0f6f8}img{max-width:100%;height:auto}
.eyebrow{color:#087d86;font-weight:700;letter-spacing:2px}.lead{font-size:20px}.note{border-left:4px solid #d8a238;background:#fff7e5;padding:15px 20px}
.cards{display:flex;gap:16px;margin:24px 0}.card{flex:1;background:#eaf5f5;padding:20px;border-radius:8px}.card strong{display:block;font-size:30px;color:#087d86}
pre{white-space:pre-wrap;word-break:break-word;background:#eff4f7;padding:20px;font-size:13px}a{color:#087d86}
.cover{padding-bottom:34px;border-bottom:2px solid #087d86}footer{margin-top:40px;color:#526477;font-size:13px}
@media print{body{background:white;font-size:11pt}main{padding:0;max-width:none}h2,h3{break-after:avoid}table,img,.card{break-inside:avoid}a{color:inherit}pre{font-size:9pt}.cover{break-after:page}.no-print{display:none}@page{size:A4;margin:18mm}}
'''


def image_tag(name):
    payload = base64.b64encode((ROOT/'results'/name).read_bytes()).decode()
    return f'<img alt="{html.escape(name)}" src="data:image/png;base64,{payload}">'


def table(frame):
    return frame.to_html(index=False, border=0, float_format=lambda x: f'{x:,.3f}', escape=True)


def plots(base, summary, manifest):
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':10, 'axes.spines.top':False,
                         'axes.spines.right':False, 'figure.facecolor':'white'})
    fig, axes = plt.subplots(1, 2, figsize=(11,4.2))
    axes[0].hist(base.price_10k_twd_per_ping, bins=24, color='#07858c', edgecolor='white')
    axes[0].set(xlabel='Giá (10.000 TWD / ping)', ylabel='Số giao dịch', title='Phân bố giá trên dữ liệu gốc')
    axes[1].scatter(base.mrt_distance_m, base.price_10k_twd_per_ping, color='#07858c', s=22, alpha=.6)
    axes[1].set(xlabel='Khoảng cách đến MRT (m)', ylabel='Giá (10.000 TWD / ping)', title='Khoảng cách MRT và giá')
    fig.tight_layout(); fig.savefig(ROOT/'results/eda.png', dpi=160); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12,4.8))
    colors = ['#64748b','#a16207','#8b5cf6','#0284c7','#0d9488','#e05d38']
    for method, color in zip(METHODS, colors):
        sub = summary[summary.method == method].sort_values('rows')
        for ax, metric in zip(axes, ['median_s','median_peak_mib']):
            ax.plot(sub.rows/1000, sub[metric], marker='o', label=LABELS[method], color=color)
    axes[0].set(xlabel='Số dòng (nghìn)', ylabel='Thời gian trung vị (giây)', title='Đọc + lọc + tổng hợp')
    axes[1].set(xlabel='Số dòng (nghìn)', ylabel='Peak working set (MiB)', title='Bộ nhớ cao nhất của tiến trình')
    for ax in axes:
        ax.grid(alpha=.15); ax.set_ylim(bottom=0)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=3, fontsize=9)
    fig.tight_layout(rect=[0,.16,1,1]); fig.savefig(ROOT/'results/performance.png', dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8,4))
    x=np.arange(len(manifest)); width=.35
    ax.bar(x-width/2, manifest.csv_bytes/1024**2, width, label='CSV', color='#64748b')
    ax.bar(x+width/2, manifest.parquet_bytes/1024**2, width, label='Parquet / Snappy', color='#07858c')
    ax.set_xticks(x, [f'{n:,}' for n in manifest.rows]); ax.set(xlabel='Số dòng',ylabel='Dung lượng (MiB)',title='Dung lượng dữ liệu mô phỏng')
    ax.legend(); fig.tight_layout(); fig.savefig(ROOT/'results/storage.png',dpi=160); plt.close(fig)


def build_deliverables():
    out = ROOT/'report'; out.mkdir(exist_ok=True)
    base = pd.read_csv(ROOT/'data/processed/real_estate_clean.csv')
    summary = pd.read_csv(ROOT/'results/summary.csv')
    manifest = pd.DataFrame(json.loads((ROOT/'data/benchmark/manifest.json').read_text(encoding='utf-8')))
    manifest = manifest[manifest.rows.isin(summary.rows.unique())]
    env = json.loads((ROOT/'results/environment.json').read_text(encoding='utf-8'))
    audit = json.loads((ROOT/'data/processed/source_metadata.json').read_text(encoding='utf-8'))['audit']
    plots(base, summary, manifest)
    largest = int(summary.rows.max()); large = summary[summary.rows == largest]
    fastest = large.loc[large.median_s.idxmin()]; leanest = large.loc[large.median_peak_mib.idxmin()]
    disk = manifest.loc[manifest.rows == largest].iloc[0]
    saving = (1-disk.parquet_bytes/disk.csv_bytes)*100
    corr = base[['house_age','mrt_distance_m','convenience_stores','price_10k_twd_per_ping']].corr()
    show = summary[['rows','method','median_s','min_s','max_s','median_peak_mib','speedup','correct']].copy()
    show['method'] = show.method.map(LABELS)
    show.columns = ['Số dòng','Phương pháp','Trung vị (s)','Min (s)','Max (s)','Peak RAM (MiB)','Tăng tốc (lần)','Khớp kết quả']
    storage = manifest[['rows','csv_bytes','parquet_bytes','csv_write_s','parquet_write_s']].copy()
    storage['csv_bytes']/=1024**2; storage['parquet_bytes']/=1024**2
    storage.columns=['Số dòng','CSV (MiB)','Parquet (MiB)','Ghi CSV (s)','Ghi Parquet (s)']
    descriptions = [
        ('source_id','int32','Mã giao dịch gốc; lặp lại trong dữ liệu mô phỏng'),
        ('transaction_decimal','float64','Thời điểm dạng số thập phân, giữ nguyên quy ước UCI'),
        ('house_age','float64','Tuổi nhà, năm'),('mrt_distance_m','float64','Khoảng cách đến trạm MRT gần nhất, mét'),
        ('convenience_stores','int16','Số cửa hàng tiện lợi trong phạm vi đi bộ'),
        ('latitude / longitude','float64','Tọa độ theo độ'),
        ('price_10k_twd_per_ping','float64','Giá theo 10.000 TWD/ping; không phải tổng giá căn nhà'),
        ('age_band','category / text','0–10 gồm 10; 10–30 gồm 30; 30+ lớn hơn 30'),
        ('price_twd_per_m2','float64','Giá quy đổi xấp xỉ theo 1 ping = 3,3 m² của nguồn'),
        ('price_iqr_flag','bool','Chỉ ở dữ liệu sạch: đánh dấu giá ngoài hàng rào IQR, vẫn giữ hàng'),
        ('record_id / is_synthetic','int64 / bool','Chỉ ở dữ liệu mô phỏng: ID duy nhất và cờ True')]
    dictionary = table(pd.DataFrame(descriptions, columns=['Cột','Kiểu / cách lưu','Ý nghĩa']))
    sources = '''<ol>
    <li>Yeh, I. (2018). <a href="https://archive.ics.uci.edu/dataset/477/real+estate+valuation+data+set">Real Estate Valuation — UCI</a>. DOI: 10.24432/C5J30W. CC BY 4.0; nhóm đổi tên, kiểm tra và tạo dữ liệu mô phỏng từ dữ liệu này.</li>
    <li><a href="https://pandas.pydata.org/docs/user_guide/scale.html">Pandas: Scaling to large datasets</a> — đọc ít cột, chọn kiểu và chunk.</li>
    <li><a href="https://duckdb.org/docs/current/data/parquet/overview">DuckDB: Reading and Writing Parquet Files</a> — đọc cột và đẩy điều kiện lọc xuống bộ đọc.</li>
    </ol>'''
    cover = '''<section class="cover"><p class="eyebrow">ĐỒ ÁN GIỮA KÌ · NHẬP MÔN KHOA HỌC DỮ LIỆU</p>
    <h1>Xây dựng bộ dữ liệu bất động sản và đánh giá các phương pháp tối ưu hiệu năng xử lý dữ liệu bằng Python</h1>
    <p class="lead">Bùi Kiếm Khoa — n23dcn029<br>Lương Võ Hân Hân — n23dccn017</p>
    <p>Dữ liệu thực: UCI Real Estate Valuation · Dữ liệu thử tải: mô phỏng có seed</p>
    <p class="muted">Báo cáo thực nghiệm · Tháng 10/2026</p></section>'''
    abstract = f'''<h2>1. Tóm tắt và mục tiêu</h2>
    <p>Đồ án khảo sát chi phí xử lý dữ liệu bất động sản khi số bản ghi tăng lên. Quy trình gồm tiếp nhận dữ liệu,
    kiểm tra chất lượng, chuẩn hóa lược đồ, khám phá dữ liệu và thực nghiệm sáu cách đọc, lọc, tổng hợp.
    Câu hỏi nghiên cứu: lựa chọn cột, kiểu dữ liệu, xử lý theo khối và định dạng lưu trữ ảnh hưởng thế nào đến thời gian và RAM?</p>
    <div class="cards"><div class="card"><strong>{len(base)}</strong>giao dịch gốc sau làm sạch</div>
    <div class="card"><strong>{largest:,}</strong>dòng mô phỏng ở mức lớn nhất</div>
    <div class="card"><strong>{len(summary)*env['repeats']}</strong>lượt đo có kiểm tra kết quả</div></div>
    <p>Ở mức {largest:,} dòng, {LABELS[fastest.method]} đạt thời gian trung vị thấp nhất ({fastest.median_s:.4f} giây),
    còn {LABELS[leanest.method]} có peak RAM trung vị thấp nhất ({leanest.median_peak_mib:.1f} MiB).
    Kết luận này chỉ áp dụng cho truy vấn, phân bố dữ liệu và môi trường đã đo.</p>'''
    data = f'''<h2>2. Nguồn dữ liệu và lược đồ</h2>
    <p>Nguồn gốc là bộ Real Estate Valuation của UCI, tác giả I-Cheng Yeh, gồm 414 quan sát tại Sindian,
    New Taipei City, Đài Loan. Nhóm giữ dữ liệu gốc trong data/raw và lưu bản xử lý trong data/processed.</p>
    <p>Không có diện tích căn nhà hay tổng giá bán trong nguồn này. Giá là giá trên một đơn vị diện tích;
    nhóm không tự thêm diện tích hoặc đổi đơn vị thành VND. Thời điểm dạng thập phân được giữ nguyên để tránh diễn giải sai tháng.</p>
    {dictionary}<p class="note">Dữ liệu thật phục vụ EDA. Dữ liệu mô phỏng phục vụ đo hiệu năng.
    Một triệu dòng mô phỏng không tương đương một triệu giao dịch được quan sát ngoài thực tế.</p>
    <h2>3. Kiểm tra và làm sạch</h2><p>Các cột được đổi tên, ép sang số; hàng thiếu hoặc không hữu hạn được loại.
    Kiểm tra tuổi nhà, khoảng cách và số cửa hàng không âm; số cửa hàng nguyên; tọa độ trong miền hợp lệ;
    giá dương và ID nguyên dương. ID trùng giữ bản đầu tiên. Những hàng có cùng thuộc tính nhưng khác ID không mặc định là trùng giao dịch.</p>
    {table(pd.DataFrame([audit]))}<p>Ngoại lệ giá theo IQR chỉ được đánh dấu, không bị xóa tự động vì giao dịch giá cao vẫn có thể hợp lệ.
    Bản dữ liệu gốc sạch không có giá trị thiếu, không cần tạo ra lỗi rồi tuyên bố đã sửa lỗi thực tế.</p>'''
    eda = f'''<h2>4. Khám phá dữ liệu thật</h2>{image_tag('eda.png')}
    <p>Giá trung vị là {base.price_10k_twd_per_ping.median():.2f}, trung bình {base.price_10k_twd_per_ping.mean():.2f}
    (10.000 TWD/ping). Tuổi nhà trung vị {base.house_age.median():.2f} năm.
    Tương quan Pearson giữa khoảng cách MRT và giá là {corr.loc['mrt_distance_m','price_10k_twd_per_ping']:.3f}.
    Đây là liên hệ trong mẫu, không chứng minh khoảng cách gây ra thay đổi giá.</p>
    {table(base[['house_age','mrt_distance_m','convenience_stores','price_10k_twd_per_ping']].describe().round(3).reset_index())}
    <h2>5. Tạo dữ liệu thử tải</h2><p>Lấy mẫu có hoàn lại nguyên hàng từ dữ liệu sạch, sau đó thêm nhiễu nhỏ vào tuổi nhà,
    khoảng cách và giá để giảm sự lặp nguyên bản. Các trường còn lại giữ theo hàng được chọn. Dùng seed 42 và ghi theo khối 100.000 hàng.
    ID thử tải là duy nhất, source_id ghi lại hàng gốc, is_synthetic luôn là True. Nhóm không huấn luyện mô hình hay suy luận thị trường từ phần này.</p>
    <p>CSV và Parquet được ghi từ cùng khối dữ liệu, cùng giá trị float64. Giữ float64 cho giá và cột lọc để tránh thay đổi điều kiện ở biên.
    Trường nhóm có ít giá trị nên phù hợp category; số nguyên nguồn dùng kiểu nhỏ hơn sau khi kiểm tra miền.</p>'''
    methods = f'''<h2>6. Phương pháp tối ưu</h2>
    <table><tr><th>Phương pháp</th><th>Thay đổi và đánh đổi</th></tr>
    <tr><td>CSV toàn bộ</td><td>Pandas nạp tất cả các cột; mốc so sánh.</td></tr>
    <tr><td>CSV chọn cột</td><td>usecols chỉ đọc 4 cột truy vấn; CSV vẫn phải được phân tích theo hàng.</td></tr>
    <tr><td>CSV chọn cột + kiểu</td><td>Thêm dtype rõ ràng và category cho age_band; giữ float64 cho số thực.</td></tr>
    <tr><td>CSV từng khối</td><td>Khối {env['chunksize']:,} hàng. Lọc và cộng count, sum từng nhóm, cuối cùng mean = tổng sum / tổng count.</td></tr>
    <tr><td>Parquet chọn cột</td><td>Pandas đọc đúng 4 cột từ file cột có nén Snappy. Cần chi phí chuẩn bị file trước.</td></tr>
    <tr><td>DuckDB + Parquet</td><td>SQL trực tiếp trên file; threads=1, memory_limit=1GB. Kế hoạch có thể đẩy chọn cột và lọc xuống bộ đọc.</td></tr></table>
    <p>Không lấy trung bình các trung bình theo khối: khối có số hàng được chọn khác nhau phải có trọng số khác nhau.
    Cách cộng sum/count phù hợp với bài này; trung vị chính xác không thể tính bằng cách gộp trung vị các khối.</p>
    <h2>7. Thiết kế thực nghiệm</h2><p>Truy vấn chung: chọn nhà tuổi ≤ 30 năm và cách MRT ≤ 1.000 mét;
    nhóm theo age_band, trả về count, tổng giá đơn vị và giá đơn vị trung bình.</p>
    <pre>SELECT age_band, COUNT(*) AS count, SUM(price_10k_twd_per_ping) AS price_sum
FROM read_parquet(?)
WHERE house_age &lt;= 30 AND mrt_distance_m &lt;= 1000
GROUP BY age_band ORDER BY age_band;</pre>
    <p>Mỗi tổ hợp mức dữ liệu/phương pháp chạy {env['repeats']} lần trong các tiến trình riêng; thứ tự phương pháp được xáo bằng seed 42.
    Thời gian dùng perf_counter, tính cả đọc, lọc và tổng hợp. Không tính tạo dữ liệu hay khởi động trình thông dịch/import Pandas.
    DuckDB được import khi gọi phương pháp nên chi phí import riêng, mở kết nối và cấu hình của nó nằm trong thời gian đo.
    Kết quả trình bày trung vị cùng min/max. Không chủ động xóa bộ đệm hệ điều hành: đây không phải benchmark cold-cache.</p>
    <p>RAM là peak working set của toàn tiến trình trên Windows, bao gồm runtime và thư viện; không phải kích thước riêng DataFrame.
    Bộ giám sát lấy mẫu 5 ms và dùng thêm high-water mark do Windows cung cấp. Trên nền tảng không có high-water mark, phép lấy mẫu có thể bỏ lỡ đỉnh ngắn.
    Các biến môi trường luồng tính toán đặt bằng 1; cách lập lịch IO của thư viện vẫn có thể khác nhau.</p>
    <p>Nhóm và count phải khớp tuyệt đối với CSV toàn bộ; sum và mean kiểm tra với rtol=10⁻⁹, atol=10⁻⁶.
    Sai khác ngoài ngưỡng làm dừng xuất báo cáo kết luận. CSV/Parquet được tạo từ cùng khối, không đo trên hai tập khác nội dung.</p>
    <p>Môi trường: {html.escape(env['platform'])}; Python {env['python'].split()[0]}; RAM hệ thống {env['total_ram_gib']:.2f} GiB;
    {env['logical_cpus']} CPU logic. Thư viện: {html.escape(', '.join(k+' '+v for k,v in env['packages'].items()))}.</p>'''
    results = f'''<h2>8. Kết quả thực nghiệm</h2>{image_tag('performance.png')}{table(show)}
    <p>Tăng tốc = thời gian trung vị CSV toàn bộ / thời gian trung vị phương pháp; lớn hơn 1 là nhanh hơn.
    Giảm RAM = (1 − peak RAM phương pháp / peak RAM CSV toàn bộ) × 100%; số âm nghĩa là tốn RAM hơn.
    {LABELS[fastest.method]} đạt {fastest.speedup:.2f} lần ở mức lớn nhất. Không mặc định mọi cách tối ưu đều cải thiện mọi chỉ số.</p>
    <h3>Chi phí lưu trữ và chuẩn bị</h3>{image_tag('storage.png')}{table(storage)}
    <p>Ở mức lớn nhất, Parquet giảm {saving:.1f}% dung lượng so với CSV trong thử nghiệm này.
    Thời gian ghi là tổng thời gian serialize/ghi từng khối, Parquet gồm chuyển Arrow và đóng writer; không gồm sinh dữ liệu.
    Đây không phải phép đo chuyển CSV sang Parquet và không đủ để kết luận thời điểm hòa vốn của việc chuyển đổi.</p>'''
    discussion = '''<h2>9. Thảo luận và giới hạn</h2>
    <p>Chọn ít cột giảm dữ liệu được vật chất hóa trong RAM. Định dạng cột có thể tránh đọc cột không dùng và giảm chi phí phân tích chuỗi.
    Chunk giữ lượng dữ liệu đang xử lý trong giới hạn theo kích thước khối, nhưng có thêm chi phí vòng lặp và gộp kết quả, nên không nhất thiết nhanh nhất.</p>
    <p>Dữ liệu bootstrap từ 414 hàng có độ đa dạng thấp; các cột giữ nguyên có thể nén tốt hơn dữ liệu thị trường lớn thực tế.
    Bộ thử tải lớn nhất vẫn có thể vừa RAM, nên kết quả chứng minh xu hướng trong phạm vi thử nghiệm, chưa chứng minh xử lý dữ liệu vượt RAM.
    Chưa đánh giá nhiều người dùng đồng thời, mạng, cơ sở dữ liệu giao dịch, chỉ mục, máy chủ phân tán hoặc độ trễ giao diện.</p>
    <p>Chỉ có ba lần lặp mặc định, không có khoảng tin cậy thống kê. Kết quả có thể thay đổi theo máy, tải nền, cache, kiểu dữ liệu và độ chọn lọc truy vấn.
    Ngưỡng memory_limit của DuckDB áp dụng cho bộ quản lý bộ nhớ của nó; không phải giới hạn cứng toàn bộ RAM tiến trình.</p>
    <h2>10. Kết luận và hướng mở rộng</h2>
    <p>Đồ án hoàn thành một quy trình dữ liệu có thể chạy lại: nguồn gốc rõ, kiểm tra chất lượng, khám phá,
    mở rộng tải có nhãn mô phỏng và so sánh sáu phương án bằng số đo có kiểm tra đúng kết quả.
    Lựa chọn thực tế cần cân bằng tốc độ, RAM, chi phí chuẩn bị và độ phức tạp triển khai theo tác vụ cụ thể.</p>
    <p>Có thể mở rộng bằng nguồn giao dịch thật lớn hơn, thêm phép join/sắp xếp, thay đổi chunk size,
    đo dưới giới hạn RAM có kiểm soát, thử Parquet phân vùng và đo nhiều lần hơn. Những phần này chưa nằm trong kết quả hiện tại.</p>
    <h2>11. Tài liệu tham khảo</h2>'''+sources
    body = cover+abstract+data+eda+methods+results+discussion
    (out/'bao_cao.html').write_text('<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Báo cáo đồ án bất động sản</title><style>'+STYLE+'</style><main>'+body+'<footer>Báo cáo được tạo từ results/summary.csv; giữ kết quả thô trong results/runs.json.</footer></main></html>', encoding='utf-8')
    create_slides(out, cover, base, largest, fastest, leanest, saving, show, sources)
    create_notebook()
    if (ROOT/'report/bo_sung_du_lieu_viet_nam.html').exists():
        from src.vietnam_report import attach_main_files
        attach_main_files()


def create_slides(out, cover, base, largest, fastest, leanest, saving, show, sources):
    slides = [cover,
        '<h1>Bài toán</h1><p class="lead">Dữ liệu tăng → tốn thời gian đọc, tốn RAM, khó tổng hợp.</p><h2>Câu hỏi</h2><p>Đổi cách đọc và lưu trữ giúp cải thiện bao nhiêu, khi vẫn trả về cùng kết quả?</p>',
        f'<h1>Dữ liệu & tính trung thực</h1><p class="lead">{len(base)} giao dịch thật từ UCI → EDA.</p><p class="lead">Đến {largest:,} dòng mô phỏng → đo tải.</p><p>Bootstrap nguyên hàng + nhiễu nhỏ, seed 42; có source_id, record_id, is_synthetic. Không đại diện thị trường Việt Nam.</p><p>Giá: 10.000 TWD/ping. Không có tổng giá căn nhà.</p>',
        '<h1>Quy trình dữ liệu</h1><p class="lead">Nguồn UCI → kiểm tra miền, thiếu, trùng ID → dữ liệu sạch → EDA → sinh tải → đo → đối chiếu kết quả.</p><p>Giữ dữ liệu gốc. Ngoại lệ giá chỉ đánh dấu. Đầu ra gồm CSV, Parquet và thông tin nguồn.</p>',
        '<h1>Khám phá dữ liệu thật</h1>'+image_tag('eda.png')+'<p>Tương quan không chứng minh quan hệ nhân quả.</p>',
        '<h1>Sáu cách xử lý</h1><ol><li>CSV toàn bộ — baseline</li><li>CSV chọn cột</li><li>CSV chọn cột + dtype/category</li><li>CSV từng khối — cộng sum/count</li><li>Parquet chọn cột</li><li>DuckDB truy vấn Parquet</li></ol>',
        '<h1>Đo thế nào?</h1><p class="lead">Cùng điều kiện: tuổi nhà ≤ 30 và MRT ≤ 1.000 m.</p><p>Nhóm tuổi nhà; count, tổng và giá đơn vị trung bình. Ba lần lặp mặc định, tiến trình riêng, xáo thứ tự.</p><p>Thời gian đọc + truy vấn; peak RAM toàn tiến trình. Cache hệ điều hành không xóa. Kiểm tra count chính xác, số thực trong sai số quy định.</p>',
        '<h1>Kết quả thời gian và RAM</h1>'+image_tag('performance.png'),
        f'<h1>Kết quả ở {largest:,} dòng</h1><p class="lead">Nhanh nhất: {LABELS[fastest.method]} — {fastest.median_s:.4f} s, {fastest.speedup:.2f} lần baseline.</p><p class="lead">Peak RAM thấp nhất: {LABELS[leanest.method]} — {leanest.median_peak_mib:.1f} MiB.</p>'+table(show[show['Số dòng']==largest][['Phương pháp','Trung vị (s)','Peak RAM (MiB)','Tăng tốc (lần)']]),
        f'<h1>Lưu trữ cũng ảnh hưởng hiệu năng</h1>'+image_tag('storage.png')+f'<p>Parquet giảm {saving:.1f}% dung lượng ở mức lớn nhất. Chi phí chuẩn bị được ghi riêng, chưa tính hòa vốn chuyển đổi.</p>',
        '<h1>Giới hạn & kết luận</h1><p>Chọn cột, kiểu dữ liệu, chunk và Parquet có đánh đổi khác nhau.</p><p>Bootstrap từ mẫu nhỏ có thể nén tốt; chưa thử dữ liệu thật vượt RAM, người dùng đồng thời hay hệ phân tán.</p><p class="lead">Kết luận dựa trên số đo và đúng kết quả; không có một cách luôn tốt nhất cho mọi bài toán.</p>',
        '<h1>Demo & tài liệu</h1><pre>python demo.py --method csv_chunk --rows 1000000\npython -m unittest discover -s tests -v\npython run_project.py --skip-generate</pre>'+sources]
    css = STYLE+'''main{max-width:none;padding:0;background:transparent}.slide{background:white;max-width:1200px;min-height:680px;margin:24px auto;padding:42px 64px;position:relative;box-shadow:0 4px 24px #0001}.slide h1{font-size:38px;margin-top:6px}.slide h2{margin-top:20px}.slide p,.slide li{font-size:21px}.slide img{max-height:430px;object-fit:contain}.slide .cover{border:0}.num{position:absolute;right:24px;bottom:14px;color:#708090}nav{position:sticky;top:0;background:#103954;color:white;padding:10px 24px;z-index:2;font-size:14px}@media print{nav{display:none}.slide{margin:0;box-shadow:none;break-after:page;min-height:0;height:170mm;padding:10mm}.slide p,.slide li{font-size:15pt}.slide img{max-height:110mm}.cover{break-after:auto}@page{size:A4 landscape;margin:10mm}}'''
    content=''.join(f'<section class="slide" id="s{i}">{s}<span class="num">{i}/{len(slides)}</span></section>' for i,s in enumerate(slides,1))
    (out/'thuyet_trinh.html').write_text('<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Thuyết trình đồ án</title><style>'+css+'</style><nav>Dùng ← / → để chuyển trang · Ctrl+P để lưu PDF ngang</nav><main>'+content+'</main><script>let i=1;document.addEventListener("keydown",e=>{if(e.key==="ArrowRight"||e.key==="ArrowLeft"){e.preventDefault();i=Math.max(1,Math.min('+str(len(slides))+',i+(e.key==="ArrowRight"?1:-1)));document.getElementById("s"+i).scrollIntoView({behavior:"smooth"})}})</script></html>', encoding='utf-8')


def create_notebook():
    def md(s): return dict(cell_type='markdown',metadata={},source=s.splitlines(keepends=True))
    def code(s): return dict(cell_type='code',metadata={},execution_count=None,outputs=[],source=s.splitlines(keepends=True))
    cells=[md('# Đồ án bất động sản & tối ưu hiệu năng\nBùi Kiếm Khoa — n23dcn029; Lương Võ Hân Hân — n23dccn017.\n\nNotebook đọc dữ liệu và số đo đã tạo. Chạy `python run_project.py` từ thư mục gốc nếu chưa có đầu ra. Dữ liệu thật và mô phỏng được tách riêng.'),
           code('from pathlib import Path\nimport json\nimport pandas as pd\nimport matplotlib.pyplot as plt\nROOT = Path.cwd()\nif not (ROOT / "run_project.py").exists():\n    ROOT = ROOT.parent\nassert (ROOT / "run_project.py").exists(), "Mở notebook trong thư mục dự án"\nbase = pd.read_csv(ROOT / "data/processed/real_estate_clean.csv")\nbase.head()'),
           md('## 1. Chất lượng dữ liệu thật\nKhông thêm giá trị thiếu giả vào mẫu gốc. Đọc audit do pipeline ghi.'),
           code('metadata = json.loads((ROOT / "data/processed/source_metadata.json").read_text(encoding="utf-8"))\nprint(metadata["audit"])\nbase.describe()'),
           md('## 2. Khám phá\nGiá theo 10.000 TWD/ping; không phải VND hoặc tổng giá căn nhà. Tương quan không phải nhân quả.'),
           code('base.plot.scatter(x="mrt_distance_m", y="price_10k_twd_per_ping", alpha=.6)\nplt.show()\nbase[["house_age", "mrt_distance_m", "price_10k_twd_per_ping"]].corr()'),
           md('## 3. Mức dữ liệu mô phỏng\nChỉ dùng cho thử tải, không phải giao dịch thật bổ sung.'),
           code('manifest = pd.DataFrame(json.loads((ROOT / "data/benchmark/manifest.json").read_text(encoding="utf-8")))\nmanifest'),
           md('## 4. Kết quả đo\nThời gian trung vị, peak RAM toàn tiến trình; xem cả min/max. Cache hệ điều hành không xóa.'),
           code('summary = pd.read_csv(ROOT / "results/summary.csv")\nassert summary.correct.all()\nsummary[["rows", "method", "median_s", "median_peak_mib", "speedup", "correct"]]'),
           code('summary.pivot(index="rows", columns="method", values="median_s").plot(marker="o", ylabel="Seconds")\nplt.show()'),
           md('## 5. Đọc các kết quả gốc và giới hạn\nKhông suy rộng benchmark mô phỏng thành hiệu năng của mọi dữ liệu lớn. Xem `report/bao_cao.html` để đọc đầy đủ phương pháp, nguồn và giới hạn.'),
           code('runs = json.loads((ROOT / "results/runs.json").read_text(encoding="utf-8"))\nprint("Số phép đo:", len(runs))\nprint("Tất cả khớp:", all(r["correct"] for r in runs))\nruns[0]')]
    notebook=dict(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.12'}},nbformat=4,nbformat_minor=5)
    for i,cell in enumerate(cells): cell['id']=f'cell-{i:02d}'
    (ROOT/'notebooks/01_do_an.ipynb').write_text(json.dumps(notebook,ensure_ascii=False,indent=2),encoding='utf-8')
