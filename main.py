from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

CONFIG_PATH = Path(__file__).resolve().parent / "lianli_config.toml"

console = Console()


@dataclass
class Config:
    xyz_ranks: list[int]  # 額外牌組中可用的超量階級。
    fusion_levels: list[int]  # 額外牌組中可用的融合等級。

    def summary(self) -> str:
        return (
            f"超量階級 {_fmt(self.xyz_ranks)}  ·  融合等級 {_fmt(self.fusion_levels)}"
        )

    def b_bounds(self) -> tuple[int, int]:
        return (
            min(self.xyz_ranks) + min(self.fusion_levels),
            max(self.xyz_ranks) + max(self.fusion_levels),
        )


@dataclass
class Solution:
    b: int
    x: int  # 所需的超量階級
    y: int  # 所需的融合等級
    config: Config

    @property
    def x_ok(self) -> bool:
        return self.x in self.config.xyz_ranks

    @property
    def y_ok(self) -> bool:
        return self.y in self.config.fusion_levels

    @property
    def playable(self) -> bool:
        return self.x_ok and self.y_ok


def solve(a: int, b: int, config: Config) -> Solution:
    return Solution(b=b, x=a - b, y=2 * b - a, config=config)


def _fmt(values: list[int]) -> str:
    if not values:
        return "（無）"
    parts: list[str] = []
    start = prev = values[0]
    for v in values[1:]:
        if v == prev + 1:
            prev = v
            continue
        parts.append(str(start) if start == prev else f"{start}-{prev}")
        start = prev = v
    parts.append(str(start) if start == prev else f"{start}-{prev}")
    return ", ".join(parts)


def parse_int_set(raw: str) -> list[int]:
    out: set[int] = set()
    for token in raw.replace(",", " ").split():
        if "-" in token:
            lo_s, hi_s = token.split("-", 1)
            lo, hi = int(lo_s), int(hi_s)
            if lo > hi:
                lo, hi = hi, lo
            out.update(range(lo, hi + 1))
        else:
            out.add(int(token))
    return sorted(out)


def prompt_int_set(label: str, example: str) -> list[int]:
    while True:
        raw = Prompt.ask(f"{label} [dim]（例如 {example}）[/dim]").strip()
        try:
            values = parse_int_set(raw)
        except ValueError:
            console.print("  [red]請使用數字或範圍，例如 '1-5' 或 '4,6,8'。[/red]")
            continue
        if not values:
            console.print("  [red]請至少輸入一個值。[/red]")
            continue
        if any(v < 1 for v in values):
            console.print("  [red]階級／等級必須大於等於 1。[/red]")
            continue
        return values


def ask_int(prompt: str, *, minimum: int = 0) -> int:
    while True:
        raw = Prompt.ask(prompt).strip()
        try:
            value = int(raw)
        except ValueError:
            console.print(f"  [red]『{raw}』不是整數 — 請重新輸入。[/red]")
            continue
        if value < minimum:
            console.print(f"  [red]請輸入大於等於 {minimum} 的數字。[/red]")
            continue
        return value


def ask_b_values() -> list[int]:
    while True:
        raw = Prompt.ask(
            "對方怪獸的等級 [cyan]b[/cyan] （可輸入一個或多個，例如 [dim]4 6 8[/dim]）"
        )
        tokens = raw.replace(",", " ").split()
        if not tokens:
            console.print("  [red]請至少輸入一個值。[/red]")
            continue
        try:
            values = [int(t) for t in tokens]
        except ValueError:
            console.print("  [red]輸入的並非全部都是整數 — 請重新輸入。[/red]")
            continue
        if any(v < 0 for v in values):
            console.print("  [red]等級不能是負數。[/red]")
            continue
        return values


def write_config(config: Config) -> None:
    text = (
        "# 連慄炮 方程式求解器 - 你的額外牌組。\n"
        "# 列出你實際能召喚的超量階級與融合等級。\n"
        "# 可自由編輯（整數），然後重新執行工具。或加上 --setup。\n"
        "\n"
        f"xyz_ranks = {config.xyz_ranks}\n"
        f"fusion_levels = {config.fusion_levels}\n"
    )
    CONFIG_PATH.write_text(text, encoding="utf-8")


def load_config() -> Config:
    data = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    xyz = sorted({int(v) for v in data["xyz_ranks"]})
    fusion = sorted({int(v) for v in data["fusion_levels"]})
    if not xyz or not fusion:
        raise ValueError("牌組清單為空")
    return Config(xyz_ranks=xyz, fusion_levels=fusion)


def first_time_setup() -> Config:
    console.print(
        Panel(
            "[bold]設定你的額外牌組[/bold]\n\n"
            "告訴我你能做出哪些超量階級與融合等級。\n"
            "範圍或清單皆可 — 例如 [dim]1-5[/dim] 或 [dim]4,4,7,8[/dim]。\n"
            f"這會儲存到 [cyan]{CONFIG_PATH.name}[/cyan] 供下次使用。",
            border_style="cyan",
            expand=False,
        )
    )
    xyz = prompt_int_set("你擁有的超量階級", "1-5")
    fusion = prompt_int_set("你擁有的融合等級", "1-6")
    config = Config(xyz_ranks=xyz, fusion_levels=fusion)
    write_config(config)
    console.print(f"[green]✓ 已儲存至 {CONFIG_PATH.name}。[/green]\n")
    return config


def get_config(force_setup: bool) -> Config:
    if force_setup or not CONFIG_PATH.exists():
        return first_time_setup()
    try:
        return load_config()
    except tomllib.TOMLDecodeError, KeyError, ValueError, TypeError:
        console.print(f"[yellow]無法讀取 {CONFIG_PATH.name}，將重新設定。[/yellow]\n")
        return first_time_setup()


def results_table(a: int, solutions: list[Solution]) -> Table:
    table = Table(title=f"a = {a} 的解", title_style="bold")
    table.add_column("b", justify="right", style="cyan")
    table.add_column("x（超量階級）", justify="right")
    table.add_column("y（融合等級）", justify="right")
    table.add_column("狀態", justify="left")

    for s in solutions:
        if s.playable:
            status = "[bold green]✓[/bold green]"
            x_cell, y_cell = f"[green]{s.x}[/green]", f"[green]{s.y}[/green]"
        else:
            status = "[yellow]✗[/yellow]"
            x_cell = f"{s.x}" if s.x_ok else f"[red]{s.x}[/red]"
            y_cell = f"{s.y}" if s.y_ok else f"[red]{s.y}[/red]"
        table.add_row(str(s.b), x_cell, y_cell, status)
    return table


def main() -> None:
    force_setup = "--setup" in sys.argv[1:]

    console.print(
        Panel(
            "[bold]連慄炮 方程式求解器[/bold]\n\n"
            "找出能滿足卡片效果、[bold green]除外對方場上所有卡片[/bold green]的\n"
            "超量階級（[cyan]x[/cyan]）與融合等級（[cyan]y[/cyan]）。\n\n"
            "  [dim]2x + y = a[/dim]   a = 雙方場上與手牌的卡片總數\n"
            "  [dim] x + y = b[/dim]   b = 對方某隻怪獸的等級\n\n"
            "可連續計算多次；按 [bold]Ctrl+C[/bold] 離開。",
            border_style="magenta",
            expand=False,
        )
    )

    config = get_config(force_setup)
    lo, hi = config.b_bounds()
    console.print(f"[dim]你的額外牌組：[/dim]{config.summary()}")
    console.print(
        f"[dim]可鎖定的對方怪獸等級 [/dim][cyan]b[/cyan][dim]：[/dim]"
        f"[bold]{lo} ~ {hi}[/bold][dim]（超出此範圍必定無法施放連慄炮）[/dim]"
    )
    console.print("[dim]（編輯 lianli_config.toml 或加上 --setup 以變更）[/dim]")

    while True:
        console.rule("[dim]新的計算[/dim]")
        a = ask_int("雙方場上與手牌的卡片總數 [cyan]a[/cyan]", minimum=0)
        solutions = [solve(a, b, config) for b in ask_b_values()]

        console.print()
        console.print(results_table(a, solutions))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt, EOFError:
        console.print("\n[dim]已離開。[/dim]")
