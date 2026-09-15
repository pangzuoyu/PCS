/**
 * ConflictResolver — SIM 物性冲突展示（P45-1-9 / Task 14）。
 *
 * SPEC §6.10 + plan P45-1-9：
 * - 三级：BLOCK 红 / WARN 黄 / INFO 蓝
 * - 卡片：[级别] 字段名（中文 label）
 *   用户输入: X unit / 计算值: Y unit / 偏差: Z%
 *   [采用用户值] [采用计算值]
 * - 字段优先级（显示在卡片底部，提示用户）：
 *   - 用户值优先：物性类（mw、bp、density 等）
 *   - 计算值优先：molecular_weight / total_mass_flow / total_molar_flow
 *
 * Props（SPEC 锁定）：
 *   conflicts: Conflict[]
 *   onResolve?: (field, choice) => void
 *     field  = 冲突字段名
 *     choice = 'USER' | 'CALC'
 */
import { Card, Space, Tag, Typography, Button } from 'antd';

export type ConflictLevel = 'BLOCK' | 'WARN' | 'INFO';
export type ConflictChoice = 'USER' | 'CALC';

export interface Conflict {
  field: string;
  field_label?: string;
  level: ConflictLevel;
  user_value: number | string;
  calc_value: number | string;
  user_unit?: string;
  calc_unit?: string;
  /** 偏差百分比字符串（如 "0.07%"），由调用方算好 */
  deviation_pct?: string;
}

interface Props {
  conflicts: Conflict[];
  onResolve?: (field: string, choice: ConflictChoice) => void;
}

const LEVEL_COLOR: Record<ConflictLevel, string> = {
  BLOCK: 'red',
  WARN: 'orange',
  INFO: 'blue',
};

const LEVEL_LABEL: Record<ConflictLevel, string> = {
  BLOCK: '阻止保存',
  WARN: '提示',
  INFO: '提示',
};

/** SPEC 字段优先级（用户值优先的字段集） */
const USER_PRIORITY_FIELDS = new Set([
  'molecular_weight', // 显式说明：计算值优先
  'total_mass_flow', // 显式说明：计算值优先
  'total_molar_flow', // 显式说明：计算值优先
]);

/** 反过来：默认用户值优先（物性类），仅以上三个计算值优先 */
function defaultPriority(field: string): ConflictChoice {
  return USER_PRIORITY_FIELDS.has(field) ? 'CALC' : 'USER';
}

export function ConflictResolver({ conflicts, onResolve }: Props): JSX.Element {
  if (conflicts.length === 0) {
    return (
      <Card data-testid="conflict-resolver" title="物性冲突">
        <Typography.Text type="secondary">无冲突</Typography.Text>
      </Card>
    );
  }

  return (
    <div data-testid="conflict-resolver">
      <Typography.Title level={5} style={{ marginTop: 16 }}>
        物性冲突（{conflicts.length}）
      </Typography.Title>
      <Space direction="vertical" style={{ width: '100%' }}>
        {conflicts.map((c) => {
          const priority = defaultPriority(c.field);
          return (
            <Card
              key={c.field}
              data-testid="conflict-card"
              data-conflict-field={c.field}
              data-conflict-level={c.level}
              size="small"
              style={{
                borderLeft: `4px solid var(--state-${c.level === 'BLOCK' ? 'check-rejected' : c.level === 'WARN' ? 'stale' : 'info'}, transparent)`,
              }}
              title={
                <Space>
                  <Tag color={LEVEL_COLOR[c.level]} data-testid="conflict-level">
                    {c.level}
                  </Tag>
                  <Typography.Text strong>
                    {c.field_label ?? c.field}
                  </Typography.Text>
                  <Typography.Text type="secondary">
                    {LEVEL_LABEL[c.level]}
                  </Typography.Text>
                </Space>
              }
            >
              <Space direction="vertical" size={4}>
                <div data-testid="conflict-user">
                  <Typography.Text type="secondary">用户输入：</Typography.Text>
                  <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>
                    {c.user_value} {c.user_unit ?? ''}
                  </span>
                </div>
                <div data-testid="conflict-calc">
                  <Typography.Text type="secondary">计算值：</Typography.Text>
                  <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>
                    {c.calc_value} {c.calc_unit ?? c.user_unit ?? ''}
                  </span>
                </div>
                {c.deviation_pct && (
                  <div data-testid="conflict-deviation">
                    <Typography.Text type="secondary">偏差：</Typography.Text>
                    <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>
                      {c.deviation_pct}
                    </span>
                  </div>
                )}
                <div data-testid="conflict-priority-hint">
                  <Typography.Text type="secondary">
                    字段优先级：{priority === 'USER' ? '用户值' : '计算值'}优先
                  </Typography.Text>
                </div>
              </Space>
              <Space style={{ marginTop: 12 }}>
                <Button
                  type={priority === 'USER' ? 'primary' : 'default'}
                  data-testid="choose-user"
                  data-field={c.field}
                  onClick={() => onResolve?.(c.field, 'USER')}
                >
                  采用用户值
                </Button>
                <Button
                  type={priority === 'CALC' ? 'primary' : 'default'}
                  data-testid="choose-calc"
                  data-field={c.field}
                  onClick={() => onResolve?.(c.field, 'CALC')}
                >
                  采用计算值
                </Button>
              </Space>
            </Card>
          );
        })}
      </Space>
    </div>
  );
}

export default ConflictResolver;