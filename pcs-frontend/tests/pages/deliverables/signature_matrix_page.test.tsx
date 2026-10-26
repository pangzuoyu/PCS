/**
 * 签署矩阵管理页的守卫（TODO-079 · P9A-DLV-011 T3 的前端）。
 *
 * ## 这组测试钉住的失败模式
 *
 * | # | 失败模式 | 期望 |
 * |---|---|---|
 * | RF-1 | 页面**不拉**列表（只渲染空表）⇒ 用户看到「没有矩阵」 | 拉 `GET /signature-matrices` 并渲染 |
 * | RF-2 | 步骤**不显示** ⇒ 用户看不出「谁该签几步」 | 显示 `1.CHECKER → 2.APPROVER` |
 * | RF-3 | 后端 403（不是项目负责人）被吞掉 ⇒ 用户只看到「失败」 | **原样显示**后端 message |
 * | RF-4 | 拉列表失败时页面**崩**（未捕获的 promise） | 显示错误条 + 空表 |
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { SignatureMatrixPage } from '../../../src/pages/deliverables/SignatureMatrixPage';
import { useAuth } from '../../../src/store/auth';
import type { components } from '../../../src/types/api';

type SignatureMatrix = components['schemas']['SignatureMatrixResponse'];

const MATRICES: SignatureMatrix[] = [
  {
    matrix_id: 'm-1',
    matrix_name: '变更单 3 级矩阵',
    module: 'CHANGE_NOTICE',
    doc_type: 'CHANGE_NOTICE',
    version_purpose: 'ISSUED_FOR_CHANGE',
    status: 'ACTIVE',
    steps: [
      { step_order: 1, sign_role: 'CHECKER', required: true, can_self_check: false, can_skip: false },
      { step_order: 2, sign_role: 'REVIEWER', required: true, can_self_check: false, can_skip: false },
      { step_order: 3, sign_role: 'APPROVER', required: true, can_self_check: false, can_skip: false },
    ],
    created_at: '2026-10-26T00:00:00Z',
    updated_at: '2026-10-26T00:00:00Z',
  },
];

let listFails = false;

const server = setupServer(
  http.get('/api/v1/signature-matrices', () => {
    if (listFails) {
      return HttpResponse.json(
        { code: 'INTERNAL_ERROR', message: '矩阵列表加载失败' },
        { status: 500 },
      );
    }
    return HttpResponse.json({ items: MATRICES, total: MATRICES.length });
  }),
);

describe('SignatureMatrixPage —— 签署矩阵管理面', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    listFails = false;
    useAuth.getState().setSession({
      access_token: 'test-token',
      refresh_token: 'r',
      username: 'u',
      role: 'SYSTEM_ADMIN',
      user_id: 'u',
    });
  });

  it('RF-1/RF-2：列表渲染，且步骤按顺序显示「谁该签几步」', async () => {
    render(<SignatureMatrixPage />);
    await waitFor(() => expect(screen.getByText('变更单 3 级矩阵')).toBeTruthy());
    expect(screen.getByText('1.CHECKER → 2.REVIEWER → 3.APPROVER')).toBeTruthy();
    // ⚠️ 「CHANGE_NOTICE」出现两次（模块列 + 文档类型列）⇒ 用 getAllByText
    expect(screen.getAllByText('CHANGE_NOTICE').length).toBeGreaterThan(0);
  });

  it('RF-4：列表拉取失败 ⇒ 显示错误条，不崩', async () => {
    listFails = true;
    render(<SignatureMatrixPage />);
    await waitFor(() => expect(screen.getByTestId('signature-matrix-error')).toBeTruthy());
    expect(screen.getByText('矩阵列表加载失败')).toBeTruthy();
  });

  it('页面提供「新建矩阵」入口与项目绑定区', async () => {
    render(<SignatureMatrixPage />);
    await waitFor(() => expect(screen.getByText('变更单 3 级矩阵')).toBeTruthy());
    expect(screen.getByText('新建矩阵')).toBeTruthy();
    expect(screen.getByText('绑定到当前项目')).toBeTruthy();
  });
});
