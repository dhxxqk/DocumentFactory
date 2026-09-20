import argparse
from pathlib import Path
import sys
from . import __version__
from .models import DocumentFactoryError
from .lint_engine import lint
from .renderer import render
from .report_writer import write_report
from .normalizer import normalize
from .template import analyze_template, apply_template


def main(argv=None):
    parser = argparse.ArgumentParser(description="DocumentFactory：DOCX 结构审计、确定性规范化与渲染")
    parser.add_argument("--version", action="version", version=__version__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("lint", "render", "audit"):
        command = subcommands.add_parser(name)
        command.add_argument("input", type=Path)
        if name != "render":
            command.add_argument("--rules", type=Path, default=Path("rules/grid_tech_v1_4.yaml"))
            command.add_argument("--report", type=Path)
        if name != "lint":
            command.add_argument("--output-dir", type=Path)
            command.add_argument("--backend", choices=("auto", "LibreOffice", "Word COM"), default="auto")
            command.add_argument("--timeout", type=int, default=120)
            command.add_argument("--dpi", type=int, default=144)
    command = subcommands.add_parser("normalize")
    command.add_argument("input", type=Path)
    command.add_argument("--rules", type=Path, default=Path("rules/grid_tech_v1_4.yaml"))
    command.add_argument("--output", type=Path)
    command.add_argument("--report", type=Path)
    template_command = subcommands.add_parser("template")
    template_subcommands = template_command.add_subparsers(dest="template_command", required=True)
    analyze_command = template_subcommands.add_parser("analyze")
    analyze_command.add_argument("template", type=Path)
    analyze_command.add_argument("--output", type=Path)
    apply_command = template_subcommands.add_parser("apply")
    apply_command.add_argument("--template", type=Path, required=True)
    apply_command.add_argument("--input", type=Path, required=True)
    apply_command.add_argument("--output", type=Path)
    apply_command.add_argument("--report", type=Path)
    apply_command.add_argument("--rules", type=Path, default=Path("rules/grid_tech_v1_4.yaml"))
    args = parser.parse_args(argv)
    try:
        if args.command == "template":
            if args.template_command == "analyze":
                output = args.output or Path("reports") / f"{args.template.stem}_profile.json"
                profile = analyze_template(args.template, output)
                print("STATUS=PASS")
                print(f"PROFILE={Path(output).resolve()}")
                print(f"STYLES={len(profile.styles)}")
                print(f"TABLE_STYLES={len(profile.table_styles)}")
                return 0
            result = apply_template(args.template, args.input, args.output, args.report, args.rules)
            print(f"STATUS={result.status}")
            print(f"OUTPUT={result.output_path}")
            print(f"REPORT={result.report_path}")
            print(f"MAPPINGS={len(result.mappings)}")
            print(f"CHANGED={len(result.changes)}")
            return 0 if result.status == "PASS" else 1
        if args.command == "normalize":
            result = normalize(args.input, args.rules, args.output, args.report)
            print(f"STATUS={result.status}")
            print(f"OUTPUT={result.output_path}")
            print(f"REPORT={result.report_path}")
            print(f"BEFORE_ERROR={result.before_counts['ERROR']}")
            print(f"AFTER_ERROR={result.after_counts['ERROR']}")
            print(f"CHANGED={len(result.changes)}")
            return 1 if result.status == "FAIL" else 0
        ctx = lint(args.input, args.rules) if args.command != "render" else None
        result = render(args.input, args.output_dir, timeout=args.timeout, dpi=args.dpi, backend=args.backend) if args.command != "lint" else None
        if ctx:
            path = write_report(ctx, args.report or Path("reports") / f"{args.input.stem}_LINT_REPORT.md", result)
            print(f"RESULT={ctx.result} ERROR={ctx.counts['ERROR']} WARNING={ctx.counts['WARNING']} INFO={ctx.counts['INFO']}")
            print(f"中文报告：{path}")
        if result:
            print(f"{result.status} backend={result.backend} PNG={len(result.pages)}\n{result.message}")
            if result.pdf:
                print(f"PDF：{result.pdf}")
            if result.status != "SUCCESS":
                return 3
        return 1 if ctx and ctx.result == "FAIL" else 0
    except DocumentFactoryError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"执行失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
