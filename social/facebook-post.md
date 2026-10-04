Mình vừa làm một app nhỏ cho những ai dùng nhiều tài khoản Claude trên Mac: **Claude Harbor** ⚓️

Ý tưởng xuất phát từ một nhu cầu rất thực tế: mở cùng lúc nhiều bản Claude Desktop, mỗi bản dùng một tài khoản riêng, rồi chuyển sang tài khoản khác mà vẫn tiếp tục được lịch sử làm việc trong tab Code.

Claude Harbor gom việc đó vào một cửa sổ:

• Tạo thêm bản Claude Desktop và đăng nhập riêng từng tài khoản.
• Mở một bản hoặc tất cả cùng lúc, không cần dùng giao diện Terminal.
• Bấm “Đồng bộ tất cả”: app chờ lượt trả lời kết thúc, đóng các bản Claude, sao lưu và đồng bộ lịch sử, rồi mở lại.
• Nếu cùng một hội thoại được tiếp tục theo hai hướng khác nhau, giữ cả hai nhánh.
• Có menu nhanh trên thanh menu macOS và báo cáo những session thiếu nội dung.

Ở bộ dữ liệu mình kiểm tra, 3.146 nhóm phiên đã có mặt trong cả ba profile, không có khác biệt nội dung hội thoại trong phạm vi đã đồng bộ. Bản public đầu tiên cũng đã qua 18 kiểm thử tự động.

Đây là **v0.1.0**, hiện hỗ trợ **Code local trên cùng máy Mac**. Chưa đồng bộ Chat web, Cowork hay cloud; không thể khôi phục transcript đã mất. App cần đóng các bản Claude trong lúc đồng bộ. Bản tải sẵn dành cho Apple Silicon, macOS 14+, và cần cài Claude Desktop chính thức cùng Apple Command Line Tools. Release chưa được Apple notarize.

Mình đã public mã nguồn theo MIT, kèm README và screenshot:
👉 https://github.com/anlvdt/claude-harbor

Tải bản đầu tiên:
👉 https://github.com/anlvdt/claude-harbor/releases/tag/v0.1.0

Nếu bạn cũng hay đổi giữa tài khoản cá nhân và công việc trong Claude Code, mời dùng thử và góp ý qua GitHub Issues. Đây là tiện ích cộng đồng độc lập, không phải app chính thức của Anthropic.

#ClaudeHarbor #ClaudeCode #ClaudeDesktop #macOS #OpenSource
