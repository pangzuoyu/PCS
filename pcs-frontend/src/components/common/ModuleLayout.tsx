/**
 * ModuleLayout — 计算模块统一布局（P45-3-0 / Task 27）。
 *
 * SPEC §7.12 P5/P6 设备计算统一布局：
 *   PageHeader
 *   ├── 输入表单（input slot）
 *   ├── 计算按钮
 *   ├── 结果卡片区（result slot）
 *   ├── 血缘 / 同步设备表（lineage + syncDevices slot）
 *
 * Props：
 *   input: ReactNode                       // 必填（SchemaForm 等）
 *   result: ReactNode                      // 必填
 *   lineage?: ReactNode                    // 可选：LineageGraph
 *   syncDevices?: ReactNode                // 可选：同步设备表
 */
import type { ReactNode } from 'react';
import { Col, Row } from 'antd';

interface Props {
  input: ReactNode;
  result: ReactNode;
  lineage?: ReactNode;
  syncDevices?: ReactNode;
}

export function ModuleLayout({ input, result, lineage, syncDevices }: Props): JSX.Element {
  const hasLower = !!lineage || !!syncDevices;
  const lowerSpan = lineage && syncDevices ? 12 : 24;

  return (
    <div data-testid="module-layout" data-has-lower={String(hasLower)}>
      <Row gutter={[16, 16]}>
        <Col span={12} data-testid="module-layout-input">
          {input}
        </Col>
        <Col span={12} data-testid="module-layout-result">
          {result}
        </Col>
      </Row>
      {hasLower && (
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          {lineage && (
            <Col span={lowerSpan} data-testid="module-layout-lineage">
              {lineage}
            </Col>
          )}
          {syncDevices && (
            <Col span={lowerSpan} data-testid="module-layout-sync">
              {syncDevices}
            </Col>
          )}
        </Row>
      )}
    </div>
  );
}

export default ModuleLayout;