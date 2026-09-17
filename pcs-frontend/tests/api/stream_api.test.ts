/**
 * streamApi 真跑测试（P5 frontend 全栈收口 / OPEN-6）。
 *
 * 覆盖：
 * 1. listByProject 路径正确（/projects/{projectId}/streams）
 * 2. 响应 StreamListItem[] 直接 resolve（不包 envelope）
 */
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

import { streamApi } from '../../src/api/stream';

const PROJECT = '00000000-0000-0000-0000-000000000001';

const seedStreams = [
  {
    stream_id: 's-101',
    tag_number: 'S-101',
    stream_name: '进料物流',
    phase: 'LIQUID',
    subphase: 'SUBCOOLED',
  },
  {
    stream_id: 's-102',
    tag_number: 'S-102',
    stream_name: '塔顶蒸汽',
    phase: 'VAPOR',
    subphase: 'SAT_VAPOR',
  },
];

// axios baseURL = '/api/v1' → 相对路径，由 MSW 拦截
const server = setupServer(
  http.get(`/api/v1/projects/${PROJECT}/streams`, () => HttpResponse.json(seedStreams)),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('streamApi (P5 frontend / OPEN-6)', () => {
  it('listByProject 命中 /projects/{projectId}/streams', async () => {
    const list = await streamApi.listByProject(PROJECT);
    expect(Array.isArray(list)).toBe(true);
    expect(list).toHaveLength(2);
    expect(list[0].stream_id).toBe('s-101');
    expect(list[0].tag_number).toBe('S-101');
    expect(list[1].phase).toBe('VAPOR');
  });
});
