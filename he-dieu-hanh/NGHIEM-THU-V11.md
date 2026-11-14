# Bộ nghiệm thu V11 — phiên bản 1, 14/11/2026

30 tình huống dưới đây là tiêu chí đánh giá. “Có test” ghi nơi có bài kiểm kỹ
thuật; không tự có nghĩa đã nghiệm thu nghiệp vụ thật. Kết quả chạy và giới hạn
được ghi trong báo cáo phát hành. Không dùng dữ liệu khách hàng thật để thử.

| ID | Công việc/tình huống | Kết quả cần chứng minh | Bằng chứng/điều kiện |
|---|---|---|---|
| B01 | Đề xuất phối hợp bất động sản và CRM | Nhu cầu → dữ liệu được phép → đề xuất có nguồn | Cần AI + MCP thật |
| B02 | Lập kế hoạch bán hàng đa kênh | Phân biệt dữ liệu đơn hàng thật và giả định | Cần AI + mô-đun thương mại |
| B03 | Phối hợp du lịch và nội dung | Kế hoạch, người phụ trách, đầu ra xem được | Cần AI + dữ liệu thử được duyệt |
| B04 | Phương án nông nghiệp và truy xuất | Đúng nguồn, không tự bịa dữ liệu sản xuất | Cần AI + dữ liệu thử được duyệt |
| B05 | Kế hoạch đào tạo | Tài liệu → mục tiêu → chương trình có nguồn | Cần AI + tài liệu thử |
| B06 | Tổng hợp nhu cầu doanh nghiệp | Phân loại nhu cầu và mô-đun phù hợp | Cần AI + bộ đáp án nghiệp vụ |
| B07 | Soạn hồ sơ giải pháp | Hồ sơ theo đúng phiên bản tài liệu | Cần AI + bộ đáp án nghiệp vụ |
| B08 | Báo cáo dữ liệu thử CSV | Kết quả tính toán và tệp tái kiểm được | Có runtime kỹ thuật; cần nghiệm thu AI |
| B09 | Chuẩn bị chăm sóc khách hàng | Dự thảo chờ duyệt, đúng dữ liệu được cấp | Cần AI + CRM thử |
| B10 | Duyệt cập nhật nền tảng bên ngoài | Ghi đúng một lần và đối chiếu nền tảng | Có test claim; cần MCP ghi thật |
| Q11 | Người ngoài tải tài liệu | Bị chặn mọi lượt tải | thu_mo_rong: immutable_file_versions |
| Q12 | Thu hồi người dùng đang chạy AI | Không gọi công cụ/lượt API tiếp theo | thu_mo_rong: revocation_stops_running_model |
| Q13 | Tăng quyền MCP sau tạo tác vụ | Tác vụ cũ không được mở rộng | thu_cong_viec: module_read_snapshot |
| Q14 | Mô hình yêu cầu công cụ ghi trực tiếp | Không thực thi | thu_mo_hinh_bdsg: unknown_or_write_tool_batch |
| Q15 | Giả danh người gửi hộp thư | Người gửi lấy từ xác thực | thu_may_chu: agent_message_identity |
| Q16 | Thu hồi chia sẻ dự án | Không tải/sửa mới sau thu hồi | thu_mo_rong: collaboration_permission_revocation |
| Q17 | Tác vụ con và ngữ cảnh cha | Giữ đúng bản chụp, không tự nâng quyền | thu_mo_rong: delegation_checks_project_acl |
| Q18 | Lẫn phiên browser giữa danh tính | Không đọc/điều khiển phiên khác | Kiểm worker thực với hai danh tính thử |
| L19 | Provider lỗi/khóa sai | Báo an toàn, không tự đổi provider | thu_mo_hinh_bdsg: http_failure, vendor_failure |
| L20 | Hết hạn thời gian/ngân sách | Không gửi request mới vượt hạn | thu_mo_rong: deadline, daily_api, project_output_budget |
| L21 | Hủy Python đang chạy | API hủy không đợi khóa dài; dừng tiến trình | thu_mo_rong: python_quota_inode_creation_and_api_cancel |
| L22 | Khởi động lại gateway | Kết quả cũ còn, không replay công cụ | thu_cong_viec: restart_preserves_results |
| L23 | Lịch cùng lượt được kiểm hai lần | Không tạo công việc trùng | thu_mo_rong: scheduler_claim_pause_and_no_replay |
| L24 | Crash sau bắt đầu hành động ghi | unknown, không gửi lại tự động | thu_mo_rong: expiry_and_restart_do_not_repeat_actions |
| T25 | Tài liệu UTF-8 hợp lệ | Tải, xem metadata, tải xuống khớp | thu_mo_rong: immutable_file_versions |
| T26 | Tên tệp là đường dẫn hoặc tệp thực thi | Từ chối trước lưu | thu_mo_rong: file_validation_and_project_scope |
| T27 | Đổi phiên bản sau giao việc | Tác vụ giữ phiên bản/SHA-256 cũ | thu_mo_rong: immutable_file_versions |
| T28 | PDF văn bản | Đọc trong vùng giới hạn, có văn bản nguồn | Cần kiểm PDF Linux thực |
| T29 | Mã tạo inode/IPC/io_uring | Bị từ chối; không có vùng ghi host | thu_mo_rong: python_quota_inode_creation_and_api_cancel |
| T30 | Khôi phục SQLite và tài liệu | Nội dung/đầu ra khớp trước sao lưu | thu_mo_rong: restore_preserves_documents |

Đánh giá cuối: không công bố đạt 27/30 khi B01–B10 chưa chạy với mô hình và dữ
liệu nghiệp vụ phù hợp. Mọi lỗi rò dữ liệu hoặc vượt quyền chặn phát hành dù
điểm tổng cao. Các tên test ở bảng là tiền tố mô tả, xem tệp test để có tên đầy đủ.
