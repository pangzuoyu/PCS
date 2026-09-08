# PRO/II Parser Test Fixtures

5 最小复现 .inp + .out 双文件样例，覆盖 SIM-2 parser 5 个边界场景。
手工构造（不复制仓库 `sample/` 大文件，避免版权 + 体积约束）。

## 5 样例映射

| 目录 | Banner | 收敛状态 | 覆盖 lexer 边界 | spec 锚点 |
|---|---|---|---|---|
| `sample1_34comp/` | V8.5 | CONVERGED | 34 组分表解析 | spec §608 |
| `sample2_unconverged/` | V4.17 | NOT_CONVERGED | 未收敛 → unreliable 流标记 | spec §614 |
| `sample3_side_draw/` | V8.5 | CONVERGED | SIDESTRIPPER 侧线抽出 | spec §619 |
| `sample4_flash_valve/` | V2.71 | WARNINGS | FLASH + VALVE + zero_flow 流 | spec §623 |
| `sample5_reactor_extraction/` | V8.5 | CONVERGED | REACTOR + EXTRACTOR + 4 反应 | spec §628 |

## Banner 版本分布（满足 P3.2 SIM plan §243 三版支持）

- **V2.71**：sample4（1995 老格式，spec §第三部分示例同款）
- **V4.17**：sample2（1998 过渡格式，sample2 未收敛参考）
- **V8.5**：sample1, sample3, sample5（2014+ 现代格式，仓库 dmc.inp 同款）

## 文件大小约束

- `.inp` < 5 KB
- `.out` < 20 KB

## 验收要点（spec §607-633）

| 样例 | 关键断言 |
|---|---|
| sample1 | `len(result.components) == 34`、`convergence_status == "CONVERGED"`、`len(result.streams) == 21` |
| sample2 | `convergence_status == "NOT_CONVERGED"`、`result.streams["S2"].unreliable == True` |
| sample3 | `result.streams["F"].is_side_draw == True`、`len(result.components) == 38` |
| sample4 | `result.unit_ops["V01"].type == "FLASH"`（VALVE+FLASH 组合）、`result.zero_flow_streams == ["FG1", "FG2"]` |
| sample5 | `result.unit_ops["R101"].type == "REACTOR"`、`len(result.reactions) == 4`、含 `COMPRESSOR` / `SPLITTER` / `STCA` / `CALCULATOR` |

## 验证命令

```bash
# Banner 版本正确
head -2 sample1_34comp/sample1_34comp.out
head -2 sample2_unconverged/sample2_unconverged.out
head -2 sample3_side_draw/sample3_side_draw.out
head -2 sample4_flash_valve/sample4_flash_valve.out
head -2 sample5_reactor_extraction/sample5_reactor_extraction.out

# 收敛状态正确
grep -c "CONVERGED\|NOT_CONVERGED\|WARNINGS" sample*/*.out

# RUN STATISTICS 末段
tail -8 sample*/*.out
```

## 回归样本（不入此目录）

仓库 `sample/dmc.inp+out` / `huafeng140_FCC2015.out` / `200FlexiCoking1.out` /
`proii .out`（V2.71 + V4.17 + V8.x 真实工程实例）由 `pytest -m regression`
路径使用，不进 git 也不进 fixtures。

## 与 parser 实现的契约

双文件接口（spec §1229 `parse_proii_files(inp_path, out_path)`）：
- `.inp` → lexer 提取组分表、物流、单元操作
- `.out` → 提取 banner 版本、收敛状态、警告、单元产品可靠性

parser 应：
1. 跳过 `** WARNING **` 输出行
2. `$` 后非注释数据截断
3. 零流量物流保留（标记 `zero_flow=True`，不剔除）
4. 收敛分层：CONVERGED / WARNINGS / NOT_CONVERGED / ABORTED / NOT_SOLVED
5. NOT_CONVERGED/ABORTED 单元的输出流 → `unreliable=True`