"""Save the original Summary Cards design; errors leave the last valid SVG intact."""

import argparse
from pathlib import Path
import re
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

CARD_URL = (
    "https://github-profile-summary-cards.vercel.app/api/cards/profile-details"
    "?username=heetae-L&theme=github_dark&name=Recent%20activity"
    "&bg_color=121c29&title_color=a9c5df&text_color=8aa1b8"
    "&chart_color=85b9dc&border_color=121c29"
)
LIGHT_COLORS = {
    "#121c29": "#f3f7fa",
    "#a9c5df": "#355570",
    "#8aa1b8": "#6b8298",
    "#85b9dc": "#7196b2",
    "#8b949e": "#586069",
}
SVG = "{http://www.w3.org/2000/svg}"


def validate_card(source):
    if re.search(r"error|rate.?limit|temporarily|<!DOCTYPE", source, re.IGNORECASE):
        raise ValueError("Card service returned an error instead of a valid profile card")
    root = ET.fromstring(source)
    if root.tag != SVG + "svg" or (root.get("width"), root.get("height")) != ("700", "200"):
        raise ValueError("Unexpected profile card format")
    text = " ".join(element.text or "" for element in root.iter(SVG + "text"))
    expected = ("Recent activity", "Contributions on GitHub", "Public Repos",
                "Joined GitHub", "contributions in the last year")
    if not all(label in text for label in expected):
        raise ValueError("Profile card is missing its original details")
    if not any(element.get("d", "").startswith("M") and element.get("fill") in ("#85b9dc", "#7196b2")
               for element in root.iter(SVG + "path")):
        raise ValueError("Profile card is missing its contribution graph")
    if any(element.tag in (SVG + "script", SVG + "foreignObject") for element in root.iter()):
        raise ValueError("Unexpected active content in profile card")


def make_cards(dark):
    validate_card(dark)
    # Derive the matching light palette from the same response, keeping the two
    # themes' data and chart geometry identical and making one daily request.
    light = re.sub(r"#[0-9a-fA-F]{6}\b",
                   lambda match: LIGHT_COLORS.get(match[0].lower(), match[0]), dark)
    validate_card(light)
    return {"dark": dark, "light": light}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg", type=Path, help="Validate and save a downloaded card")
    args = parser.parse_args()
    if args.svg:
        source = args.svg.read_text(encoding="utf-8")
    else:
        request = Request(CARD_URL, headers={"User-Agent": "heetae-L-profile-activity"})
        with urlopen(request, timeout=30) as response:
            source = response.read(500_000).decode("utf-8")
    # Download and validate both themes before touching the saved images.
    cards = make_cards(source)
    output = Path(__file__).resolve().parents[1] / "assets"
    output.mkdir(exist_ok=True)
    for theme, svg in cards.items():
        destination = output / f"activity-{theme}.svg"
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(svg.rstrip() + "\n", encoding="utf-8", newline="\n")
        temporary.replace(destination)
    print("Saved original profile card design in both themes.")


if __name__ == "__main__":
    main()
