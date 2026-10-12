"""Render public GitHub activity; failed downloads leave the saved cards intact."""

import argparse
from collections import defaultdict
from datetime import date, timedelta
from html.parser import HTMLParser
from math import ceil
from pathlib import Path
import re
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells = {}
        self.tooltips = {}
        self.current = None
        self.caption = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and attrs.get("data-date"):
            self.cells[attrs["id"]] = date.fromisoformat(attrs["data-date"])
        if tag == "tool-tip" and attrs.get("for"):
            self.current = attrs["for"]
            self.caption = []

    def handle_data(self, data):
        if self.current:
            self.caption.append(data)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.current:
            self.tooltips[self.current] = "".join(self.caption).strip()
            self.current = None


def parse_calendar(source):
    parser = CalendarParser()
    parser.feed(source)
    days = {}
    for cell, day in parser.cells.items():
        caption = parser.tooltips.get(cell, "")
        match = re.match(r"(No|[\d,]+) contributions? on\b", caption)
        if not match:
            raise ValueError("Contribution calendar has an unrecognized or missing count")
        if day in days:
            raise ValueError("Contribution calendar contains duplicate dates")
        days[day] = 0 if match[1] == "No" else int(match[1].replace(",", ""))
    ordered = sorted(days)
    if not 360 <= len(ordered) <= 371:
        raise ValueError("Contribution calendar is incomplete")
    if any(b - a != timedelta(days=1) for a, b in zip(ordered, ordered[1:])):
        raise ValueError("Contribution calendar contains a date gap")
    return [(day, days[day]) for day in ordered]


def render(days, theme):
    colors = {
        "light": ("f3f7fa", "355570", "6b8298", "7196b2", "dce6ef"),
        "dark": ("121c29", "a9c5df", "8aa1b8", "85b9dc", "26364a"),
    }
    bg, title, text, chart, grid = colors[theme]
    weeks = defaultdict(int)
    for day, count in days:
        weeks[day - timedelta(days=day.weekday())] += count
    weekly = sorted(weeks.items())
    maximum = max(10, ceil(max(weeks.values()) / 10) * 10)
    left, right, top, bottom = 306, 924, 67, 183
    points = [(left + i * (right - left) / (len(weekly) - 1),
               bottom - count * (bottom - top) / maximum)
              for i, (_, count) in enumerate(weekly)]
    line = f"M {points[0][0]:.1f} {points[0][1]:.1f}"
    for i in range(1, len(points) - 1):
        x, y = points[i]
        nx, ny = points[i + 1]
        line += f" Q {x:.1f} {y:.1f} {(x + nx) / 2:.1f} {(y + ny) / 2:.1f}"
    line += f" L {points[-1][0]:.1f} {points[-1][1]:.1f}"
    area = line + f" L {right} {bottom} L {left} {bottom} Z"
    total = sum(count for _, count in days)
    active = sum(count > 0 for _, count in days)
    labels = []
    for i in range(0, len(weekly), 9):
        x = points[i][0]
        labels.append(f'<text x="{x:.1f}" y="206" text-anchor="middle">{weekly[i][0]:%b}</text>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="240" viewBox="0 0 960 240" role="img" aria-labelledby="title desc">
  <title id="title">Recent activity</title>
  <desc id="desc">{total:,} contributions across {active} active days, from {days[0][0]} to {days[-1][0]}. Graph shows weekly contribution totals from the public GitHub calendar.</desc>
  <rect width="960" height="240" rx="7" fill="#{bg}"/>
  <g font-family="Consolas, Menlo, monospace">
    <text x="28" y="37" fill="#{title}" font-size="20">Recent activity</text>
    <text x="28" y="89" fill="#{title}" font-size="26">{total:,}</text>
    <text x="28" y="111" fill="#{text}" font-size="12">contributions in the last year</text>
    <text x="28" y="151" fill="#{title}" font-size="18">{active} active days</text>
    <text x="28" y="211" fill="#{text}" font-size="10">Updated {days[-1][0]}</text>
    <text x="924" y="38" text-anchor="end" fill="#{text}" font-size="10">weekly contributions</text>
    <path d="M {left} {top} H {right} M {left} {(top + bottom) / 2} H {right} M {left} {bottom} H {right}" stroke="#{grid}" stroke-width="1" fill="none"/>
    <path d="{area}" fill="#{chart}" opacity="0.8"/>
    <path d="{line}" stroke="#{chart}" stroke-width="2" fill="none"/>
    <g fill="#{text}" font-size="10">{''.join(labels)}</g>
  </g>
</svg>
'''
    ET.fromstring(svg)
    return svg


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--html", type=Path, help="Read a saved public calendar instead of downloading")
    args = cli.parse_args()
    if args.html:
        source = args.html.read_text(encoding="utf-8")
    else:
        request = Request("https://github.com/users/heetae-L/contributions",
                          headers={"User-Agent": "heetae-L-profile-activity", "Accept-Language": "en"})
        with urlopen(request, timeout=30) as response:
            source = response.read(2_000_000).decode("utf-8")
    days = parse_calendar(source)
    # Validate both themes before replacing any existing image.
    cards = {theme: render(days, theme) for theme in ("light", "dark")}
    output = Path(__file__).resolve().parents[1] / "assets"
    output.mkdir(exist_ok=True)
    for theme, svg in cards.items():
        destination = output / f"activity-{theme}.svg"
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(svg, encoding="utf-8", newline="\n")
        temporary.replace(destination)
    print(f"Rendered {len(days)} public calendar days; total {sum(n for _, n in days):,}.")


if __name__ == "__main__":
    main()
