/**
 * HEAT API 客户端测试（P5-4 frontend / Task 2）。
 *
 * 真实测试断言（≥1 真测试 / Task 2）：
 * 1. heatApi.importHtri 调用 axios 时未显式声明 Content-Type —— 避免 multipart
 *    boundary 缺失导致后端解析失败（422 HEAT_INPUT_ERROR）。
 * 2. heatApi.importHtri 正确序列化 FormData 字段顺序与 backend Form 字段对齐。
 * 3. heatApi.get / estimateWeight 路径模板正确。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// 拦截 axios instance
vi.mock('../../src/api/client', async () => {
  const actual = await vi.importActual<typeof import('../../src/api/client')>(
    '../../src/api/client',
  );
  return {
    ...actual,
    api: {
      post: vi.fn().mockResolvedValue({ data: { stub: true } }),
      get: vi.fn().mockResolvedValue({ data: { stub: true } }),
    },
  };
});

import { api } from '../../src/api/client';
import { heatApi } from '../../src/api/heat';

describe('heatApi.importHtri (multipart upload)', () => {
  beforeEach(() => {
    vi.mocked(api.post).mockClear();
  });

  it('does NOT explicitly set Content-Type header (let browser add boundary)', async () => {
    const file = new File(['htri-content'], 'htri.txt', { type: 'text/plain' });
    await heatApi.importHtri({
      file,
      project_id: '00000000-0000-0000-0000-000000000001',
      workspace_id: '00000000-0000-0000-0000-000000000002',
      equipment_no: 'E-201',
      tag_number: 'E-201',
      exchanger_category: 'SHELL_TUBE',
    });

    // 仅断言 axios.post 被调 1 次
    expect(api.post).toHaveBeenCalledTimes(1);

    // 关键断言：传 FormData 时不传 Content-Type header（让浏览器/axios 自动加 boundary）
    // 第 3 个参数（AxiosRequestConfig）的 headers 字段为 undefined 或不包含 Content-Type
    const callArgs = vi.mocked(api.post).mock.calls[0];
    const config = callArgs[2] as { headers?: Record<string, string> } | undefined;
    // 未来 heatApi 增加 config 参数时本断言需更新
    expect(config?.headers?.['Content-Type']).toBeUndefined();
  });

  it('serializes FormData with all required fields including optional ones when provided', async () => {
    const file = new File(['htri'], 'htri.txt', { type: 'text/plain' });
    await heatApi.importHtri({
      file,
      project_id: 'p1',
      workspace_id: 'w1',
      equipment_no: 'E-201',
      tag_number: 'E-201',
      exchanger_category: 'SHELL_TUBE',
      equipment_name: 'HEAT-E-201',
      source_stream_id: 's1',
    });

    const formData = vi.mocked(api.post).mock.calls[0][1] as FormData;
    // FormData 字段对齐后端 Form schema
    expect(formData.get('file')).toBe(file);
    expect(formData.get('project_id')).toBe('p1');
    expect(formData.get('workspace_id')).toBe('w1');
    expect(formData.get('equipment_no')).toBe('E-201');
    expect(formData.get('tag_number')).toBe('E-201');
    expect(formData.get('exchanger_category')).toBe('SHELL_TUBE');
    expect(formData.get('equipment_name')).toBe('HEAT-E-201');
    expect(formData.get('source_stream_id')).toBe('s1');
  });
});

describe('heatApi.get / heatApi.estimateWeight', () => {
  beforeEach(() => {
    vi.mocked(api.post).mockClear();
    vi.mocked(api.get).mockClear();
  });

  it('heatApi.get uses correct path template', async () => {
    await heatApi.get('heat-uuid-1');
    expect(api.get).toHaveBeenCalledWith('/heat/heat-uuid-1');
  });

  it('heatApi.estimateWeight posts to correct path with payload', async () => {
    await heatApi.estimateWeight('heat-uuid-2', {
      tema_type: 'BEM',
      shell_id_m: 1.0,
      shell_length_m: 5.0,
      shell_thickness_m: 0.012,
    });
    expect(api.post).toHaveBeenCalledWith(
      '/heat/heat-uuid-2/weight-estimate',
      {
        tema_type: 'BEM',
        shell_id_m: 1.0,
        shell_length_m: 5.0,
        shell_thickness_m: 0.012,
      },
    );
  });
});