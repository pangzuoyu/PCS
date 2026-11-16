#!/usr/bin/env bash
# 启动 hermes 第三视角审查（P10-B 计划）—— 独立进程，避免 pkill 自匹配。
cd /home/pangzy/code_project/PCS || exit 1
exec hermes chat -Q --oneshot \
  --in /home/pangzy/code_project/PCS \
  --query-file docs/superpowers/plans/reviews/2026-11-13-p10-b-hermes/brief.md \
  --reasoning high \
  --max-turns 40 \
  --run-budget 1500
