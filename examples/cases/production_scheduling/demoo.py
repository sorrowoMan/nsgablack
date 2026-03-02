from __future__ import annotations
import argparse
import os
from pathlib import Path
from typing import Iterable
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd
def _pick_first_existing_font(candidates: Iterable[str]) -> str | None:
    for name in candidates:
        try:
            path = fm.findfont(fm.FontProperties(family=name), fallback_to_default=False)
        except (TypeError, ValueError, RuntimeError, OSError):
            continue
        if path and Path(path).exists():
            return name
    return None
def _configure_chinese_font(verbose: bool = False) -> None:
    preferred = [
        "Microsoft YaHei",
        "SimHei",
        "SimSun",
        "Arial Unicode MS",
        "WenQuanYi Micro Hei",
    ]
    chosen = _pick_first_existing_font(preferred)
    if chosen:
        plt.rcParams["font.sans-serif"] = [chosen]
    else:
        plt.rcParams["font.sans-serif"] = preferred
    plt.rcParams["axes.unicode_minus"] = False
    if verbose:
        print(f"[viz] font={plt.rcParams['font.sans-serif']}")


def _find_latest_result(search_dirs: list[Path]) -> Path:
    patterns = [
        "integrated_result_production_*.xlsx",
        "integrated_result_*.xlsx",
        "??????_*.xlsx",
        "?????????_*.xlsx",
        "GA_ProductionSchedule_*.xlsx",
        "*.xlsx",
    ]
    candidates: list[Path] = []
    for d in search_dirs:
        if not d.exists():
            continue
        for pat in patterns:
            candidates.extend(d.glob(pat))
    candidates = [p for p in candidates if p.is_file()]
    if not candidates:
        raise FileNotFoundError(
            "没有找到 Excel 结果文件。请用 --input 指定路径，或把输出的 xlsx 放在当前目录/上一级目录。"
        )
    return max(candidates, key=lambda p: p.stat().st_mtime)
def _load_plan(path: Path, sheet: str | None, verbose: bool = False) -> pd.DataFrame:
    xls = pd.ExcelFile(path)
    if sheet is None:
        sheet = "production_plan" if "production_plan" in xls.sheet_names else ("????" if "????" in xls.sheet_names else xls.sheet_names[0])
    elif sheet not in xls.sheet_names:
        raise KeyError(f"Excel 里没有 sheet={sheet!r}。可选：{xls.sheet_names}")

    df = pd.read_excel(path, sheet_name=sheet)
    if verbose:
        print(f"[viz] input={path}")
        print(f"[viz] sheet={sheet}")
        print(f"[viz] columns={list(df.columns)}")
    return df
def _normalize_plan(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    if "Day_Index" not in df.columns:
        raise KeyError("表格缺少 Day_Index 列（必须）。")
    df = df.dropna(subset=["Day_Index"]).copy()
    df["Day_Index"] = df["Day_Index"].astype(int)
    df = df.set_index("Day_Index")
    max_day = int(df.index.max())
    full_index = pd.Index(range(max_day + 1), name="Day_Index")
    df = df.reindex(full_index)
    if "Date" in df.columns:
        labels = (
            df["Date"]
            .fillna(df.index.to_series().apply(lambda x: f"Day{x}"))
            .astype(str)
            .tolist()
        )
        df = df.drop(columns=["Date"])
    else:
        labels = [f"Day{i}" for i in df.index]
    df = df.fillna(0)

    ignore = {"Day_Index"}
    machine_cols = [c for c in df.columns if c not in ignore]
    if not machine_cols:
        raise ValueError("没有找到机种列（除 Day_Index/Date 外的列）。")
    return df[machine_cols], labels
def _plot_plan(
    df_plan: pd.DataFrame,
    x_labels: list[str],
    out_path: Path,
    title: str = "机种生产计划（堆积柱状图 + 表格）",
    with_table: bool = True,
) -> None:
    machine_cols = list(df_plan.columns)
    n_rows = len(machine_cols)

    chart_height = 12
    if with_table:
        row_height = 0.6
        header_height = 1.8
        table_height = n_rows * row_height + header_height
        total_height = chart_height + table_height
        fig, (ax1, ax2) = plt.subplots(
            2,
            1,
            figsize=(min(40, max(18, 0.9 * len(df_plan))), total_height),
            gridspec_kw={"height_ratios": [chart_height, table_height]},
        )
    else:
        fig, ax1 = plt.subplots(figsize=(min(40, max(18, 0.9 * len(df_plan))), chart_height))
        ax2 = None

    bottom = np.zeros(len(df_plan), dtype=float)
    cmap = plt.get_cmap("tab20")
    colors = [cmap(i % 20) for i in range(n_rows)]

    for i, machine in enumerate(machine_cols):
        vals = df_plan[machine].to_numpy(dtype=float)
        bars = ax1.bar(
            df_plan.index,
            vals,
            bottom=bottom,
            color=colors[i],
            alpha=0.65,
            width=0.6,
            edgecolor="white",
            linewidth=0.5,
        )
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax1.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_y() + h / 2,
                    f"{int(h)}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="black",
                )
        bottom += vals

    ax1.set_ylabel("产量")
    ax1.set_title(title, fontsize=16, fontweight="bold", pad=14)
    ax1.grid(axis="y", linestyle="--", alpha=0.4)
    ax1.set_xlim(-0.5, len(df_plan) - 0.5)
    ax1.set_xticks([])

    if with_table and ax2 is not None:
        ax2.axis("off")
        cell_text = []
        for machine in machine_cols:
            row = df_plan[machine].to_numpy(dtype=float)
            cell_text.append([str(int(x)) if x > 0 else "" for x in row])

        table = ax2.table(
            cellText=cell_text,
            rowLabels=machine_cols,
            rowColours=colors,
            colLabels=x_labels,
            loc="center",
            bbox=[0, 0, 1, 1],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(10)

    plt.subplots_adjust(left=0.05, right=0.98, top=0.97, bottom=0.03, hspace=0.05)
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="把生产计划 Excel 画成堆积柱状图（可选表格）。默认会自动寻找最新的 `集成优化结果_*.xlsx`。",
    )
    parser.add_argument("--input", type=str, default=None, help="Excel 路径；不填则自动找最新结果。")
    parser.add_argument("--sheet", type=str, default=None, help="sheet 名；默认优先 '生产计划'。")
    parser.add_argument("--out", type=str, default=None, help="输出 PNG 路径；默认与 input 同目录。")
    parser.add_argument("--no-table", action="store_true", help="不画下方表格（更快、更清爽）。")
    parser.add_argument("--title", type=str, default=None, help="图标题。")
    parser.add_argument("--verbose", action="store_true", help="输出调试信息。")
    args = parser.parse_args(argv)
    _configure_chinese_font(verbose=args.verbose)
    if args.input:
        in_path = Path(args.input).expanduser().resolve()
    else:
        here = Path.cwd()
        in_path = _find_latest_result(
            [
                here / "examples" / "cases",
                here,
                here.parent / "examples" / "cases",
                here.parent,
            ]
        )

    df_raw = _load_plan(in_path, sheet=args.sheet, verbose=args.verbose)
    df_plan, x_labels = _normalize_plan(df_raw)

    if args.out:
        out_path = Path(args.out).expanduser().resolve()
    else:
        stem = in_path.stem
        out_path = in_path.with_name(f"{stem}_production_plan.png")

    title = args.title or ("机种生产计划堆积柱状图" if args.no_table else "机种生产计划（堆积柱状图 + 表格）")
    _plot_plan(df_plan, x_labels, out_path, title=title, with_table=not args.no_table)

    print(f"[viz] saved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

