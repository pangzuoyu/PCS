/**
 * api/errors —— 共享错误格式化器（评审 #7：errorText 统一到 api 层后需直测）。
 */
import { describe, it, expect } from 'vitest';

import { errorText, describePcsError } from '../../src/api/errors';

const envelopeErr = {
  response: { data: { code: 'SIGN_STEP_ROLE_MISMATCH', message: '第 1 步要求角色 CHECKER' } },
};
const bareErr = { response: { data: { message: '纯消息无码' } } };
const networkErr = new Error('boom');

describe('errorText（信封原文，前端不自造文案）', () => {
  it('有 code ⇒ `code：message`（全角冒号）', () => {
    expect(errorText(envelopeErr, '兜底')).toBe(
      'SIGN_STEP_ROLE_MISMATCH：第 1 步要求角色 CHECKER',
    );
  });
  it('无 code ⇒ 只回 message', () => {
    expect(errorText(bareErr, '兜底')).toBe('纯消息无码');
  });
  it('非信封错误（网络/未知）⇒ **纯 fallback**，不编造 HTTP_500 前缀', () => {
    // ⚠️ 这正是它与 describePcsError 的分工：兜底文案要给人读，不是给日志读
    expect(errorText(networkErr, '无法读取交付物')).toBe('无法读取交付物');
  });
  it('describePcsError 语义不变（非信封 ⇒ HTTP_500 前缀）—— 防两头漂移', () => {
    expect(describePcsError(networkErr, '兜底')).toBe('HTTP_500：兜底');
  });
});
