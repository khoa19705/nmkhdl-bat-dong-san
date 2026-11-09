# Đồ án giữa kì — Nhập môn Khoa học dữ liệu

**Xây dựng bộ dữ liệu bất động sản và đánh giá các phương pháp tối ưu hiệu năng xử lý dữ liệu bằng Python**

- Bùi Kiếm Khoa — **n23dcn029**
- Lương Võ Hân Hân — **n23dccn017**

Mã sinh viên được ghi theo thông tin nhóm cung cấp; kiểm tra lại tiền tố của Khoa trước khi nộp.

## Mở kết quả có sẵn

**Bản nâng cấp mới:** mở `report/nang_cap_he_thong.html` để xem chuẩn bị theo khối, tra cứu có tham số, hàng bị loại và thí nghiệm nhiều chunk size/truy vấn.

**Kiểm chứng bổ sung:** mở `report/kiem_chung_du_lieu_lon.html` để xem giới hạn commit Windows 256/512 MiB, nhóm theo tỉnh + loại, top 100 giá đăng, lọc nhiều điều kiện và điểm hòa vốn chuyển CSV → Parquet. Có bảng giải thích đóng góp xây dựng dữ liệu của nhóm.

Lần chạy đã lưu: 54 lượt workload mới đều đúng; 72 ca giới hạn có 57 thành công, 10 OOM và 5 lỗi native được giữ riêng. CSV từng khối và DuckDB + Parquet hoàn thành cả hai tải ở 256 MiB commit. Phần hòa vốn đo 3 lần chuyển đổi và 50 lượt truy vấn, có đối chứng DuckDB đọc CSV trực tiếp; kết luận chỉ áp dụng điều kiện đã đo.

1. Mở `report/bao_cao.html` bằng Chrome hoặc Edge để đọc báo cáo. Có thể dùng Ctrl+P → Save as PDF, khổ A4, tắt header/footer của trình duyệt.
2. Mở `report/thuyet_trinh.html` để trình chiếu; dùng phím trái/phải. Khi in PDF chọn khổ ngang.
3. Đọc `report/huong_dan_bao_ve.md` để hiểu code, demo và các câu hỏi thường gặp.
4. Kết quả số: `results/summary.csv`; từng lần đo: `results/measurements.csv`, `results/runs.json`; cấu hình máy thực nghiệm: `results/environment.json`.

Hai HTML nhúng biểu đồ trực tiếp, mở ngoại tuyến được. Các báo cáo có số đo đã chạy; không phải số liệu minh họa. Tài liệu HTML là định dạng báo cáo/thuyết trình của bản này, không phải DOCX/PPTX.

Khi tải mã từ GitHub, có thể mở báo cáo và slide ngay. Hai thư mục mẫu benchmark (`data/benchmark/` và `data/vietnam/benchmark/`) được tạo lại bằng `run_project.py` và `run_vietnam.py` sau khi cài thư viện. Hãy chạy bước này trước khi dùng `demo.py`, `run_validation.py` hoặc các cờ bỏ qua bước chuẩn bị. Gói ZIP nộp bài trong `dist/` để riêng ở máy.

## Bổ sung dữ liệu Việt Nam

Bản mở rộng có nguồn tin đăng Việt Nam do [TiniX AI công bố](https://huggingface.co/datasets/tinixai/vietnam-real-estates), giấy phép [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/), sử dụng học tập phi thương mại và ghi công TiniX AI.

- Toàn nguồn công bố 3.500.744 hàng; đồ án trích **9 cột của 4 shard đầu**, tổng **1.400.300 hàng nguồn**, không nhận đã tải toàn bộ nguồn.
- Tải riêng các cột cấu trúc bằng HTTP Range, không lấy tiêu đề, mô tả hoặc địa chỉ chi tiết. Giữ commit nguồn và SHA-256 của từng bản trích.
- Dữ liệu sạch không được sinh bù; số hàng sau lọc và lý do loại nằm trong `data/vietnam/processed/profile.json`.
- Tin đăng khác giao dịch đã chốt. Nguồn có cả bán/thuê nhưng không có cột phân biệt trong schema này; giá trung bình của benchmark không phải thống kê giá bán thị trường.
- Chữ ký 9 cột có thể lặp, không có ID tin/bất động sản để khẳng định duy nhất; các hàng được giữ lại và báo số chữ ký lặp. Địa phương giữ nhãn của nguồn.
- Bộ Việt Nam và UCI được xử lý/đo riêng, không nối giá VND với giá TWD và không so trực tiếp thời gian hai truy vấn khác nhau.

Mở **`report/bo_sung_du_lieu_viet_nam.html`** để xem báo cáo dữ liệu và benchmark bổ sung. Báo cáo chính có liên kết sang phần này; thuyết trình có thêm hai trang. Notebook cũng có phần đọc kết quả Việt Nam.

Đo lại bằng dữ liệu Việt Nam đã kèm (dùng cùng môi trường Python):

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe run_vietnam.py
```

Nếu chỉ muốn đo lại, không chuẩn bị lại các tập mẫu:

```powershell
.\.venv\Scripts\python.exe run_vietnam.py --skip-prepare
```

Demo nhanh trên dữ liệu Việt Nam:

```powershell
.\.venv\Scripts\python.exe demo.py --dataset vietnam --method duckdb_parquet --rows 1000000
```

Nếu cần tải lại từ đầu (cần mạng; giữ nguyên commit ghim):

```powershell
.\.venv\Scripts\python.exe run_vietnam.py --download --shards 4
```

Các mức mặc định là 100 nghìn, 500 nghìn và 1 triệu hàng lấy mẫu **không hoàn lại** từ phần sạch đã tải, seed 42. Sáu phương pháp, mỗi phương pháp/mức lặp ba lần. Kết quả riêng trong `results/vietnam/`; dữ liệu riêng trong `data/vietnam/`.

### Chuẩn bị theo khối và lấy mẫu

Bản mới đọc tối đa 50.000 hàng mỗi Arrow batch để làm sạch, ghi Parquet và CSV hàng bị loại. Không nạp toàn bộ bảng sạch hoặc toàn bộ tập mẫu vào Pandas. DuckDB dùng ngân sách bộ quản lý bộ nhớ 256 MB, một luồng và vùng tràn đĩa cho các phép nhóm/sắp xếp. Đây **không phải giới hạn cứng RAM của toàn tiến trình**, và chưa là bằng chứng xử lý dữ liệu vượt RAM.

Các mẫu được tạo theo thứ tự hash của `(source_shard, source_row, seed)`, có khóa phụ để phá hòa. Các mức nhỏ là tiền tố của mức lớn; không hoàn lại và không tạo hàng mới. Đây là thứ tự giả ngẫu nhiên xác định trên phần nguồn đã tải, không phải mẫu phân tầng hoặc cam kết đại diện toàn thị trường. Phiên bản DuckDB được ghim trong requirements vì hash có thể đổi giữa các phiên bản. Thuật toán khác bản NumPy ban đầu nên các phép đo của bản mới đã được chạy lại.

Tùy chỉnh: `--prepare-batch 50000 --prepare-memory-mb 256 --chunksize 50000`. Chuẩn bị và truy vấn có tham số batch riêng. Số đo bước chuẩn bị nằm trong `results/vietnam/preparation_measurement.json`, gồm thời gian và high-water working set tiến trình trên Windows đến hết chuẩn bị; chưa có đối chứng chuẩn bị cũ để công bố tỷ lệ cải thiện.

### Tra cứu, xem trước và xuất CSV

```powershell
.\.venv\Scripts\python.exe search_vietnam.py --province 'Hà Nội' --property-type 'Nhà' --area-min 50 --area-max 100 --price-max 5000000000 --limit 10 --export results/ha_noi.csv
```

Tỉnh và loại nhà phải theo nhãn trong nguồn. Bỏ hai điều kiện này để lấy mọi tỉnh/loại. Giá nhập bằng VND, diện tích m². Cận được tính bao gồm hai đầu. `--limit` chỉ giới hạn xem trước (1–1.000 hàng); `--export` xuất **toàn bộ** hàng khớp theo luồng. Xem trước sắp theo giá và ID hàng nguồn; tệp xuất không bảo đảm cùng thứ tự. Không có nhãn bán/thuê để lọc riêng hoặc xác nhận giá giao dịch.

Demo thống kê cùng điều kiện bằng một phương pháp được chọn:

```powershell
.\.venv\Scripts\python.exe demo.py --dataset vietnam --method csv_chunk --query month --province 'Hà Nội' --area-max 100 --price-max 5000000000
```

### Chất lượng trước–sau và hàng bị loại

- `data/vietnam/processed/rejected_rows.csv`: các giá trị nguồn được giữ lại kèm shard, số thứ tự hàng **đếm từ 0** và lý do loại từng trường.
- `data/vietnam/processed/quality_before_after.csv`: số/tỷ lệ thiếu trước và sau lọc theo cột. Hai tỷ lệ có mẫu số khác nhau do hàng bị loại.
- `profile.json`: tổng kiểm tra, cờ giá trị lớn, thiếu số phòng/tầng và chữ ký trùng. Không tự xóa tin cùng chữ ký hoặc tự điền trung bình số phòng.

### Bộ thí nghiệm mở rộng

```powershell
.\.venv\Scripts\python.exe run_vietnam.py --extended
.\.venv\Scripts\python.exe run_vietnam.py --skip-prepare --extended
.\.venv\Scripts\python.exe run_vietnam.py --only-extended
```

Lệnh đầu chuẩn bị lại rồi đo. Lệnh thứ hai dùng mẫu có sẵn. Lệnh thứ ba chỉ chạy phần mở rộng ở mức lớn nhất trong `--sizes`.

- `province`: truy vấn gốc, sáu phương pháp × ba mức × ba lần mặc định.
- `month`: nhóm theo tháng, cùng bộ lọc; sáu phương pháp tại mức lớn nhất.
- `top_types`: top 3 loại có nhiều hàng nhất sau lọc; gộp đầy đủ rồi sắp theo count giảm/tên tăng để phá hòa. Sáu phương pháp tại mức lớn nhất.
- Chunk 10.000 / 50.000 / 100.000 hàng: mỗi cấu hình so với CSV toàn bộ, ba lần lặp. Không kết luận chỉ từ chênh lệch nhỏ.

Tất cả truy vấn dùng count/sum/mean để đối chiếu; không coi kết quả trung bình là giá bán thị trường. Số đo mở rộng nằm trong `results/vietnam/experiments/expanded_summary.csv` và các thư mục con.

### Lịch sử và kiểm tra đầu vào

Mỗi lần đo có thư mục `history/<UTC-run-id>/`, gồm cấu hình, checksum tập mẫu, số đo thô và trạng thái. Các file `summary.csv`/`runs.json` trực tiếp trong thư mục kết quả là bản thành công mới nhất; `latest_run.json` trỏ về lịch sử. Lượt lỗi được ghi FAILED và giữ kết quả đã công bố trước đó. Các kết quả có sẵn trước nâng cấp được lưu một lần trong thư mục `legacy-*`.

Lịch sử lưu số đo/cấu hình/hash, không tự nhân bản toàn bộ dữ liệu của mỗi phiên. Muốn tái lập một phiên cũ sau khi đã thay bộ dữ liệu cần giữ hoặc khôi phục đúng đầu vào có checksum khớp. Bộ nộp kèm dữ liệu của phiên mới nhất; legacy là bản lưu kết quả trước nâng cấp.

Khi có checksum trong manifest, benchmark từ chối file bị thay đổi; kiểm tra số hàng Parquet khớp mức dữ liệu. Cấu hình và hash được chụp trước đo, không tính thời gian hash vào thời gian truy vấn. Lưu ý việc kiểm tra/chuẩn bị trước đo cũng có thể làm ấm cache; đây vẫn không phải cold-cache benchmark.

### Kiểm chứng dữ liệu lớn, thêm workload và hòa vốn

```powershell
.\.venv\Scripts\python.exe run_validation.py
```

Không cần tải hoặc sinh thêm dữ liệu. Mặc định dùng mẫu 1 triệu hàng hiện có, 3 lần lặp cho mỗi ca workload/giới hạn; truy vấn lặp để tính hòa vốn có 1 warmup bỏ đi và 5 lần đo.

Phần kiểm chứng gồm:

- `province_type`: lọc theo phạm vi mặc định rồi nhóm đồng thời tỉnh và loại bất động sản.
- `multi_filter`: Hà Nội, loại Nhà, 50–100 m², giá đăng đến 5 tỷ VND; benchmark riêng độ chọn lọc này.
- `top100`: top 100 **bản ghi tin đăng** giá cao nhất của toàn mẫu; không mặc định giới hạn giá 10 tỷ/diện tích 150 m². Phá hòa theo `source_shard, source_row`. Có thể chứa giá bất hợp lý được nguồn công bố; không xác nhận giá thị trường hoặc căn nhà duy nhất.
- Giới hạn OS: Windows Job Object, `ProcessMemoryLimit` 256 hoặc 512 **MiB committed virtual memory** cho tiến trình con, trước import thư viện. Đây **không phải** giới hạn RAM vật lý/RSS. Runtime và thư viện cũng chịu hạn mức; tiến trình điều phối nằm ngoài. Chỉ Windows hỗ trợ phần này.
- Kiểm tra đối chứng: 32 MiB cấp phát thành công; một yêu cầu lớn hơn hạn mức 64 MiB bị từ chối. Đọc lại cờ/giới hạn Job Object. Đối chứng không đạt thì dừng, không công bố giới hạn đã được áp dụng.
- Mỗi phương pháp có cùng hạn mức OS. DuckDB đặt buffer budget bằng nửa giá trị hạn mức để chừa runtime; không coi buffer budget là giới hạn cứng toàn tiến trình.
- Ghi riêng SUCCESS, OOM, TIMEOUT, NATIVE_ERROR hoặc lỗi khác. Không quy mọi lỗi về OOM. Timeout 60 giây gồm cả khởi động/import; thời gian query thành công loại import. CSV top100 dùng round-trip parsing để giữ thứ hạng giá/tie chính xác.
- Đo trực tiếp đọc CSV → parse theo schema phân tích có sẵn → nén/ghi Parquet → đóng writer. Không dùng thời gian ghi Parquet trong bước tạo mẫu làm chi phí chuyển đổi. Đối chiếu số hàng và tổng hợp hash đủ 14 cột theo schema chuẩn, rồi kiểm tra kết quả truy vấn.
- Đo truy vấn lặp trên **file Parquet vừa chuyển đổi**, so với CSV chọn cột, CSV chọn cột + kiểu và DuckDB đọc CSV trực tiếp, cùng tiến trình với warmup; không giữ DataFrame/kết quả. Thời gian tạo kết nối DuckDB được tính.
- Mô hình `N*t_csv` và `C+N*t_mới` dùng trung vị đo thật. Số nguyên đầu tiên nhanh hơn là `floor(C/(t_csv-t_mới))+1` khi chênh lệch dương. Các tổng thời gian theo N là **ước tính**, không nhận đã đo thực tế mọi N.

Không xóa OS cache, không ép fsync, chưa đánh giá nhiều người dùng/máy khác. Chi phí kiểm định nằm ngoài C; cần cộng vào nếu quy trình thực tế yêu cầu. Thí nghiệm giới hạn không tương đương dữ liệu vượt 16 GB RAM của máy.

Kết quả ở `results/vietnam/workloads/`, `memory_limits/`, `break_even/`, mỗi phần có lịch sử riêng. `break_even` giữ một file Parquet chuyển đổi trong thư mục lịch sử để kiểm tra lại.

Chạy lại từng phần (các phần skip phải đã có kết quả phù hợp):

```powershell
.\.venv\Scripts\python.exe run_validation.py --skip-workloads
.\.venv\Scripts\python.exe run_validation.py --skip-workloads --skip-memory
.\.venv\Scripts\python.exe demo.py --dataset vietnam --query province_type --method csv_chunk
.\.venv\Scripts\python.exe demo.py --dataset vietnam --query top100 --method duckdb_parquet
```

Nhóm xây dựng **bộ dữ liệu phân tích từ nguồn công khai đã tồn tại**, không nhận trực tiếp thu thập/xác minh toàn bộ tin đăng. Đóng góp gồm chọn cột, ghim nguồn/giấy phép, kiểm tra/làm sạch/chuẩn hóa, tạo thuộc tính, truy nguồn, tạo mẫu và thiết kế/đo thực nghiệm. Xem bảng đầu vào–biến đổi–đầu ra trong báo cáo kiểm chứng.

Truy vấn Việt Nam lọc diện tích 50–150 m² và giá đăng 1 VND–10 tỷ VND, nhóm theo tỉnh, tính count/sum/mean. Đây là tải truy vấn để đối chiếu kết quả và hiệu năng, không phải tiêu chí nhận diện tin thật/giả.

## Dữ liệu UCI ban đầu và giới hạn

Nguồn: [Yeh, I. (2018), Real Estate Valuation, UCI](https://archive.ics.uci.edu/dataset/477/real+estate+valuation+data+set), DOI [10.24432/C5J30W](https://doi.org/10.24432/C5J30W), giấy phép [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

- **414 giao dịch thật** tại Đài Loan: dùng làm sạch và phân tích khám phá.
- **100.000 / 500.000 / 1.000.000 hàng mô phỏng**: bootstrap nguyên hàng và thêm nhiễu nhỏ vào tuổi nhà, khoảng cách MRT và giá; dùng đo tải, có `is_synthetic=True`.
- Giá gốc là **10.000 TWD/ping**, không phải VND, không phải tổng giá căn nhà. Không có diện tích căn nhà trong nguồn.
- Đổi sang TWD/m² theo quy ước xấp xỉ **1 ping = 3,3 m²** của nguồn. Giữ ngày dạng số thập phân gốc.
- Đã đổi tên cột, kiểm tra miền, thêm cột nhóm tuổi/giá quy đổi/cờ IQR trong dữ liệu sạch; dữ liệu mô phỏng có ID riêng. Bản nguồn được giữ nguyên trong `data/raw/uci_477_original.xlsx`.
- Dữ liệu mô phỏng không bổ sung bằng chứng về thị trường và không đại diện bất động sản Việt Nam.
- Mức thử tải hiện tại chưa chứng minh xử lý dữ liệu thật vượt dung lượng RAM. Đây là nghiên cứu hiệu năng xử lý trên một máy, không phải hệ phân tán.

## Cài và chạy lại

Khuyến nghị Python **3.12 64-bit**. Mở PowerShell trong thư mục dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe run_project.py
```

Nếu máy có nhiều bản Python, chọn Python 3.12 bằng Python Launcher: `py -3.12 -m venv .venv`. Không cần kích hoạt môi trường nên không cần đổi ExecutionPolicy.

Môi trường `.venv` trên máy tạo bài đã được cài và kiểm tra. Khi chép sang máy khác phải tạo lại môi trường; không cần chép `.venv`.

Dữ liệu nguồn ZIP đã kèm theo nên lần chạy bình thường không tải lại. Nếu xóa ZIP, chương trình cần mạng để tải từ UCI. Việc cài thư viện cần mạng nếu máy chưa có các gói tương ứng.

### Chạy nhanh để kiểm tra

```powershell
.\.venv\Scripts\python.exe run_project.py --sizes 10000 --repeats 1
```

Lệnh này **ghi đè báo cáo và kết quả đo** bằng thử nghiệm nhỏ; không dùng số đo một lần làm kết quả cuối. Chạy lại cấu hình mặc định để khôi phục bài đầy đủ.

### Đo lại trên máy nhóm, giữ dữ liệu đã sinh

```powershell
.\.venv\Scripts\python.exe run_project.py --skip-generate --repeats 3
```

### Demo một truy vấn

```powershell
.\.venv\Scripts\python.exe demo.py --method csv_full --rows 1000000
.\.venv\Scripts\python.exe demo.py --method csv_chunk --rows 1000000
.\.venv\Scripts\python.exe demo.py --method duckdb_parquet --rows 1000000
```

Kết quả gồm nhóm tuổi, số hàng được chọn, tổng giá đơn vị và giá đơn vị trung bình. `price_sum` là tổng của giá đơn vị để tính mean, **không phải tổng giá trị giao dịch**. Thời gian demo một lần không thay thế benchmark lặp.

### Kiểm tra tính đúng

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Kiểm tra loại dữ liệu lỗi, giữ ngoại lệ hợp lệ, trùng ID, điều kiện biên, khối rỗng, tập không có kết quả, gộp trung bình có trọng số và sự tương đương của cả sáu phương pháp.

## Cách đo

Truy vấn thống nhất: lọc `house_age <= 30` và `mrt_distance_m <= 1000`, nhóm `age_band`, tính count, sum và mean của `price_10k_twd_per_ping`.

1. `csv_full`: Pandas đọc mọi cột.
2. `csv_columns`: chỉ đọc bốn cột dùng trong truy vấn.
3. `csv_typed`: thêm schema rõ ràng và category cho nhóm tuổi.
4. `csv_chunk`: đọc 50.000 hàng mỗi khối, gộp count/sum rồi tính mean.
5. `parquet_columns`: Parquet/Snappy, chỉ đọc bốn cột.
6. `duckdb_parquet`: SQL trên Parquet, một luồng, memory_limit=1GB.

Mỗi mức/phương pháp lặp 3 lần, mỗi lần tiến trình mới, xáo thứ tự bằng seed 42. Báo cáo trung vị, min/max thời gian và trung vị peak RAM. Thời gian gồm đọc và truy vấn, không gồm khởi động Python, import Pandas hay sinh dữ liệu. Import DuckDB lười và mở kết nối nằm trong thời gian phương pháp DuckDB. Giữ float64 cho giá và điều kiện lọc để tránh sai khác do float32.

Trên Windows, RAM dùng peak working set của cả tiến trình, bao gồm runtime/thư viện. Dùng `psutil` lấy mẫu 5 ms và high-water mark của hệ điều hành. Trên nền tảng khác chỉ có lấy mẫu thì có thể bỏ lỡ đỉnh ngắn. Không xóa cache hệ điều hành. Do đó không diễn giải đây là cold-cache hoặc RAM riêng DataFrame.

Kiểm tra nhóm/count chính xác; sum và mean dùng `rtol=1e-9, atol=1e-6`. Chi phí ghi CSV/Parquet được ghi riêng trong manifest. Phép đo chuyển CSV→Parquet và hòa vốn riêng nằm trong `report/kiem_chung_du_lieu_lon.html`. Bộ bảo vệ của benchmark thông thường dừng phép đo vượt 180 giây hoặc peak 4 GiB; đây là ngưỡng bảo vệ, không chứng minh chạy ngoài RAM.

## Cấu trúc

```text
run_project.py                 Chạy toàn bộ quy trình
run_vietnam.py                 Chạy phần Việt Nam độc lập
run_validation.py              Giới hạn commit, workload mới, chi phí chuyển đổi/hòa vốn
search_vietnam.py              Lọc có điều kiện, xem trước và xuất CSV
demo.py                        Chạy một truy vấn để demo
src/prepare.py                 Đọc, làm sạch, tạo dữ liệu mô phỏng theo khối
src/queries.py                 Sáu phương pháp trả về cùng một thống kê
src/worker.py                  Một phép đo trong tiến trình con
src/benchmark.py               Điều phối, đo, kiểm tra, tổng hợp
src/deliverables.py             Vẽ biểu đồ, tạo báo cáo và thuyết trình
data/raw/                      ZIP, XLSX gốc và CSV đổi tên cột
data/processed/                Dữ liệu thật sạch và thông tin nguồn
data/benchmark/                CSV/Parquet mô phỏng và manifest
data/vietnam/                  Bản trích nguồn Việt Nam, bản sạch và tập benchmark
results/                       Số đo thật, cấu hình máy và biểu đồ
results/vietnam/               Số đo riêng của dữ liệu Việt Nam
report/                        Báo cáo, thuyết trình, hướng dẫn bảo vệ
notebooks/01_do_an.ipynb        Notebook để khám phá và đọc kết quả
tests/                         Kiểm tra tính đúng
```

Notebook cần môi trường Jupyter có cùng thư viện nếu muốn chạy tương tác. Đây là đầu ra phụ; toàn bộ quy trình chính không cần Jupyter.

Tên trường, lớp, giảng viên chưa được cung cấp nên không tự điền. Khi nộp, bổ sung nếu trường yêu cầu.

Tạo lại file nén để gửi: `.\.venv\Scripts\python.exe package_project.py`. File được lưu ở `dist/DoAn_BatDongSan_Khoa_HanHan.zip`, gồm toàn bộ dữ liệu thử tải nhưng không kèm môi trường Python.
