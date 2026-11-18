from django import template

from contracts import codes

register = template.Library()


@register.filter
def trade_icon(key):
    return codes.TRADE_ICONS.get(key, "\U0001F527")


@register.filter
def set_aside_icon(key):
    return codes.SET_ASIDE_ICONS.get(key, "\U0001F4C4")


@register.filter
def days_text(days):
    if days is None:
        return ""
    if days < 0:
        return "Closed"
    if days == 0:
        return "Closes today"
    if days == 1:
        return "1 day left"
    return f"{days} days left"


@register.filter
def is_in(value, items):
    return bool(items) and value in items


# Urgency colors. One smooth scale: red (due now), orange (1 week), yellow (2 weeks), green (3+ weeks).
# static/js/browse.js uses the same stops for the map dots.
URGENCY_STOPS = [(0, (217, 45, 32)), (7, (240, 124, 18)), (14, (224, 177, 10)), (21, (47, 154, 92))]


def urgency_rgb(days):
    days = max(0, min(21, days if days is not None else 21))
    for (d1, c1), (d2, c2) in zip(URGENCY_STOPS, URGENCY_STOPS[1:]):
        if days <= d2:
            t = (days - d1) / (d2 - d1)
            return tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))
    return URGENCY_STOPS[-1][1]


def _tint(rgb, white):
    return "rgb({},{},{})".format(*(round(v + (255 - v) * white) for v in rgb))


def _shade(rgb):
    return "rgb({},{},{})".format(*(round(v * .78) for v in rgb))


@register.filter
def urgency_style(days):
    """Inline colors for a days-left badge."""
    rgb = urgency_rgb(days)
    return f"background:{_tint(rgb, .9)};border-color:{_tint(rgb, .7)};color:{_shade(rgb)}"


@register.filter
def urgency_chip(days):
    rgb = urgency_rgb(days)
    return f"background:{_tint(rgb, .88)};color:{_shade(rgb)}"


@register.filter
def urgency_dot(days):
    return "rgb({},{},{})".format(*urgency_rgb(days))
