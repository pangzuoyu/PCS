# OpenWolf

This project uses OpenWolf for context management. The always-on rules live in `.claude/rules/openwolf.md`; the hooks handle bookkeeping (anatomy index, memory log, read tracking) automatically.

For the full operating protocol (session handoff, memory discipline, bug logging), load the `openwolf` skill, or read `.wolf/OPENWOLF.md`. Regenerate the session handoff with `/handoff`.

# 测试前检查

schema 敏感测试（seeds / 迁移 / 真库用例）运行前，先对 pcs_test 库执行：

```bash
cd pcs-backend && uv run alembic upgrade head
```

（矫正迁移 historically 只应用了 pcs 库；pcs_test 需手动对齐后再跑。）
