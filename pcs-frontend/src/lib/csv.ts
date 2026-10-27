/**
 * CSV 导出工具（P9B-2 · T7）。
 *
 * ## 为什么必须自己转义
 *
 * 审计日志的 `detail_json` 里**什么都可能有**：逗号、引号、换行 ⇒ 不转义
 * 的话导出的文件会被 Excel 拆成错列 / 破行 ⇒ 用户拿到的数据是**残缺的**，
 * 而他以为那是全部。
 *
 * ## RFC 4180
 *
 * - 含 `,` `"` CR LF 的字段**必须**用双引号包起来；
 * - 字段里的 `"` 要**加倍**（`"` → `""`）。
 *
 * ⚠️ 另：单元格以 `=` / `+` / `-` / `@` 开头时是**公式注入**面 ⇒ 本实现
 * 在前面加一个 `'`（Excel 会把它当文本）。⚠️ 这会让**正常**的负数（`-1`）
 * 变成 `'-1` ⇒ 只对**非数字**的这类前缀加。
 */

/** 单个单元格 ⇒ CSV 字段（RFC 4180）。 */
export function csvCell(value: unknown): string {
  if (value === null || value === undefined) return '';
  const raw = String(value);
  // ⚠️ 公式注入：非数字的 `=`/`+`/`-`/`@` 开头 ⇒ 前置 `'`（Excel 当文本）。
  // ⚠️ **tab / CR 也要算**：Excel / LibreOffice 会**忽略前导的 tab / CR** ⇒
  //    `\t=1+1` 照样被当公式求值 ⇒ 注入向量不止 4 个前缀。
  const safe = /^[=+\-@\t\r]/.test(raw) && !/^-?\d+(\.\d+)?$/.test(raw) ? `'${raw}` : raw;
  if (/[",\r\n]/.test(safe)) {
    return `"${safe.replace(/"/g, '""')}"`;
  }
  return safe;
}

/** 一行 ⇒ CSV 记录（不含换行）。 */
export function csvRow(values: unknown[]): string {
  return values.map(csvCell).join(',');
}

/**
 * 整个表 ⇒ CSV 文本。
 *
 * @param headers 表头（逐字）
 * @param rows 数据行
 */
export function toCsv(headers: string[], rows: unknown[][]): string {
  return [csvRow(headers), ...rows.map(csvRow)].join('\r\n');
}

/** 触发浏览器下载（前端唯一的导出出口）。 */
export function downloadCsv(filename: string, csv: string): void {
  // ⚠️ BOM：Excel 靠它认出 UTF-8 ⇒ 没有 BOM 中文全是乱码
  // ⚠️ 用转义写法（字面 BOM 会被 eslint 的 no-irregular-whitespace 拦下）
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
