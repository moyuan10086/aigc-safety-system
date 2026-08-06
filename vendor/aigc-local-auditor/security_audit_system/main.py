from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .audit_system import SecurityAuditSystem
except ImportError:  # pragma: no cover - direct script execution
    from audit_system import SecurityAuditSystem


def main() -> int:
    parser = argparse.ArgumentParser(description="AI 安全审核系统本地入口")
    parser.add_argument("text", nargs="?", help="待审核文本")
    parser.add_argument("--file", type=Path, help="逐行审核文本文件")
    parser.add_argument("--config", type=Path, help="配置文件，默认 security_audit_system/config.json")
    parser.add_argument("--no-alert", action="store_true", help="关闭 alert 标记，只输出 pass/fail")
    parser.add_argument("--alert-threshold", type=float, help="低置信 alert 阈值")
    parser.add_argument("--no-votes", action="store_true", help="不输出专家 vote")
    args = parser.parse_args()

    system = SecurityAuditSystem(
        args.config,
        alert_confidence_threshold=args.alert_threshold,
        enable_alert=not args.no_alert,
        include_votes=not args.no_votes,
    )
    if args.file:
        for line_number, line in enumerate(args.file.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            output = system.audit_dict(line)
            output["line"] = line_number
            output["text"] = line
            print(json.dumps(output, ensure_ascii=False))
        return 0
    if not args.text:
        parser.error("请提供 text 或 --file")
    print(system.audit_json(args.text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
