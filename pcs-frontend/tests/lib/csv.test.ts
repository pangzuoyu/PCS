/**
 * CSV 导出工具的**转义**规则（P9B-2 · T7 · RFC 4180）。
 *
 * ⚠️ **为什么值得单测**：审计日志的 `detail_json` 里什么都可能有 ——
 * 逗号、引号、**换行**。不转义的话导出的文件会被 Excel 拆成错列 / 破行
 * ⇒ 用户拿到的数据是**残缺的**，而他以为那是全部（RF-11）。
 */
import { describe, it, expect, vi } from 'vitest';

import { csvCell, csvRow, toCsv, downloadCsv } from '../../src/lib/csv';

describe('csvCell —— RFC 4180 转义', () => {
  it('普通值原样输出', () => {
    expect(csvCell('abc')).toBe('abc');
    expect(csvCell(123)).toBe('123');
  });

  it('⚠️ 含逗号 ⇒ 用双引号包起来', () => {
    expect(csvCell('a,b')).toBe('"a,b"');
  });

  it('⚠️ 含引号 ⇒ 加倍（`"` → `""`）并包起来', () => {
    expect(csvCell('say "hi"')).toBe('"say ""hi"""');
  });

  it('⚠️ 含**换行** ⇒ 用双引号包起来（**不破行**）', () => {
    expect(csvCell('line1\nline2')).toBe('"line1\nline2"');
    expect(csvCell('line1\r\nline2')).toBe('"line1\r\nline2"');
  });

  it('空值 ⇒ 空字段（不是 `null` 字面量）', () => {
    expect(csvCell(null)).toBe('');
    expect(csvCell(undefined)).toBe('');
  });

  it('⚠️ 公式注入面：`=`/`+`/`@` 开头 ⇒ 前置 `\'`（Excel 当文本）', () => {
    expect(csvCell('=1+1')).toBe("'=1+1");
    expect(csvCell('@SUM(A1)')).toBe("'@SUM(A1)");
  });

  it('⚠️ **tab / CR 开头**也是注入向量（Excel 会忽略前导 tab/CR）', () => {
    // ⚠️ Excel / LibreOffice **忽略前导的 tab / CR** ⇒ `\t=1+1` 照样被当公式
    //    求值 ⇒ 只挡 `=`/`+`/`-`/`@` 四个前缀**不够**。
    expect(csvCell('\t=1+1')).toBe("'\t=1+1");
    // ⚠️ CR 触发 RFC 4180 的**加引号**（CR 是必须加引号的字符）⇒ 输出带引号
    expect(csvCell('\r=1+1')).toBe('"\'\r=1+1"');
  });

  it('⚠️ **正常负数**不加 `\'`（否则数字被当文本）', () => {
    expect(csvCell(-1)).toBe('-1');
    expect(csvCell(-1.5)).toBe('-1.5');
  });
});

describe('downloadCsv —— 下载', () => {
  it('⚠️ `revokeObjectURL` **不在同一个 tick** 撤销（否则下载可能被打断）', async () => {
    // ⚠️ 浏览器**同步** revoke ⇒ 下载还没开始就把 URL 撤销了 ⇒ 文件下不来。
    const revoke = vi.fn();
    const create = vi.fn(() => 'blob:mock');
    const origCreate = URL.createObjectURL;
    const origRevoke = URL.revokeObjectURL;
    URL.createObjectURL = create as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = revoke as unknown as typeof URL.revokeObjectURL;
    try {
      downloadCsv('x.csv', 'a,b\r\n1,2');
      // ⚠️ **当场**不该撤销
      expect(revoke).not.toHaveBeenCalled();
      // ⚠️ 下一个 tick 之后才撤销
      await new Promise((r) => setTimeout(r, 0));
      expect(revoke).toHaveBeenCalledWith('blob:mock');
    } finally {
      URL.createObjectURL = origCreate;
      URL.revokeObjectURL = origRevoke;
    }
  });
});

describe('csvRow / toCsv', () => {
  it('一行 ⇒ 逗号分隔', () => {
    expect(csvRow(['a', 'b'])).toBe('a,b');
  });

  it('⚠️ 含逗号 / 引号 / 换行的**数据行** ⇒ 解析回来仍是 **1 行**', () => {
    const csv = toCsv(['h1', 'h2'], [['a,b', 'x"y\nz']]);
    const lines = csv.split('\r\n');
    // 表头 + 数据行 = 2 段（换行在引号内 ⇒ 不算断行）
    expect(lines.length).toBe(2);
    expect(lines[1]).toBe('"a,b","x""y\nz"');
  });
});
