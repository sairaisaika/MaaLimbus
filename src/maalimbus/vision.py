"""Text + normalized position; artwork and currency are never scene anchors."""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Text:
    text: str
    box: tuple[int, int, int, int]
    score: float


def find(records, pattern, roi, size, threshold=.65):
    w, h = size
    matches = []
    for record in records:
        x, y, bw, bh = record.box
        cx, cy = (x + bw / 2) / w, (y + bh / 2) / h
        if record.score >= threshold and roi[0] <= cx <= roi[2] and roi[1] <= cy <= roi[3] and re.search(pattern, record.text, re.I):
            matches.append(record)
    return matches


def inset_box(box, ratio=.2):
    x, y, w, h = box
    dx, dy = int(w * ratio), int(h * ratio)
    return (x + dx, y + dy, max(1, w - 2 * dx), max(1, h - 2 * dy))


def classify(records, locale, size):
    # Shop/extraction/resource dialogs are separate tasks, never generic mirror buttons.
    forbidden = locale['forbidden_dialog']
    if find(records, forbidden, (.2, .15, .85, .85), size, .7):
        return 'RESOURCE_DIALOG'
    if find(records, locale['expired'], (.15, .1, .9, .85), size):
        return 'EXPIRED_SESSION'
    if find(records, locale['defeat'], (.15, .05, .9, .7), size):
        return 'DEFEAT'
    if (find(records,locale['acquire_gift'],(.06,.13,.95,.26),size,.8)
        and find(records,locale['gift_confirm'],(.77,.72,.97,.91),size,.8)):
        return 'FLOOR_GIFTS'
    if find(records, locale['mirror_menu'], (.23, .25, .46, .55), size) and find(records, locale['inferno'], (.70, .07, .99, .3), size):
        return 'DRIVE'
    if find(records, locale['enter'], (.76, .55, .97, .85), size) and find(records, locale['exploring'], (.68, .10, .96, .3), size):
        return 'MIRROR_ENTRY'
    # The supplied Sinners page is a library, not the dungeon deployment page.
    if (find(records, locale['details'], (.6, .04, .95, .35), size)
        and find(records, locale['teams'], (.03, .08, .20, .8), size)
        and find(records, locale['sin_cost'], (.78, .05, .95, .24), size)):
        return 'TEAM_LIBRARY'
    return 'UNKNOWN'
