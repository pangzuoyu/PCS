/**
 * BeddPage — BEDD 文档（P45-3-8 / Task 35）。
 *
 * SPEC §7.5.2：
 * - 章节列表（左侧）+ 内容预览（右侧）
 * - 签名行（step_index + signer + signed_at）
 */
import { useState } from 'react';
import { Card, Col, Descriptions, Empty, List, Row, Space, Tag, Typography } from 'antd';

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