/**
 * 物流手动创建向导测试（SPEC §7.7.3「手工」分支 · P9B-3 · T7）。
 *
 * 守五件事：
 * 1. 向导是**多步**（基本信息 / 组成 / 状态点 / 校验 / 写入 DRAFT / 物性估算 /
 *    提交校对），不是一行表单
 * 2. 「校验」步调 `POST /streams/validate` ⇒ 通过项绿 / 警告项黄 / 错误项红
 * 3. ⚠️ **校验有红项 ⇒ 「写入 DRAFT」按钮禁用**（阻断项必须处理）
 * 4. 「写入 DRAFT」⇒ `POST /streams` ⇒ 成功 ⇒ 跳回列表；失败 ⇒ 显示错误
 * 5. ⚠️ **物性估算失败 ⇒ 提示 + 仍可继续提交校对**（估算**不阻塞**提交）
 *
 * ⚠️ 步骤顺序按 SPEC §7.7.3 的「手工」分支：**校验 → 写入 → 估算 → 提交**
 * （估算排在写入之后 —— 估算要 `stream_id`；且估算失败**不阻塞**提交校对）。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter, useLocation } from 'react-router-dom';

import { StreamManualWizardPage } from '../../../src/pages/sim/StreamManualWizardPage';
import type { components } from '../../../src/types/api';

type ValidateStreamResponse = components['schemas']['ValidateStreamResponse'];

const PROJECT_ID = '00000000-0000-0000-0000-000000000001';

let validateCalls = 0;
let createCalls = 0;
let estimateCalls = 0;
let submitCalls = 0;
/** 校验返回的三色结果（blocks=红 / warnings=黄 / infos=绿）。 */
let validateResult: ValidateStreamResponse = {
  valid: true,
  blocks: [],
  warnings: [],
  infos: [],
  stats: {},
};
/** 写入是否失败（500）。 */
let createFails = false;
/** 物性估算是否失败（500）。 */
let estimateFails = false;

const server = setupServer(
  http.post('/api/v1/projects/:project_id/streams/validate', async ({ request }) => {
    validateCalls += 1;
    await request.json();
    return HttpResponse.json(validateResult);
  }),
  http.post('/api/v1/projects/:project_id/streams', async ({ request }) => {
    createCalls += 1;
    await request.json();
    if (createFails) {
      return HttpResponse.json(
        { code: 'INTERNAL_ERROR', message: '写入失败', detail: null, trace_id: 't-500' },
        { status: 500 },
      );
    }
    return HttpResponse.json(
      {
        stream_id: 's-new',
        stream_name: '新物流',
        case_type: 'NORMAL',
        data_mode: 'CHEMICAL',
        source_type: 'MANUAL_ENTRY',
        source: 'MANUAL',
        sign_status: 'DRAFT',
        approval_depth: 1,
        record_hash: 'abc123',
        created_at: '2026-11-03 10:00',
      },
      { status: 201 },
    );
  }),
  http.post('/api/v1/streams/:stream_id/properties/estimate', async ({ request }) => {
    estimateCalls += 1;
    await request.json();
    if (estimateFails) {
      return HttpResponse.json(
        { code: 'PROPERTY_ESTIMATE_FAILED', message: '估算失败', detail: null, trace_id: 't-e' },
        { status: 500 },
      );
    }
    return HttpResponse.json({ estimated: 1 });
  }),
  http.post('/api/v1/streams/:stream_id/submit', () => {
    submitCalls += 1;
    // ⚠️ 提交校对**没有请求体** ⇒ 不能 `request.json()`（空 body 会抛）
    return HttpResponse.json({ stream_id: 's-new', sign_status: 'IN_APPROVAL' });
  }),
  http.post('/api/v1/streams/:stream_id/state-points', async ({ request }) => {
    await request.json();
    return HttpResponse.json({ state_point_id: 'sp-1' }, { status: 201 });
  }),
);

/** 记录当前路由（验证「写入成功 ⇒ 跳回列表」）。 */
function LocationSpy(): JSX.Element {
  const loc = useLocation();
  return <div data-testid="location-path">{loc.pathname}</div>;
}

function renderWizard() {
  return render(
    <MemoryRouter initialEntries={['/sim/streams/new']}>
      <StreamManualWizardPage projectId={PROJECT_ID} />
      <LocationSpy />
    </MemoryRouter>,
  );
}

/**
 * 点「下一步」直到到达目标步（0 基）。
 *
 * ⚠️ **记住当前步** —— 同一个用例里可能连着调两次（校验 → 写入）⇒ 不能
 * 每次都从 0 开始等（否则第二次会等一个**已经过去**的步 ⇒ 永远等不到）。
 */
let currentStep = 0;
async function gotoStep(target: number): Promise<void> {
  while (currentStep < target) {
    fireEvent.click(screen.getByTestId('wizard-next'));
    currentStep += 1;
    await waitFor(() =>
      expect(screen.getByTestId(`wizard-step-${currentStep}`)).toBeTruthy(),
    );
  }
}

describe('StreamManualWizardPage —— 物流手动创建向导（T7）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    validateCalls = 0;
    createCalls = 0;
    estimateCalls = 0;
    submitCalls = 0;
    validateResult = { valid: true, blocks: [], warnings: [], infos: [], stats: {} };
    createFails = false;
    estimateFails = false;
    currentStep = 0;
  });

  it('是**多步**向导：7 个步骤都摆出来（不是一行表单）', async () => {
    renderWizard();
    await waitFor(() => expect(screen.getByTestId('wizard-steps')).toBeTruthy());

    const steps = screen.getByTestId('wizard-steps').textContent ?? '';
    for (const title of ['基本信息', '组成', '状态点', '校验', '写入 DRAFT', '物性估算', '提交校对']) {
      expect(steps).toContain(title);
    }
    // ⚠️ 当前只渲染**当前步**的面板（多步，不是长表单）
    expect(screen.getByTestId('wizard-step-0')).toBeTruthy();
    expect(screen.queryByTestId('wizard-step-3')).toBeNull();
  });

  it('「校验」步调 validate ⇒ 通过项绿 / 警告项黄 / 错误项红', async () => {
    validateResult = {
      valid: false,
      blocks: [{ code: 'SIM-V01', message: '缺相态', field: 'phase' }],
      warnings: [{ code: 'SIM-W02', message: '温度偏高' }],
      infos: [{ code: 'SIM-I03', message: '建议补描述' }],
      stats: { BLOCK: 1, WARN: 1, INFO: 1, TOTAL: 3 },
    };
    renderWizard();
    await gotoStep(3);

    fireEvent.click(screen.getByTestId('wizard-validate'));
    await waitFor(() => expect(validateCalls).toBe(1));

    expect(screen.getByTestId('wizard-block-0').textContent).toContain('缺相态');
    expect(screen.getByTestId('wizard-warning-0').textContent).toContain('温度偏高');
    expect(screen.getByTestId('wizard-info-0').textContent).toContain('建议补描述');
    // 三色：红 / 黄 / 绿
    expect(screen.getByTestId('wizard-block-0').getAttribute('data-level')).toBe('error');
    expect(screen.getByTestId('wizard-warning-0').getAttribute('data-level')).toBe('warning');
    expect(screen.getByTestId('wizard-info-0').getAttribute('data-level')).toBe('info');
  });

  it('⚠️ 校验有红项 ⇒ 「写入 DRAFT」按钮**禁用**', async () => {
    validateResult = {
      valid: false,
      blocks: [{ code: 'SIM-V01', message: '缺相态' }],
      warnings: [],
      infos: [],
      stats: { BLOCK: 1 },
    };
    renderWizard();
    await gotoStep(3);
    fireEvent.click(screen.getByTestId('wizard-validate'));
    await waitFor(() => expect(validateCalls).toBe(1));

    await gotoStep(4);
    const writeBtn = screen.getByTestId('wizard-write') as HTMLButtonElement;
    expect(writeBtn.disabled).toBe(true);
  });

  it('「写入 DRAFT」⇒ POST streams ⇒ 成功 ⇒ 显示已写入（**不**跳走）', async () => {
    // ⚠️ 写入后**留在向导**（后面还有「物性估算」「提交校对」两步）⇒
    //    跳回列表发生在**提交校对**成功之后。
    renderWizard();
    await gotoStep(4);

    fireEvent.click(screen.getByTestId('wizard-write'));
    await waitFor(() => expect(createCalls).toBe(1));
    expect(screen.getByTestId('wizard-write-result').textContent).toContain('s-new');
    expect(screen.getByTestId('location-path').textContent).toBe('/sim/streams/new');
  });

  it('写入失败（500）⇒ 显示错误（**不**跳走）', async () => {
    createFails = true;
    renderWizard();
    await gotoStep(4);

    fireEvent.click(screen.getByTestId('wizard-write'));
    await waitFor(() => expect(screen.getByTestId('wizard-error')).toBeTruthy());
    expect(screen.getByTestId('wizard-error').textContent).toContain('INTERNAL_ERROR');
    expect(screen.getByTestId('location-path').textContent).toBe('/sim/streams/new');
  });

  it('提交校对成功 ⇒ 跳回列表', async () => {
    renderWizard();
    await gotoStep(4);
    fireEvent.click(screen.getByTestId('wizard-write'));
    await waitFor(() => expect(createCalls).toBe(1));

    await gotoStep(6);
    fireEvent.click(screen.getByTestId('wizard-submit'));
    await waitFor(() => expect(submitCalls).toBe(1));
    await waitFor(() => expect(screen.getByTestId('location-path').textContent).toBe('/sim/streams'));
  });

  it('⚠️ 物性估算失败 ⇒ 提示 + **仍可继续提交校对**', async () => {
    estimateFails = true;
    renderWizard();
    await gotoStep(4);
    fireEvent.click(screen.getByTestId('wizard-write'));
    await waitFor(() => expect(createCalls).toBe(1));

    await gotoStep(5);
    fireEvent.click(screen.getByTestId('wizard-estimate'));
    await waitFor(() => expect(estimateCalls).toBe(1));
    // ⚠️ 失败要**提示**，但**不阻塞**后面的提交校对
    expect(screen.getByTestId('wizard-estimate-warning')).toBeTruthy();

    await gotoStep(6);
    fireEvent.click(screen.getByTestId('wizard-submit'));
    await waitFor(() => expect(submitCalls).toBe(1));
    await waitFor(() => expect(screen.getByTestId('location-path').textContent).toBe('/sim/streams'));
  });
});
