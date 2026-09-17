/**vesselApi 真跑测试（P5 frontend全栈收口 / OPEN-4-1）。*/
import { describe, it, expect } from 'vitest';

import { vesselApi } from '../../src/api/vessel';

describe('vesselApi (P5 frontend / OPEN-4-1)', () => {
  it('导出 calculate 方法', () => {
    expect(typeof vesselApi.calculate).toBe('function');
  });
});
