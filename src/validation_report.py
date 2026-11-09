"""Báo cáo kiểm chứng bộ nhớ, workload, hòa vốn và đóng góp xây dựng dữ liệu."""
import base64
import html
import json
import re
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from src.vietnam_data import ROOT,SOURCE
from src.deliverables import STYLE,table
from src.queries import LABELS,METHODS


def embedded(path):
    return '<img alt="Kết quả kiểm chứng" src="data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()+'">'


def build_validation_report():
    result=ROOT/'results/vietnam'; memory=pd.read_csv(result/'memory_limits/summary.csv')
    controls=json.loads((result/'memory_limits/controls.json').read_text(encoding='utf-8'))
    costs=pd.read_csv(result/'break_even/conversion_cost.csv')
    query_times=pd.read_csv(result/'break_even/query_times.csv')
    estimates=pd.read_csv(result/'break_even/break_even.csv')
    model=pd.read_csv(result/'break_even/modeled_totals.csv')
    profile=json.loads((ROOT/'data/vietnam/processed/profile.json').read_text(encoding='utf-8'))
    memory_config=json.loads((result/'memory_limits/config.json').read_text(encoding='utf-8'))
    rows=memory_config['rows']; case_repeats=int(memory.attempts.max()); query_repeats=int(query_times.repeats.max())
    manifest=json.loads((ROOT/'data/vietnam/benchmark/manifest.json').read_text(encoding='utf-8'))
    csv_mib=next(item['csv_bytes'] for item in manifest if item['rows']==rows)/1024**2
    workloads=[]
    for label in ['province_type','top100','multi_filter']:
        frame=pd.read_csv(result/f'workloads/{label}/summary.csv')
        if not frame.correct.all(): raise AssertionError('Workload mới khác baseline.')
        workloads.append(frame.assign(workload=label))
    workloads=pd.concat(workloads,ignore_index=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
    labels=[(q,b) for b in [256,512] for q in ['province','top100']]
    matrix=np.array([[int(memory.loc[(memory['query']==q)&(memory.limit_mib==b)&(memory.method==method),'success'].iloc[0]) for method in METHODS] for q,b in labels])
    figure,ax=plt.subplots(figsize=(11,4))
    image=ax.imshow(matrix,cmap='YlGnBu',vmin=0,vmax=int(memory.attempts.max()),aspect='auto')
    ax.set_xticks(range(len(METHODS)),[LABELS[m] for m in METHODS],rotation=15,ha='right')
    ax.set_yticks(range(len(labels)),[f'{q} · {b} MiB commit' for q,b in labels])
    ax.set_title(f'Số lần hoàn thành và khớp kết quả / {case_repeats} lần thử')
    for y in range(len(labels)):
        for x in range(len(METHODS)):
            ax.text(x,y,f'{matrix[y,x]}/{case_repeats}',ha='center',va='center',color='white' if matrix[y,x]>=case_repeats*.6 else '#172b42')
    figure.colorbar(image,ax=ax,label='Số lần thành công'); figure.tight_layout()
    memory_plot=result/'memory_limits/completion.png'; figure.savefig(memory_plot,dpi=160); plt.close(figure)
    figure,axes=plt.subplots(1,2,figsize=(11,4.5))
    for ax,query in zip(axes,['province','top100']):
        for target,color in [('parquet_columns','#07858c'),('duckdb_parquet','#e05d38')]:
            points=model[(model['query']==query)&(model.csv_baseline=='csv_typed')&(model.target==target)&(model.n<=20)]
            ax.plot(points.n,points.modeled_converted_s,marker='o',label='Chuyển + '+LABELS[target],color=color)
        ax.plot(points.n,points.modeled_csv_s,marker='o',label='CSV chọn cột + kiểu',color='#64748b')
        direct=model[(model['query']==query)&(model.csv_baseline=='duckdb_csv')&(model.target=='duckdb_parquet')&(model.n<=20)]
        if len(direct): ax.plot(direct.n,direct.modeled_csv_s,marker='s',linestyle='--',label='DuckDB đọc CSV trực tiếp',color='#7c3aed')
        ax.set(xlabel='Số lần truy vấn N',ylabel='Tổng thời gian ước tính (s)',title=query); ax.grid(alpha=.2); ax.set_ylim(bottom=0)
    handles,names=axes[0].get_legend_handles_labels(); figure.legend(handles,names,loc='lower center',ncol=2,fontsize=9)
    figure.tight_layout(rect=[0,.13,1,1]); break_plot=result/'break_even/modeled_cost.png'; figure.savefig(break_plot,dpi=160); plt.close(figure)
    show_memory=memory.copy(); show_memory['method']=show_memory.method.map(LABELS)
    memory_metrics=show_memory[['limit_mib','query','method','max_verified_peak_commit_mib','verified_commit_cases','max_success_peak_rss_mib']].rename(columns={
        'limit_mib':'Hạn mức MiB','query':'Tải','method':'Cách xử lý','max_verified_peak_commit_mib':'Đỉnh commit MiB',
        'verified_commit_cases':'Số snapshot','max_success_peak_rss_mib':'Đỉnh RSS ca đạt MiB'})
    show_memory=show_memory[['limit_mib','query','method','success','oom','timeout','other_errors','median_success_s']].rename(columns={
        'limit_mib':'Hạn mức MiB','query':'Tải','method':'Cách xử lý','success':'Đạt','oom':'OOM','timeout':'Timeout',
        'other_errors':'Lỗi khác','median_success_s':'Trung vị ca đạt (s)'})
    show_work=workloads[['workload','method','median_s','min_s','max_s','median_peak_mib','correct']].copy()
    show_work['method']=show_work.method.map(LABELS)
    show_estimates=estimates.copy()
    show_estimates['csv_baseline']=show_estimates.csv_baseline.map(LABELS); show_estimates['target']=show_estimates.target.map(LABELS)
    show_estimates['first_strictly_faster_n']=show_estimates.first_strictly_faster_n.map(lambda n:'Không có' if pd.isna(n) else str(int(n)))
    show_estimates=show_estimates.rename(columns={'query':'Tải','csv_baseline':'Đối chứng CSV','target':'Cách đọc Parquet',
        'conversion_s':'C (s)','csv_query_s':'CSV (s)','target_query_s':'Parquet (s)',
        'saved_s_per_query':'Tiết kiệm/lượt (s)','first_strictly_faster_n':'N đầu nhanh hơn'})
    cost_median=float(costs.conversion_s.median())
    direct_examples=[]
    for query in ['province','top100']:
        item=estimates[(estimates['query']==query)&(estimates.csv_baseline=='duckdb_csv')&(estimates.target=='duckdb_parquet')].iloc[0]
        n='không có điểm hòa vốn' if pd.isna(item.first_strictly_faster_n) else f'N = {int(item.first_strictly_faster_n)}'
        direct_examples.append(f'{query}: {item.csv_query_s:.3f} s/lượt trên CSV và {item.target_query_s:.3f} s/lượt trên Parquet, {n}')
    attempts=int(memory.attempts.sum()); successes=int(memory.success.sum()); oom=int(memory.oom.sum())
    lowest=int(memory.limit_mib.min())
    low=memory[memory.limit_mib==lowest]
    reliable=[LABELS[method] for method,group in low.groupby('method') if (group.success==group.attempts).all()]
    contribution=pd.DataFrame([
        ['Nguồn công khai','Chọn 4 shard, trích 9 cột từ schema 19 cột; ghim commit và giấy phép','1.400.300 hàng trích + metadata/checksum'],
        ['Chuẩn hóa','Đặt tên cột, ép kiểu số, bỏ khoảng trắng, giữ đơn vị VND/m² của nguồn','Schema phân tích và các quy tắc kiểm tra'],
        ['Làm sạch','Loại thiếu/sai miền trường bắt buộc; số phòng lỗi chuyển thành thiếu; giữ ngoại lệ có cờ','1.297.417 hàng sạch, 102.883 hàng bị loại kèm lý do'],
        ['Thuộc tính dẫn xuất','Giá đăng/m², tháng đăng, cờ giá trị lớn; source_shard/source_row để truy nguồn','Bảng sạch 14 cột, có dấu vết hàng gốc'],
        ['Bộ benchmark','Thứ tự hash xác định, seed 42, lấy mẫu không hoàn lại theo khối','100 nghìn / 500 nghìn / 1 triệu hàng lồng nhau'],
        ['Thực nghiệm','Cùng tải truy vấn, đối chiếu đúng kết quả, đo bộ nhớ/thời gian/chi phí chuyển đổi','Số đo thô, cấu hình, lịch sử và báo cáo']
    ],columns=['Khâu','Đóng góp của nhóm','Đầu ra kiểm tra được'])
    body=f'''<p class="eyebrow">KIỂM CHỨNG THỰC NGHIỆM · BẢN BỔ SUNG CUỐI</p>
    <h1>Giới hạn bộ nhớ, tải truy vấn và điểm hòa vốn</h1>
    <p class="lead">Bùi Kiếm Khoa — n23dcn029<br>Lương Võ Hân Hân — n23dccn017</p>
    <p><a href="bao_cao.html">Báo cáo chính</a> · <a href="bo_sung_du_lieu_viet_nam.html">Dữ liệu Việt Nam</a> ·
    <a href="nang_cap_he_thong.html">Các chức năng đã nâng cấp</a></p>
    <h2>1. Định nghĩa rõ “dữ liệu quá lớn”</h2>
    <p>{rows:,} hàng CSV khoảng {csv_mib:.1f} MiB vẫn vừa máy 16 GB. Thí nghiệm này không gọi đó là dữ liệu vượt RAM máy.
    Vấn đề được kiểm tra là: cùng dữ liệu nhưng ngân sách cấp phát của tiến trình bị giới hạn, phương pháp nào
    còn hoàn thành đúng và phương pháp nào hết bộ nhớ hoặc quá thời gian?</p>
    <p>Áp dụng Windows Job Object với ProcessMemoryLimit = 256 hoặc 512 MiB, trước khi import Pandas/PyArrow/DuckDB.
    Đây là giới hạn <strong>committed virtual memory của tiến trình</strong>, không phải giới hạn RSS,
    working set hay việc máy chỉ có 256/512 MiB RAM vật lý. Đơn vị MiB = 2²⁰ byte.
    Cùng giới hạn OS cho cả sáu phương pháp, gồm Python, thư viện và dữ liệu. Tiến trình điều phối nằm ngoài giới hạn.</p>
    <p>Đo riêng peak working set và peak commit. Bảng chỉ dùng high-water RSS do tiến trình con SUCCESS trả về;
    peak commit lấy trực tiếp từ Job Object ở các ca trả được snapshot, kèm số ca verified_commit_cases.
    Ca crash không có snapshot được để thiếu, không lấy mẫu bộ nhớ nhỏ trước crash làm đỉnh thực tế.
    Các mẫu từ tiến trình cha trong dữ liệu thô chỉ là cận dưới quan sát được, có thể bỏ lỡ đỉnh.
    Bộ nhớ xin cấp phát bị từ chối có thể khiến OOM dù đỉnh đã dùng còn dưới hạn mức.
    DuckDB dùng ngân sách nội bộ bằng nửa giá trị hạn mức, một luồng, để chừa chỗ cho runtime; giới hạn OS bên ngoài vẫn áp dụng.
    Không thay đổi cấu hình RAM toàn máy. Nền tảng thí nghiệm: Windows; chưa triển khai cơ chế tương đương trên Linux.</p>
    <h2>2. Kiểm tra đối chứng cơ chế giới hạn</h2><p>Với mỗi hạn mức, cấp phát 32 MiB phải thành công;
    yêu cầu cấp phát lớn hơn hạn mức 64 MiB phải bị từ chối. Ngoài ra đọc lại thông tin Job Object để xác nhận cờ và số byte.
    Cả {len(controls)} đối chứng đều đạt trước khi chạy dữ liệu thật.</p>
    {table(pd.DataFrame([dict(limit_mib=c['limit_mib'],allocation_mib=c['allocation_mib'],expected=c['expected'],actual=c['status'],passed=c['passed']) for c in controls]))}
    <h2>3. Kết quả dưới giới hạn commit</h2>{embedded(memory_plot)}
    <p>{attempts} lần thử: {successes} hoàn thành và khớp kết quả; {oom} lần OOM.
    Các cột timeout và other_errors ghi riêng; không tự quy mọi lỗi thành hết bộ nhớ.
    Thời gian trung vị chỉ tính các ca SUCCESS; ô NaN là không có ca thành công, không có nghĩa là 0 giây.</p>
    {table(show_memory)}
    <p><strong>Kết quả đáng chú ý:</strong> ở {lowest} MiB commit, các phương pháp hoàn thành đủ mọi lần
    trên cả hai tải là {', '.join(reliable)}. Định dạng Parquet không tự bảo đảm đủ bộ nhớ:
    đọc các cột vào DataFrame rồi sắp xếp vẫn có thể cần nhiều RAM hơn quét theo khối hoặc top-k trong engine SQL.</p>
    <h3>Bộ nhớ có số đo xác nhận</h3>{table(memory_metrics)}
    <p>Hai tải là nhóm theo tỉnh và top 100 giá đăng. Các ca thành công đối chiếu với baseline không giới hạn của cùng mẫu/query.
    Thứ tự phương pháp, truy vấn và hạn mức được xáo bằng seed 42; mỗi cấu hình {case_repeats} lần.
    Thời gian query gồm đọc và xử lý, loại thời gian import; import vẫn chịu hạn mức.
    Timeout 60 giây tính từ khởi động tiến trình. Không xóa cache OS, không tính khoảng tin cậy.</p>
    <p>Đọc runs.json để xem mã thoát và lỗi từng ca. Lỗi native của thư viện khi cấp phát bị hạn chế
    được giữ ở nhóm lỗi khác; không suy từ mã thoát đơn thuần thành MemoryError hay tuyên bố đã xác định nguyên nhân nội bộ.</p>
    <h2>4. Những tải truy vấn mới</h2><ul>
    <li><strong>province_type:</strong> lọc diện tích 50–150 m², giá 1 VND–10 tỷ; nhóm đồng thời tỉnh và loại bất động sản.</li>
    <li><strong>multi_filter:</strong> Hà Nội, loại Nhà, diện tích 50–100 m², giá 1 VND–5 tỷ; nhóm theo tỉnh.</li>
    <li><strong>top100:</strong> lấy 100 bản ghi giá đăng cao nhất trong toàn bộ mẫu, không áp trần 10 tỷ hoặc diện tích 150 m².
    Phá hòa bằng source_shard/source_row tăng dần. Đây là bản ghi tin đăng, không khẳng định 100 căn nhà duy nhất.</li></ul>
    <p>Top 100 không tự bỏ các giá trị cực lớn đã gắn cờ: thứ hạng chỉ là phép tính trên dữ liệu nguồn,
    không chứng nhận giá hợp lý. CSV top100 dùng float_precision='round_trip' để giữ độ chính xác khi xếp hạng;
    cả bốn cách đọc CSV dùng cùng quy tắc này. Chunk chỉ giữ tối đa 100 ứng viên sau mỗi khối rồi gộp tiếp theo cùng thứ tự toàn phần.</p>
    {table(show_work)}
    <p>{int(workloads.repeats.sum())} lượt đo mới không giới hạn, cả sáu phương pháp và ba tải đều khớp baseline.
    Không lấy thời gian của truy vấn khác để suy ra mức tăng tốc của cùng một tác vụ.</p>
    <h2>5. Chi phí CSV → Parquet được đo trực tiếp</h2>
    <p>Đọc CSV, parse theo schema phân tích có sẵn, nén Snappy, ghi Parquet và đóng writer.
    Đọc theo block CSV 8 MiB, row group tối đa 50.000 hàng. Không gồm khởi động Python/import thư viện hoặc kiểm định kết quả.
    Không ép fsync và không bảo đảm cold-cache; đây là thời gian ghi logic của phần mềm.</p>{table(costs[['repetition','rows','conversion_s','correct']])}
    <p>Chi phí C dùng trung vị {len(costs)} lần chuyển. Mỗi lần kiểm tra số hàng và tổng hợp hash trên đủ 14 cột sau ép về schema chuẩn;
    thêm đối chiếu đầu ra các truy vấn. Các phép kiểm tra này nằm ngoài thời gian C.
    File Parquet chuyển đổi thực sự được dùng cho phần truy vấn lặp phía dưới, không dùng số đo trên file Parquet cũ để ghép vào.</p>
    <h2>6. Truy vấn lặp và mô hình hòa vốn</h2>
    <p>Trong cùng tiến trình, chạy một warmup bỏ đi cho mỗi phương pháp/query rồi đo {query_repeats} lần, xáo thứ tự trong từng vòng.
    Mỗi lần đều đọc lại tệp; không giữ DataFrame hay cache kết quả truy vấn. DuckDB tạo kết nối mỗi lần.
    So với CSV chọn cột, CSV chọn cột + kiểu và DuckDB đọc CSV trực tiếp theo cùng schema 14 cột.
    Đối chứng DuckDB + CSV giúp phân biệt lợi ích của engine SQL với lợi ích của định dạng Parquet;
    đọc CSV trực tiếp không phải trả chi phí chuyển đổi C.</p>{table(query_times)}
    <pre>T_CSV(N) = N × t_CSV
T_chuyển(N) = C + N × t_mới
N đầu tiên nhanh hơn = floor(C / (t_CSV − t_mới)) + 1, nếu t_CSV &gt; t_mới.</pre>
    <p>Nếu chênh lệch không dương, không có điểm hòa vốn theo mô hình này.
    Đây là ước tính từ trung vị đo được, không phải đã chạy thực tế mọi N ở đồ thị.
    Nếu cần tính cả kiểm định/triển khai hoặc cập nhật lại dữ liệu, phải cộng chi phí đó vào C.</p>
    <p>Mô hình dùng phiên truy vấn lặp đã warmup, loại khởi động Python/import. Nếu thực tế mỗi truy vấn mở
    một tiến trình mới, cần đo và cộng chi phí khởi động/import tương ứng, không áp dụng trực tiếp ngưỡng N này.</p>
    {table(show_estimates)}{embedded(break_plot)}
    <p><strong>Đọc kết quả hiện tại:</strong> C trung vị = {cost_median:.3f} s. Khi giữ cùng engine DuckDB,
    {'; '.join(direct_examples)}. Đây là số đo trên mẫu và môi trường này, không phải ngưỡng cố định cho mọi hệ thống.
    Cặp nào có chênh lệch không dương được ghi “Không có”; chênh lệch nhỏ chưa được kiểm định ý nghĩa thống kê.</p>
    <p>Dùng CSV có thể hợp lý cho ít truy vấn hoặc khi cần trao đổi dữ liệu văn bản.
    Chuyển sang Parquet/DuckDB đáng xem xét khi có đủ số truy vấn để bù C, hoặc khi CSV vượt ngân sách bộ nhớ.
    Nếu CSV không hoàn thành dưới hạn mức, so sánh thời gian đơn thuần không thay thế được điều kiện khả thi.
    Điểm hòa vốn thay đổi theo dữ liệu, độ chọn lọc, máy, cache, cách bố trí row group và phiên bản thư viện.</p>
    <h2>7. Nhóm đã xây dựng bộ dữ liệu như thế nào?</h2>
    <p>Nhóm <strong>xây dựng bộ dữ liệu phân tích từ nguồn công khai đã tồn tại</strong> của
    <a href="{SOURCE}">TiniX AI</a>, dùng theo CC BY-NC 4.0 cho học tập phi thương mại.
    Nhóm không trực tiếp thu thập/xác minh toàn bộ tin đăng. Toàn nguồn công bố hơn 3,5 triệu hàng;
    phần đã trích là {profile['raw_rows']:,} hàng, không nhận đã tải toàn nguồn.</p>{table(contribution)}
    <p>Không sinh hàng mới cho thí nghiệm Việt Nam. Các mẫu có thể chứa tin lặp từ nguồn; giữ nguyên vì không có ID để xác nhận trùng.
    Dữ liệu có thể lẫn bán/thuê; kết quả giá phục vụ kiểm tra phép tính, không phải kết luận giá bán thị trường.
    Phần mô phỏng UCI ban đầu vẫn được gắn nhãn riêng và không dùng thay dữ liệu Việt Nam trong các thí nghiệm ở đây.</p>
    <h2>8. Tệp kết quả và chạy lại</h2><pre>python run_validation.py
python run_validation.py --skip-workloads
python run_validation.py --skip-workloads --skip-memory
python demo.py --dataset vietnam --query province_type --method csv_chunk
python demo.py --dataset vietnam --query top100 --method duckdb_parquet</pre>
    <p>Dùng .venv theo README. Các cờ skip yêu cầu phần bị bỏ qua đã có kết quả tương ứng; không tạo số đo thay thế.
    Kết quả riêng trong results/vietnam/workloads, memory_limits và break_even; mỗi phần có lịch sử, cấu hình và trạng thái.
    OOM và timeout được lưu như kết quả của từng ca thử.</p>
    <h2>9. Tài liệu phương pháp</h2><ul><li><a href="https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information">Microsoft: ProcessMemoryLimit giới hạn committed virtual memory</a>.</li>
    <li><a href="https://duckdb.org/2024/07/09/memory-management">DuckDB: quản lý bộ nhớ và tràn đĩa</a>.</li>
    <li><a href="{SOURCE}">TiniX AI: nguồn, schema và giấy phép dữ liệu</a>.</li></ul>'''
    (ROOT/'report/kiem_chung_du_lieu_lon.html').write_text('<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Kiểm chứng dữ liệu lớn và hòa vốn</title><style>'+STYLE+'</style><main>'+body+'</main></html>',encoding='utf-8')
    attach_validation_files()


def attach_validation_files():
    for name in ['bao_cao.html','bo_sung_du_lieu_viet_nam.html','nang_cap_he_thong.html']:
        path=ROOT/'report'/name; text=path.read_text(encoding='utf-8')
        text=re.sub(r'<aside id="validation-link".*?</aside>','',text,flags=re.S)
        banner='<aside id="validation-link" class="note"><strong>Đã bổ sung kiểm chứng:</strong> giới hạn commit Windows 256/512 MiB, workload mới và điểm hòa vốn. <a href="kiem_chung_du_lieu_lon.html">Mở báo cáo kiểm chứng và đóng góp xây dựng dữ liệu</a>.</aside>'
        text=text.replace('Chưa đo chuyển đổi CSV sang Parquet hoặc hòa vốn.',
                          'Chi phí chuyển CSV → Parquet và điểm hòa vốn được đo trong <a href="kiem_chung_du_lieu_lon.html">báo cáo kiểm chứng riêng</a>; không suy từ thời gian ghi ở bảng này.')
        text=text.replace('Đây không phải phép đo chuyển CSV sang Parquet và không đủ để kết luận thời điểm hòa vốn của việc chuyển đổi.',
                          'Các số ghi tệp ở bảng này không dùng làm chi phí chuyển CSV. Xem <a href="kiem_chung_du_lieu_lon.html">phép đo chuyển đổi và hòa vốn riêng</a>.')
        path.write_text(text.replace('<main>','<main>'+banner,1),encoding='utf-8')
    path=ROOT/'report/thuyet_trinh.html'; text=path.read_text(encoding='utf-8')
    text=re.sub(r'<!--validation-slides-start-->.*?<!--validation-slides-end-->','',text,flags=re.S)
    n=text.count('class="slide"'); total=n+4
    pages=[
        '<h1>“Lớn” so với ngân sách bộ nhớ</h1><p>Máy 16 GB; không gọi 1 triệu hàng là vượt RAM vật lý.</p><p>Job Object giới hạn commit toàn tiến trình 256/512 MiB, trước import thư viện. Đối chứng cấp phát xác nhận giới hạn.</p>'+embedded(ROOT/'results/vietnam/memory_limits/completion.png'),
        '<h1>Thêm ba tải truy vấn</h1><ul><li>Nhóm đồng thời tỉnh + loại bất động sản.</li><li>Lọc tỉnh, loại, diện tích và giá.</li><li>Top 100 bản ghi giá đăng cao nhất; phá hòa bằng ID hàng nguồn.</li></ul><p>Mọi phương pháp đối chiếu cùng kết quả. Top 100 là thứ hạng trong dữ liệu nguồn, không xác nhận giá thị trường hoặc căn nhà duy nhất.</p>',
        '<h1>Khi nào chuyển CSV sang Parquet?</h1>'+embedded(ROOT/'results/vietnam/break_even/modeled_cost.png')+'<p>C + N × t_mới so với N × t_CSV. Điểm hòa vốn ước tính từ chi phí chuyển đổi thật và truy vấn lặp; không dùng thời gian ghi file đơn lẻ.</p>',
        '<h1>Đóng góp xây dựng bộ dữ liệu</h1><p>Nguồn công khai → chọn cột, ghim phiên bản → làm sạch/chuẩn hóa → thuộc tính mới và truy nguồn → mẫu benchmark → kiểm chứng.</p><p>1.400.300 hàng trích → 1.297.417 hàng sạch + 102.883 hàng bị loại có lý do.</p><p>Không nhận tự thu thập toàn bộ tin đăng. Không sinh thêm hàng cho benchmark Việt Nam.</p><p><a href="kiem_chung_du_lieu_lon.html">Báo cáo kiểm chứng đầy đủ</a></p>']
    extra='<!--validation-slides-start-->'+''.join(f'<section class="slide" id="s{n+i}">{body}<span class="num">{n+i}/{total}</span></section>' for i,body in enumerate(pages,1))+'<!--validation-slides-end-->'
    text=text.replace('</main>',extra+'</main>',1)
    text=re.sub(r'(<span class="num">\d+)/\d+(</span>)',lambda m:m[1]+f'/{total}'+m[2],text)
    text=re.sub(r'Math\.min\(\d+,i\+',f'Math.min({total},i+',text)
    path.write_text(text,encoding='utf-8')
    notebook_path=ROOT/'notebooks/01_do_an.ipynb'
    notebook=json.loads(notebook_path.read_text(encoding='utf-8'))
    notebook['cells']=[c for c in notebook['cells'] if not c['id'].startswith('validation-')]
    notebook['cells'].extend([
        dict(cell_type='markdown',id='validation-intro',metadata={},source=['## 8. Kiểm chứng giới hạn bộ nhớ và hòa vốn\n',
             'Giới hạn commit Windows khác RAM vật lý. Giữ riêng OOM/lỗi native; chỉ tính thời gian ca thành công. Đọc `report/kiem_chung_du_lieu_lon.html` để xem điều kiện đo và đóng góp dữ liệu.']),
        dict(cell_type='code',id='validation-memory',metadata={},execution_count=None,outputs=[],source=[
             'memory = pd.read_csv(ROOT / "results/vietnam/memory_limits/summary.csv")\n','memory']),
        dict(cell_type='code',id='validation-cost',metadata={},execution_count=None,outputs=[],source=[
             'break_even = pd.read_csv(ROOT / "results/vietnam/break_even/break_even.csv")\n',
             '# N là ước tính từ trung vị; có cả đối chứng DuckDB đọc CSV trực tiếp.\n','break_even'])])
    notebook_path.write_text(json.dumps(notebook,ensure_ascii=False,indent=2),encoding='utf-8')
