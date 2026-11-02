/**
 * 系统参数页（§7.20.1 · P9B-3 · T5）。
 *
 * ⚠️ **一次保存 = 一个 PUT**（委员会硬约束 1）—— 后端事务内**全改或全不改**
 * ⇒ 前端也**只发一个请求**（逐键 PATCH 会留半改状态）。
 *
 * ⚠️ **值是 JSONB** ⇒ 输入框给 **JSON 文本** ⇒ 保存前 `JSON.parse` ⇒
 * 解析失败**就地报错、不发请求**（解析失败不是后端的错）。
 *
 * ⚠️ **失败方向**：保存失败 ⇒ 显示错误且**不**显示「已保存」——「已保存」出现在
 * 失败时，管理员会以为改动生效了（实际一个键都没改）。
 *
 * ⚠️ **列表加载失败 ≠ 列表为空**（RF-12）：加载失败时**不渲染空表**，否则
 * 管理员读成「系统里一个参数都没有」⇒ 真相可能是「你没权限」。
 */
import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Input, Space, Table, Typography } from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import { systemSettingsApi, type SystemSettingOut } from '../../api/systemSettings';
import { describePcsError } from '../../api/errors';

/** 一行参数（含输入框里的 JSON 文本与就地解析错误）。 */
interface SettingRow {
  key: string;
  description: string | null;
  /** 服务端当前值（用于判定「改没改」）。 */
  original: unknown;
  /** 输入框里的 JSON 文本。 */
  text: string;
  /** 服务端算出的最后更新时间（UTC ISO）。 */
  updatedAt: string;
  /** 该行的 JSON 解析错误（就地显示）。 */
  parseError: string | null;
}

/**
 * 时间戳显示（**UTC**，固定格式）。
 *
 * ⚠️ 不用 `toLocaleString` —— 那是运行机器的时区 ⇒ 同一份数据在不同机器上
 * 显示不同 ⇒ 单测没法断言。
 */
function formatUtc(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.toISOString().slice(0, 16).replace('T', ' ')} UTC`;
}

/** 服务端值 → 输入框里的 JSON 文本。 */
function toText(value: unknown): string {
  return JSON.stringify(value ?? null) ?? 'null';
}

/** 两个 JSON 值是否相等（按规范化后的 JSON 文本比）。 */
function sameValue(a: unknown, b: unknown): boolean {
  return JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
}

function toRow(item: SystemSettingOut): SettingRow {
  return {
    key: item.setting_key,
    description: item.description ?? null,
    original: item.setting_value_json,
    text: toText(item.setting_value_json),
    updatedAt: item.updated_at,
    parseError: null,
  };
}

export function SystemSettingsPage(): JSX.Element {
  const [rows, setRows] = useState<SettingRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // ⚠️ 列表加载失败 ⇒ **不渲染空表**（空表会被读成「没有数据」）。
  const [listFailed, setListFailed] = useState(false);

  /** 拉列表。返回 `false` = 拉取失败（调用方据此决定要不要报「已保存」）。 */
  const load = useCallback(async (): Promise<boolean> => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const list = await systemSettingsApi.list();
      setRows(list.map(toRow));
      setListFailed(false);
      return true;
    } catch (err) {
      setRows([]);
      setListFailed(true);
      setErrorMsg(describePcsError(err, '加载系统参数失败'));
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  /** 改某行的输入框文本。 */
  function editText(key: string, text: string): void {
    setRows((prev) =>
      prev.map((r) => (r.key === key ? { ...r, text, parseError: null } : r)),
    );
  }

  async function save(): Promise<void> {
    setErrorMsg(null);
    setNotice(null);

    // ⚠️ **先就地解析**：任何一个键的文本不是合法 JSON ⇒ **一个请求都不发**
    //（解析失败不是后端的错）。
    const changed: Record<string, unknown> = {};
    const parseErrors: Record<string, string> = {};
    for (const row of rows) {
      let parsed: unknown;
      try {
        parsed = JSON.parse(row.text);
      } catch (err) {
        parseErrors[row.key] = `不是合法 JSON：${(err as Error).message}`;
        continue;
      }
      if (!sameValue(parsed, row.original)) changed[row.key] = parsed;
    }

    if (Object.keys(parseErrors).length > 0) {
      setRows((prev) =>
        prev.map((r) => (r.key in parseErrors ? { ...r, parseError: parseErrors[r.key] } : r)),
      );
      setErrorMsg('有参数的值不是合法 JSON，已在对应行标出（未发送请求）');
      return;
    }

    if (Object.keys(changed).length === 0) {
      setNotice('没有改动，无需保存');
      return;
    }

    setSaving(true);
    try {
      await systemSettingsApi.save(changed);
      // ⚠️ 保存后**重新拉**（拿服务端算出的 updated_at 与最终值）。
      const ok = await load();
      if (ok) setNotice(`已保存 ${Object.keys(changed).length} 个参数`);
    } catch (err) {
      setErrorMsg(describePcsError(err, '保存系统参数失败'));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div data-testid="system-settings-page">
      <PageHeader
        title="系统参数"
        actions={
          <Space>
            <Button data-testid="system-settings-save" type="primary" loading={saving} onClick={() => void save()}>
              保存
            </Button>
            <Button data-testid="system-settings-reload" onClick={() => void load()}>
              刷新
            </Button>
          </Space>
        }
      />

      {errorMsg && (
        <Alert
          type="error"
          showIcon
          message={errorMsg}
          data-testid="system-settings-error"
          style={{ marginBottom: 16 }}
          // ⚠️ 列表加载失败 ⇒ 错误提示**不可关闭**（关掉 = 假装没有数据）。
          closable={!listFailed}
          onClose={() => setErrorMsg(null)}
        />
      )}
      {notice && (
        <Alert
          type="success"
          showIcon
          message={notice}
          data-testid="system-settings-notice"
          style={{ marginBottom: 16 }}
        />
      )}

      <Table<SettingRow>
        rowKey={(r) => r.key}
        loading={loading}
        dataSource={listFailed ? [] : rows}
        pagination={false}
        columns={[
          {
            title: '参数键',
            dataIndex: 'key',
            width: 260,
          },
          {
            title: '值（JSON）',
            dataIndex: 'text',
            render: (text: string, row) => (
              <div>
                <Input
                  data-testid={`setting-input-${row.key}`}
                  value={text}
                  style={{ width: 280 }}
                  onChange={(e) => editText(row.key, e.target.value)}
                />
                {row.parseError && (
                  <Typography.Text
                    type="danger"
                    data-testid={`setting-error-${row.key}`}
                    style={{ display: 'block' }}
                  >
                    {row.parseError}
                  </Typography.Text>
                )}
              </div>
            ),
          },
          {
            title: '说明',
            dataIndex: 'description',
            render: (d: string | null) => d ?? '—',
          },
          {
            title: '更新时间',
            dataIndex: 'updatedAt',
            render: (iso: string) => formatUtc(iso),
          },
        ]}
      />
    </div>
  );
}
