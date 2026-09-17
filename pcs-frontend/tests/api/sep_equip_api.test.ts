/**sepEquipApi 真跑测试（P5 frontend 全栈收口 / OPEN-4-2）。*/
import { describe, it, expect } from 'vitest';

import { sepEquipApi } from '../../src/api/sepEquip';

describe('sepEquipApi (P5 frontend / OPEN-4-2)', () => {
  it('导出 calculate 方法', () => {
    expect(typeof sepEquipApi.calculate).toBe('function');
  });
});