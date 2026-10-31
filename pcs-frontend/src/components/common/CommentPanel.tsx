/**
 * 批注面板（P9B-2 · T5 · SPEC §7.19.1「批注面板：右侧抽屉」）。
 *
 * ⚠️ **空白不是内容**：后端 `CommentCreateRequest` 拒纯空白
 * （`min_length=1` 拦不住 `"   "`）⇒ 前端 `trim()` 后为空 ⇒ 发送禁用。
 *
 * ⚠️ **分页按 `total`**：后端排序带 `comment_id` tiebreaker（`created_at` 是
 * `server_default=func.now()`，SQLite 下只有秒级粒度）⇒ 「加载更多直到空」
 * 会漏条或重复 ⇒ 按 `total` 算页数。
 *
 * ⚠️ **批注不写 `workflow_progress`**（ADR-0047 §①）：「有人留言」不是流程活动。
 *
 * ⚠️ **403 / 404 ⇒ 明说「无权查看」**，**不得**渲染成空列表（RF-12）——
 * 空列表会被读成「还没有人留言」。
 */
import { useCallback, useEffect, useState } from 'react';
import { Button, Empty, Input, List, Pagination, Space, Typography } from 'antd';

import { commentsApi } from '../../api/recordActions';
import { extractPcsError } from '../../api/errors';
import type { EditableRecordType } from '../../api/records';

export interface CommentPanelProps {
  module: EditableRecordType;
  recordId: string;
}

const PAGE_SIZE = 20;

export function CommentPanel({ module, recordId }: CommentPanelProps): JSX.Element {
  const [items, setItems] = useState<{ comment_id: string; body: string; author_id: string; created_at: string }[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);

  const load = useCallback(
    async (targetPage: number) => {
      setLoading(true);
      setError(null);
      try {
        const res = await commentsApi.list(module, recordId, {
          limit: PAGE_SIZE,
          offset: (targetPage - 1) * PAGE_SIZE,
        });
        setItems(res.items);
        setTotal(res.total);
        setPage(targetPage);
      } catch (err) {
        const envelope = extractPcsError(err);
        const status = (err as { response?: { status?: number } })?.response?.status;
        // ⚠️ **不得**渲染成空列表（RF-12）
        setItems([]);
        setTotal(0);
        setError(
          status === 403
            ? '无权查看批注'
            : status === 404
              ? '记录不存在或无权查看批注'
              : envelope?.message
                ? `加载批注失败：${envelope.message}`
                : '暂时无法加载批注',
        );
      } finally {
        setLoading(false);
      }
    },
    [module, recordId],
  );

  useEffect(() => {
    void load(1);
  }, [load]);

  async function send() {
    const text = body.trim();
    // ⚠️ 纯空白不是内容（后端也拒，但前端先拦）
    if (!text) return;
    setSending(true);
    setError(null);
    try {
      await commentsApi.create(module, recordId, text);
      setBody('');
      // ⚠️ 评审 B-4：**重拉最后一页**（不是本地 append 到当前页）——
      //    后端按 `created_at ASC` 排 ⇒ 新批注永远在**最后一页**的末尾；
      //    在非最后一页发送时本地 append 会把它放错页（刷新后跳走），
      //    还可能让当前页显示 21 条。重拉 = 位置来自后端真相。
      const nextPage = Math.max(1, Math.ceil((total + 1) / PAGE_SIZE));
      await load(nextPage);
    } catch (err) {
      const envelope = extractPcsError(err);
      setError(
        envelope?.code
          ? `${envelope.code}：${envelope.message ?? ''}`
          : '发送批注失败',
      );
    } finally {
      setSending(false);
    }
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div data-testid="comment-panel">
      <Typography.Text strong>批注</Typography.Text>
      <Input.TextArea
        data-testid="comment-input"
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="留一条批注"
        rows={3}
      />
      <Space>
        <Button
          type="primary"
          data-testid="comment-send"
          disabled={!body.trim() || sending}
          onClick={() => void send()}
        >
          发送
        </Button>
      </Space>
      {error && (
        <Typography.Text type="danger" data-testid="comment-error">
          {error}
        </Typography.Text>
      )}
      {!error && items.length === 0 && !loading && (
        <Empty data-testid="comment-empty" description="尚无批注" />
      )}
      <List
        dataSource={items}
        loading={loading}
        renderItem={(item) => (
          <List.Item data-testid={`comment-item-${item.comment_id}`}>
            <List.Item.Meta
              title={item.author_id}
              description={
                <>
                  <Typography.Text>{item.body}</Typography.Text>
                  <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
                    {item.created_at}
                  </Typography.Text>
                </>
              }
            />
          </List.Item>
        )}
      />
      {/* ⚠️ **分页**（不是「加载更多」）：页数 = ceil(total / limit) */}
      {pageCount > 1 && (
        <Pagination
          data-testid="comment-pagination"
          current={page}
          pageSize={PAGE_SIZE}
          total={total}
          onChange={(p) => void load(p)}
        />
      )}
    </div>
  );
}
