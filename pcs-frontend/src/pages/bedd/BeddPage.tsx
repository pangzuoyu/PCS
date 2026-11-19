/**
 * BeddPage — BEDD 文档（P45-3-8 / Task 35）。
 *
 * SPEC §7.5.2：
 * - 章节列表（左侧）+ 内容预览（右侧）
 * - 签名行（step_index + signer + signed_at）
 */
import { useState } from 'react';
import { Alert, Card, Col, Descriptions, Empty, List, Row, Space, Tag, Typography } from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import { StateBadge } from '../../components/common/StateBadge';
import type { BeddSection } from '../../types/pms';

interface Props {
  sections: BeddSection[];
}

export function BeddPage({ sections }: Props): JSX.Element {
  const [active, setActive] = useState<string | null>(sections[0]?.section_id ?? null);
  const current = sections.find((s) => s.section_id === active);

  return (
    <div data-testid="bedd-page">
      <PageHeader title="BEDD 文档" module="CONFIG" actions={null as unknown as undefined} />

      {/* ⚠️ **占位说明（P10-C · T2 · TODO-159）** —— 这不是「没有数据」，
       *     是「**数据源还不存在**」。
       *
       * 此前本页调 `GET /projects/{id}/bedd` ⇒ ⇒ **契约里没有这个端点**
       * ⇒ ⇒ 真后端 404（mock 通道有 handler ⇒ 一路绿灯 ⇒ 只有真后端抓得到）。
       *
       * ⚠️ **为什么不给 `projects.bedd_json` 补一个读端点**：那一列**存在**
       * （`projects.bedd_json` JSONB）⇒ ⇒ 但全仓**没有任何写入路径**
       * （只有建表迁移提到它）⇒ ⇒ 补出来的端点**永远返回空**
       * ⇒ ⇒ 「看起来有、其实永远空」的端点比没有更坏 ⇒ ⇒ 不补。
       *
       * ⚠️ SPEC §7.5 的 BEDD 是**项目创建向导的第 3 步（BEDD 录入）**
       * +「分组 Tab 编辑」⇒ ⇒ 与本页的「章节列表」不是同一件事。
       */}
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        data-testid="bedd-not-wired"
        message="BEDD 数据源尚未接入"
        description="projects.bedd_json 这一列目前没有任何写入路径（只有建表迁移提到它）⇒ 无数据可读 ⇒ 本页暂为占位。SPEC §7.5 的 BEDD 是「项目创建向导」的第 3 步（BEDD 录入），与本页不是同一件事。"
      />

      <Row gutter={16}>
        <Col span={8}>
          <Card title={`章节 (${sections.length})`} size="small">
            {sections.length === 0 ? (
              <Empty description="无章节" />
            ) : (
              <List
                data-testid="bedd-section-list"
                dataSource={sections.map((s) => ({ ...s, idx: s.section_id }))}
                renderItem={(item) => (
                  <List.Item
                    data-testid="bedd-section-item"
                    data-section-id={item.section_id}
                    onClick={() => setActive(item.section_id)}
                    style={{ cursor: 'pointer' }}
                  >
                    <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                      <span style={{ fontWeight: item.section_id === active ? 600 : 400 }}>
                        {item.title}
                      </span>
                      <StateBadge status={item.sign_status} module="CONFIG" />
                    </Space>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>

        <Col span={16}>
          <Card title={current?.title ?? '请选择章节'} size="small" data-testid="bedd-content">
            {!current ? (
              <Empty description="请选择左侧章节" />
            ) : (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Typography.Paragraph>{current.content}</Typography.Paragraph>

                <Card size="small" title="签名" data-testid="bedd-signatures">
                  {!current.signatures || current.signatures.length === 0 ? (
                    <Typography.Text type="secondary">暂无签名</Typography.Text>
                  ) : (
                    <Descriptions size="small">
                          {current.signatures.map((sig) => (
                            <Descriptions.Item
                              key={sig.step_index}
                              label={
                                <Space>
                                  <Tag color="blue">Step {sig.step_index}</Tag>
                                </Space>
                              }
                            >
                              {sig.signer} · {sig.signed_at}
                            </Descriptions.Item>
                          ))}
                        </Descriptions>
                  )}
                </Card>
              </Space>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default BeddPage;