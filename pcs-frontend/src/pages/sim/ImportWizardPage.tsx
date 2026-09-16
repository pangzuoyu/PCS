/**
 * ImportWizardPage — SIM 物流导入向导（P45-3-1 / Task 28 极简版）。
 *
 * SPEC §7.7.3：
 * - 4 步骤：上传 → 字段映射 → 预览 → 确认
 * - 每步可前进/后退/跳过/确认
 *
 * Props：
 *   onConfirm?: () => void   // 最后一步确认导入
 *
 * 注：本任务 V1 极简版仅实现步骤导航 + UI 占位；真实 Excel 解析 / 字段映射规则
 * 由后端 SIM-37b parser 链路负责，前端仅 UI 骨架。
 */
import { useState } from 'react';
import { Button, Empty, Space, Steps, Typography, Upload } from 'antd';
import { InboxOutlined } from '@ant-design/icons';

const { Dragger } = Upload;

interface Props {
  onConfirm?: () => void;
}

const STEP_ITEMS = [
  { title: '上传', description: '上传 Excel / CSV' },
  { title: '字段映射', description: '映射到 SIM 字段' },
  { title: '预览', description: '预览待导入数据' },
  { title: '确认', description: '确认导入' },
];

export function ImportWizardPage({ onConfirm }: Props): JSX.Element {
  const [step, setStep] = useState(0);

  return (
    <div data-testid="import-wizard-page">
      <Typography.Title level={3}>SIM 物流导入向导</Typography.Title>

      <Steps
        data-testid="import-wizard-steps"
        current={step}
        items={STEP_ITEMS.map((s, i) => ({
          title: s.title,
          description: s.description,
          key: i,
        }))}
      />

      <div style={{ marginTop: 24, minHeight: 240 }}>
        {step === 0 && (
          <div data-testid="import-wizard-step-upload">
            <Dragger multiple={false} beforeUpload={() => false}>
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p>点击或拖拽文件到此区域上传（仅 Excel / CSV）</p>
            </Dragger>
          </div>
        )}
        {step === 1 && (
          <div data-testid="import-wizard-step-mapping">
            <Empty description="字段映射 UI 占位（V1：上传即自动映射；自定义映射规则留 P5）" />
          </div>
        )}
        {step === 2 && (
          <div data-testid="import-wizard-step-preview">
            <Empty description="预览 UI 占位（V1：后端 preview 端点未就绪）" />
          </div>
        )}
        {step === 3 && (
          <div data-testid="import-wizard-step-confirm">
            <Empty description="确认后导入，失败行将进入冲突队列（ConflictResolver 占位）" />
          </div>
        )}
      </div>

      <Space style={{ marginTop: 16 }}>
        <Button
          data-testid="import-wizard-prev"
          disabled={step === 0}
          onClick={() => setStep((s) => Math.max(0, s - 1))}
        >
          上一步
        </Button>
        {step < STEP_ITEMS.length - 1 ? (
          <Button
            type="primary"
            data-testid="import-wizard-next"
            onClick={() => setStep((s) => Math.min(STEP_ITEMS.length - 1, s + 1))}
          >
            下一步
          </Button>
        ) : (
          <Button
            type="primary"
            data-testid="import-wizard-confirm"
            onClick={() => onConfirm?.()}
          >
            确认导入
          </Button>
        )}
      </Space>
    </div>
  );
}

export default ImportWizardPage;