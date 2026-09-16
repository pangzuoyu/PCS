/**
 * ProjectWizardPage — 项目向导（P45-3-8 / Task 35）。
 *
 * SPEC §7.5.3：
 * - 步骤序列（创建项目 → PMS → BEDD → 设备库 → 计算模块 → 收口）
 * - 每步：title / description / done 状态
 * - 前进 / 后退 / 标记完成
 */
import { useState } from 'react';
import { Button, Card, Checkbox, Empty, Space, Steps, Typography } from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import type { WizardStep } from '../../types/pms';

interface Props {
  initialSteps: WizardStep[];
  initialProjectName?: string;
  onStepDone?: (idx: number, done: boolean) => void;
  onFinish?: (projectName: string) => void;
}

export function ProjectWizardPage({
  initialSteps,
  initialProjectName = '',
  onStepDone,
  onFinish,
}: Props): JSX.Element {
  const [steps, setSteps] = useState(initialSteps);
  const [current, setCurrent] = useState(0);
  const [projectName, setProjectName] = useState(initialProjectName);
  const step = steps[current];

  const toggleDone = (idx: number, done: boolean) => {
    setSteps((prev) => prev.map((s, i) => (i === idx ? { ...s, done } : s)));
    onStepDone?.(idx, done);
  };

  const handleFinish = () => {
    onFinish?.(projectName);
  };

  return (
    <div data-testid="project-wizard-page">
      <PageHeader title="新建项目向导" module="CONFIG" actions={null as unknown as undefined} />

      <Card size="small" style={{ marginBottom: 16 }}>
        <Steps
          data-testid="wizard-steps"
          current={current}
          items={steps.map((s, i) => ({ key: i, title: s.title, description: s.description }))}
          onChange={(k) => setCurrent(Number(k))}
        />
      </Card>

      <Card
        title={step ? `步骤 ${current + 1} / ${steps.length} · ${step.title}` : '项目'}
        size="small"
      >
        {!step ? (
          <Empty description="无步骤" />
        ) : (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            {current === 0 && (
              <div data-testid="wizard-step-project-name">
                <Typography.Text strong>项目名</Typography.Text>
                <input
                  data-testid="wizard-project-name-input"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="请输入项目名"
                  style={{ display: 'block', marginTop: 8, padding: 8, width: 320 }}
                />
              </div>
            )}

            <Checkbox
              data-testid="wizard-step-done"
              checked={step.done}
              onChange={(e) => toggleDone(current, e.target.checked)}
            >
              标记当前步骤完成
            </Checkbox>

            <Space>
              <Button
                data-testid="wizard-prev"
                disabled={current === 0}
                onClick={() => setCurrent((c) => Math.max(0, c - 1))}
              >
                上一步
              </Button>
              {current < steps.length - 1 ? (
                <Button
                  type="primary"
                  data-testid="wizard-next"
                  onClick={() => setCurrent((c) => Math.min(steps.length - 1, c + 1))}
                >
                  下一步
                </Button>
              ) : (
                <Button
                  type="primary"
                  data-testid="wizard-finish"
                  disabled={!steps.every((s) => s.done) || !projectName}
                  onClick={handleFinish}
                >
                  完成
                </Button>
              )}
            </Space>
          </Space>
        )}
      </Card>
    </div>
  );
}

export default ProjectWizardPage;