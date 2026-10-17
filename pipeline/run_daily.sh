#!/bin/bash
# ai-daily 每日流水线一键脚本
#   计算"昨天"日期 -> 运行 collect.py 采集 -> 运行 build.py 重新生成网站 -> 输出日志
set -euo pipefail

AI_DAILY="$HOME/workspace/ai-daily"
YESTERDAY="$(TZ=Asia/Shanghai date -d "yesterday" +%F)"
LOG_DIR="$AI_DAILY/logs"
LOG_FILE="$LOG_DIR/${YESTERDAY}.log"
mkdir -p "$LOG_DIR"

{
  echo "=================================================================="
  echo "[$(date '+%F %T %Z')] ai-daily 每日流水线启动, 目标日期: $YESTERDAY"
  echo "=================================================================="

  echo "--- [1/2] 采集内容 ---"
  python3 "$AI_DAILY/pipeline/collect.py" "$YESTERDAY"
  echo "采集完成, 退出码: $?"

  echo "--- [2/2] 重新生成网站 ---"
  if [ -f "$AI_DAILY/build.py" ]; then
    python3 "$AI_DAILY/build.py"
    echo "网站生成完成"
  else
    echo "[warn] 未找到 $AI_DAILY/build.py, 跳过网站生成(数据文件已就绪)"
  fi

  echo "[$(date '+%F %T %Z')] ai-daily 每日流水线结束"
} 2>&1 | tee "$LOG_FILE"

echo "日志已写入: $LOG_FILE"
