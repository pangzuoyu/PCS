/**
 * JOIN 白名单选择器（b6 第二批）。
 *
 * ## 为什么只列「两端都已被选中」的
 *
 * 列了别的，执行时才撞 `REPORT_BUILDER_JOIN_NOT_SUPPORTED`（400）——
 * 用户填完整个报表才被拒。b1 把白名单随字段树一起下发、要解决的
 * 正是这个（「选得了就跑得了」），所以选项必须跟着已选数据源实时收窄。
 *
 * ⚠️ **不按名称猜关联**。SPEC §1.3 明确禁止名称模糊 JOIN；关联键
 * 逐字来自后端注册表（`a_field` / `b_field`），前端不推断。
 */
import type { JSX } from 'react';
import { Alert, Checkbox, Space, Tooltip, Typography } from 'antd';

import { availableJoins, pairKey } from './definitionBody';
import type { JoinWhitelistEntry } from './definitionBody';

interface Props {
  /** 已选数据源（由字段表的行推导） */
  selectedSources: string[];
  /** 后端下发的**白名单**（全量） */
  whitelist: JoinWhitelistEntry[];
  /** 用户**已启用**的关联（白名单的子集，用 `pairKey` 标识） */
  active: string[];
  onChange: (next: string[]) => void;
  labelOf: (sourceKey: string) => string;
}

export function JoinPicker(props: Props): JSX.Element {
  const { selectedSources, whitelist, active, onChange, labelOf } = props;

  if (whitelist.length === 0) {
    return <Typography.Text type="secondary">
      后端未下发 JOIN 白名单 —— 按 SPEC §1.3 这意味着不支持任何关联。
    </Typography.Text>;
  }

  const offerable = availableJoins(
    selectedSources.map((source) => ({ source })), whitelist);

  if (offerable.length === 0) {
    return <Typography.Text type="secondary">
      同时勾选两个数据源后，这里会列出可用的关联。
      （白名单共 {whitelist.length} 对）
    </Typography.Text>;
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={6}>
      {offerable.map((j) => {
        const key = pairKey(j.a, j.b);
        return (
          <Space key={key} wrap>
            <Checkbox
              checked={active.includes(key)}
              onChange={(e) => onChange(
                e.target.checked
                  ? [...active, key]
                  : active.filter((k) => k !== key))}
            >
              {labelOf(j.a)} ↔ {labelOf(j.b)}
            </Checkbox>
            <Typography.Text type="secondary">
              ({j.a_field} = {j.b_field})
            </Typography.Text>
            {j.degrade_warn && (
              <Tooltip title={j.degrade_warn}>
                {/* ⚠️ 降级关联必须显式告知：关联键不是设计意图里的那个，
                    结果可能看着「对」但其实少了一部分行。 */}
                <Alert type="warning" showIcon style={{ padding: '0 8px' }}
                  message="降级关联" />
              </Tooltip>
            )}
          </Space>
        );
      })}
    </Space>
  );
}
