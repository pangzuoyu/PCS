"""通知写侧包（ADR-0049 §①）。

模块边界：
- `payload.py`  —— DTO 与 `detail_json` 的 schema（P9A-DLV-010）
- `channel.py`  —— `NotificationChannel` 协议 + `DeliveryResult`
- `in_app.py`   —— 本版唯一的通道实现，只写 `notifications` 表

⚠️ **本包不 import 推送相关模块**（broadcaster / redis / websocket）。
ADR §①：通道不应该知道 WebSocket 存在 —— 一个「邮件通道」里出现
WebSocket 调用是荒谬的。推送接线在包外（见 `notify.py`）。
"""
