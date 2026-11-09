# Danh mục nguồn dữ liệu của đồ án

## 1. UCI Real Estate Valuation

- Tác giả: I-Cheng Yeh (2018).
- Trang nguồn: https://archive.ics.uci.edu/dataset/477/real+estate+valuation+data+set
- DOI: https://doi.org/10.24432/C5J30W
- Giấy phép: CC BY 4.0 — https://creativecommons.org/licenses/by/4.0/
- 414 quan sát tại Đài Loan. Giá gốc: 10.000 TWD/ping.
- Bản gốc trong `raw/`, bản chuẩn hóa trong `processed/`.
- Bản thử tải trong `benchmark/` được **mô phỏng** từ mẫu gốc; không coi là giao dịch quan sát mới.

## 2. TiniX AI — Vietnam Real Estate Listings

- Nhà phát hành: TiniX AI (2026).
- Trang nguồn: https://huggingface.co/datasets/tinixai/vietnam-real-estates
- Commit: `ca3fedcbb089bf65f7e4cfb03316cce4bd0d779f`.
- Giấy phép: CC BY-NC 4.0 — https://creativecommons.org/licenses/by-nc/4.0/
- Đồ án dùng cho học tập phi thương mại; giữ ghi công nhà phát hành. Phần dữ liệu này không tự động có cùng giấy phép với mã nguồn hoặc UCI.
- Toàn nguồn công bố 3.500.744 hàng; đồ án trích cột từ bốn shard đầu, **1.400.300 hàng nguồn**.
- Sau quy tắc loại thiếu/sai miền các trường bắt buộc còn **1.297.417 hàng**.
- Các mức benchmark 100 nghìn, 500 nghìn, 1 triệu là mẫu **không hoàn lại**, không tạo thêm hàng mô phỏng. Bản nâng cấp dùng thứ tự hash của ID hàng nguồn + seed, ghi từng batch và giữ phiên bản DuckDB để tái lập; thay cho lấy mẫu NumPy của bản trước.
- Chỉ trích 9 cột có cấu trúc. Mô tả/tiêu đề/địa chỉ chi tiết không được tải. Bản trích không phải bản sao đầy đủ của shard.
- Có giá VND, diện tích m², nhãn tỉnh/quận/loại nhà, số phòng/tầng và thời điểm đăng. Giữ đơn vị và nhãn địa phương của nguồn.
- Không có ID bất động sản/tin hoặc nhãn bán/thuê đủ để xác nhận duy nhất và ý nghĩa giá giao dịch. Số hàng là số bản ghi tin đăng, không phải số giao dịch đã xác minh.
- Nguồn là dữ liệu bên thứ ba công bố; nhóm không tự thu thập/xác minh từng hàng hoặc bảo đảm độ bao phủ toàn thị trường.
- Phần đã tải nằm trong tháng 6–10/2025, chọn theo thứ tự shard nên không đại diện ngẫu nhiên toàn nguồn. Mẫu benchmark mới được xáo ngẫu nhiên từ phần đã tải và sạch.
- Bản trích nguồn, commit, checksum và byte tải: `vietnam/raw/source_metadata.json`.
- Quy tắc lọc, số hàng, chữ ký trùng và thiếu theo cột: `vietnam/processed/profile.json`.
- Bản sạch: `vietnam/processed/vietnam_clean.parquet`; xem nhanh: `vietnam/processed/vietnam_preview_1000.csv`.

Không nối trực tiếp giá của hai nguồn vì khác đơn vị, thời gian, schema và ý nghĩa giá. Các kết quả đo và truy vấn nằm trong hai thí nghiệm riêng.
