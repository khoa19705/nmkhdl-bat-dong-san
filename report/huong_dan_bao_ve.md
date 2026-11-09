# Hướng dẫn đọc bài và bảo vệ

## Phần kiểm chứng cuối cần giải thích đúng

Mở `report/kiem_chung_du_lieu_lon.html`. Đây là nơi trả lời bốn câu hỏi về quy mô, nhiều truy vấn, đánh đổi và đóng góp dữ liệu.

- Một triệu hàng vẫn vừa máy 16 GB. Thí nghiệm mới giới hạn **committed virtual memory** toàn tiến trình Windows, không nhận máy chỉ có 256/512 MiB RAM vật lý.
- Giới hạn được gắn trước import; có đối chứng cấp phát nhỏ/thử vượt hạn mức và đọc lại Job Object. DuckDB buffer budget khác hạn mức OS.
- OOM, timeout và lỗi native là kết quả phải báo, không xóa các ca thất bại hoặc ghi thời gian chúng là 0. Trung vị chỉ tính ca hoàn thành và đúng.
- RSS trong bảng là high-water của ca hoàn thành; commit lấy từ Job Object có snapshot xác nhận. Lỗi native không có snapshot thì để thiếu. Mẫu từ tiến trình cha trong số đo thô chỉ là cận dưới, không khẳng định là đỉnh thật.
- Top 100 tin giá cao khác top 3 loại có nhiều tin: xếp hạng giá giảm dần, phá hòa bằng ID hàng nguồn. Chunk giữ top 100 ứng viên qua từng khối; thứ tự toàn phần bảo đảm không bỏ ứng viên có thể thuộc top toàn cục.
- Giá cực lớn có thể là lỗi của nguồn; thứ hạng không chứng nhận giá hợp lý, giao dịch đã chốt hoặc căn nhà duy nhất.
- Chi phí C là đọc CSV, chuyển kiểu, nén/ghi Parquet và đóng writer. Không dùng thời gian ghi Parquet sẵn có để thay C. File vừa chuyển được dùng để đo truy vấn lặp.
- Có thêm đối chứng DuckDB đọc CSV trực tiếp. Khi so với cách này, lợi ích chuyển định dạng có thể cần nhiều truy vấn hơn so với Pandas; không nói chung rằng cứ một hoặc hai truy vấn là nên chuyển.
- Điểm hòa vốn là mô hình theo trung vị đo thật; nói rõ không chạy thực tế mọi N trên đồ thị. Nếu CSV không hoàn thành dưới hạn mức thì cần xét tính khả thi trước tỷ lệ tăng tốc.
- Nguồn là bộ tin đăng công khai. Nhóm đóng góp quy trình xây dựng dữ liệu phân tích và kiểm chứng, không nhận đã tự quan sát/thu thập hơn một triệu giao dịch.

## Chức năng nâng cấp cần demo

1. Mở `report/nang_cap_he_thong.html`, chỉ bảng thiếu trước–sau và biểu đồ chunk size.
2. Chạy `search_vietnam.py` với tỉnh/loại nhà/khoảng giá/diện tích; chỉ ra số hàng khớp khác số hàng xem trước. Xuất CSV lấy toàn bộ hàng khớp.
3. Mở `rejected_rows.csv`, giải thích lý do loại và cách tìm lại hàng nguồn qua shard + row (đếm từ 0).
4. Mở một `results/vietnam/history/<run-id>/config.json` và `status.json`, giải thích checksum, cấu hình và trạng thái thành công/thất bại.
5. Trình bày ba tải province/month/top_types. Top 3 phải gộp toàn bộ nhóm rồi chọn, không chỉ ghép top từng chunk.

**“Chia chunk trong truy vấn đã đủ xử lý dữ liệu lớn chưa?”** Cần xét toàn quy trình. Bản mới đọc và làm sạch theo batch, lấy mẫu qua DuckDB có vùng tràn đĩa, rồi ghi CSV/Parquet theo batch; không còn nạp toàn bảng sạch vào Pandas để chọn mẫu. RAM của DuckDB có ngân sách bộ quản lý bộ nhớ, không phải giới hạn cứng toàn tiến trình. Dữ liệu thử vẫn vừa RAM nên chưa nhận đã chứng minh xử lý ngoài RAM.

**“Vì sao chọn chunk 50.000?”** Đọc kết quả thực tế trong báo cáo nâng cấp, vì chunk nhanh nhất và ít RAM nhất có thể khác nhau. 50.000 là cấu hình mặc định cân bằng được đem so với 10.000 và 100.000, không mặc định là tối ưu toàn cục.

**“Lấy mẫu mới có khác bản đầu?”** Có. Thứ tự hash xác định từ ID nguồn/seed giúp tạo mẫu theo luồng và giữ tính lồng nhau. Phiên bản DuckDB được ghim vì hàm hash có thể đổi. Số đo đã chạy lại; kết quả cũ lưu trong legacy. Không gọi đây là mẫu phân tầng hoặc đại diện toàn Việt Nam.

## Bản mở rộng có thêm nguồn Việt Nam

Đọc `report/bo_sung_du_lieu_viet_nam.html` trước khi dùng phần mở đầu cũ bên dưới. Nhóm hiện có cả dữ liệu UCI và tin đăng Việt Nam do TiniX AI công bố. Phần Việt Nam trích 9 cột từ 4 shard, không phải nhóm tự cào tin hoặc xác minh giao dịch. Toàn nguồn do nhà phát hành công bố hơn 3,5 triệu hàng; đồ án chỉ tải phần được ghi trong metadata.

Khi giới thiệu bản mở rộng, có thể nói: “Bên cạnh mẫu UCI và thí nghiệm mô phỏng, nhóm bổ sung hơn một triệu bản ghi tin đăng Việt Nam từ nguồn công khai. Nhóm giữ phiên bản nguồn, kiểm tra chất lượng rồi lấy mẫu không hoàn lại để chạy một thí nghiệm riêng. Tin đăng có thể lặp và chưa có nhãn phân biệt bán/thuê, nên kết quả giá dùng để kiểm tra tính đúng của phép tính, không được nhận là giá bán thực tế của thị trường.”

Nếu thầy hỏi vì sao không gộp hai nguồn: UCI có tuổi nhà/khoảng cách MRT và giá đơn vị TWD; nguồn Việt Nam có diện tích/địa phương và giá đăng VND. Không có schema và ý nghĩa giá tương đương để cộng chung. Nhóm kiểm nghiệm cùng các kỹ thuật trên hai bài toán riêng.

Nếu hỏi “1 triệu hàng Việt Nam có phải mô phỏng?”: không sinh thêm hàng; đây là mẫu không hoàn lại từ phần nguồn tải về đã qua quy tắc lọc. Tuy nhiên số hàng tin đăng không chứng minh có cùng số căn nhà duy nhất hoặc giao dịch đã chốt.

Muốn xem dấu vết: `data/vietnam/raw/source_metadata.json` có commit và checksum; `data/vietnam/processed/profile.json` có số hàng sạch và loại; `results/vietnam/runs.json` có từng phép đo và thống kê đầu ra. Các nhận xét về nguồn gốc UCI trong phần hỏi đáp cũ bên dưới chỉ áp dụng thí nghiệm UCI ban đầu.

## Nói mở đầu khoảng 45 giây

“Đề tài của nhóm là xây dựng bộ dữ liệu bất động sản và đánh giá cách tối ưu xử lý khi dữ liệu tăng. Nhóm dùng dữ liệu giao dịch công khai của UCI để làm sạch và phân tích. Vì nguồn chỉ có 414 quan sát, nhóm tạo riêng dữ liệu mô phỏng tới một triệu hàng để thử tải. Nhóm so sánh sáu phương án trên cùng một truy vấn, đo thời gian, bộ nhớ và kiểm tra kết quả thống kê có tương đương hay không.”

## Demo theo thứ tự

1. Mở `report/bao_cao.html`, giới thiệu nguồn và sự phân biệt thật/mô phỏng.
2. Mở `src/queries.py`: chỉ ra baseline đọc toàn bộ; `usecols`; `dtype`; vòng lặp chunk; truy vấn SQL.
3. Chạy `demo.py` với `csv_full`, `csv_chunk`, `duckdb_parquet` ở cùng mức dữ liệu. Đối chiếu count và mean các nhóm.
4. Mở `results/summary.csv`, nói kết quả từ ba lần lặp; không coi một lần demo là kết luận.
5. Mở `results/environment.json` để chỉ ra máy và thư viện đã đo. Nếu đo lại trên máy nhóm, báo cáo sẽ cập nhật theo máy nhóm.

Các lệnh chính có trong README. Không cần chạy sinh lại một triệu hàng khi đang thuyết trình.

## Câu hỏi thường gặp

**1. Tại sao không tự cào tin đăng ở Việt Nam?**

Phạm vi hiện tại tập trung quy trình dữ liệu và hiệu năng; dùng nguồn công khai có xuất xứ và giấy phép giúp tái lập. Không tuyên bố đây là dữ liệu Việt Nam. Thu thập tin đăng Việt Nam là hướng mở rộng riêng, còn cần xử lý đơn vị, trùng tin và điều kiện truy cập nguồn.

**2. Một triệu dòng này có thật không?**

Không. Đây là dữ liệu mô phỏng được lấy mẫu và nhiễu từ nguồn nhỏ để kiểm thử tải. Mỗi hàng có `is_synthetic=True`. Phân tích thực tế chỉ dùng 414 quan sát gốc.

**3. Xây dựng dữ liệu ở đây là làm gì?**

Tiếp nhận nguồn, lưu bản gốc, tạo schema thống nhất, kiểm tra thiếu/sai miền/trùng ID, bổ sung biến dẫn xuất có định nghĩa, lưu CSV/Parquet và mô tả nguồn. Phần tạo tải là bước riêng, không phải thu thập giao dịch mới.

**4. Vì sao không xóa tất cả ngoại lệ?**

Giá cao hoặc thấp có thể là giao dịch hợp lệ. Nhóm đánh dấu theo IQR để xem xét, chỉ loại những vi phạm quy tắc chất lượng đã nêu. Dữ liệu nguồn hiện không có giá trị thiếu nên không cần bịa thêm một bước điền thiếu.

**5. Chunk giúp gì? Có nhanh nhất không?**

Chunk giới hạn lượng dữ liệu nạp cùng lúc, hữu ích khi file lớn. Nó có chi phí lặp và gộp nên có thể chậm hơn cách nạp một lần. Đọc số đo để kết luận thay vì mặc định chunk luôn nhanh.

**6. Vì sao không lấy trung bình các trung bình từng chunk?**

Nếu chunk A có 1 nhà giá đơn vị 100 và chunk B có 9 nhà giá đơn vị 10, trung bình hai mean là 55 nhưng mean đúng là `(100 + 90) / 10 = 19`. Vì vậy cộng sum và count trước rồi mới chia.

**7. Vì sao không tính trung vị theo chunk?**

Trung vị của các trung vị không cho trung vị toàn tập nói chung. Bài chọn count/sum/mean vì các thống kê này gộp chính xác được theo khối. Trung vị xuất hiện trong EDA trên mẫu nhỏ đọc toàn bộ và trong tổng hợp thời gian lặp, không phải gộp trung vị giá các chunk.

**8. Chọn cột khác Parquet ở đâu?**

`usecols` giúp Pandas không tạo cột không dùng trong bộ nhớ, nhưng CSV vẫn là văn bản theo hàng. Parquet lưu theo cột, có nén và metadata, nên bộ đọc có thể truy cập cột cần thiết. Hiệu quả tùy truy vấn và dữ liệu.

**9. Projection/filter pushdown là gì?**

Projection là chọn cột; filter là chọn hàng theo điều kiện. Pushdown là thực hiện lựa chọn gần bước đọc nhất để giảm dữ liệu phải chuyển và xử lý. Khả năng bỏ qua row group còn phụ thuộc thống kê và phân bố trong file; bài không tuyên bố mọi row group đều được bỏ qua.

**10. Vì sao giữ float64 thay vì ép mọi số thành float32?**

Ép kiểu có thể làm đổi giá hoặc điều kiện sát ngưỡng lọc. Nhóm giữ float64 cho giá, tuổi nhà, khoảng cách; tối ưu category với cột nhóm ít giá trị và kiểu nguyên nhỏ sau kiểm tra miền. Tính đúng được ưu tiên khi so sánh cùng tác vụ.

**11. Đo RAM thế nào?**

Peak working set toàn tiến trình trên Windows, có runtime/thư viện. Không phải chỉ `DataFrame.memory_usage` và không phải phần trăm RAM toàn máy. Mỗi phép đo có tiến trình riêng để hạn chế bộ nhớ lần trước còn giữ lại.

**12. Tại sao ba lần đo khác nhau?**

Tải nền, bộ đệm file và lập lịch CPU ảnh hưởng. Nhóm xáo thứ tự, dùng ba lần và báo trung vị/min/max. Chưa có kiểm soát cold-cache và khoảng tin cậy, nên không nói mọi lần chạy đều đúng một con số.

**13. Đây đã là Big Data chưa?**

Đây là thử nghiệm mở rộng tải trên một máy. Một triệu hàng trong bài có thể vẫn vừa RAM 16 GB. Nhóm đánh giá các kỹ thuật có ích khi dữ liệu tăng, chưa chứng minh giải quyết dữ liệu thật vượt RAM hoặc hạ tầng phân tán.

**14. Nén tốt như vậy có áp dụng cho mọi dữ liệu không?**

Không. Dữ liệu mô phỏng từ mẫu nhỏ có nhiều giá trị lặp nên dễ nén hơn. Cần thử nguồn thực đa dạng hơn trước khi suy rộng.

**15. Tại sao không dự đoán giá?**

Mục tiêu chính là dữ liệu và hiệu năng xử lý; không phải dự báo. Nhóm hoàn thành EDA và kiểm nghiệm kỹ thuật tối ưu. Chỉ thêm mô hình khi yêu cầu môn học có nội dung đó, và không đánh giá mô hình trên bootstrap như thể là giao dịch mới độc lập.

**16. Nhóm có đóng góp gì và đã dùng công cụ hỗ trợ ra sao?**

Hai thành viên cần tự đọc, chạy lại, xác nhận số đo và giải thích lựa chọn. Trình bày trung thực công cụ hỗ trợ đã dùng theo yêu cầu môn học; không nhận đã thu thập thủ công hoặc tự quan sát một triệu giao dịch. Chưa có bảng phân công hoàn thành cá nhân vì nhóm chưa xác nhận công việc thực tế của mỗi người.

## Trước khi nộp

- Kiểm tra đúng mã sinh viên, tên giảng viên/lớp nếu cần bổ sung.
- Đọc kỹ các cột, đơn vị và cách gộp chunk.
- Chạy lại trên máy sẽ dùng demo nếu có thể; số đo phụ thuộc máy.
- Đừng sửa số trong bảng bằng tay; sửa code rồi chạy lại để số và biểu đồ khớp.
- Nếu gửi file nén, giữ nguồn, code, kết quả và dữ liệu; không đưa `.venv` vào.
