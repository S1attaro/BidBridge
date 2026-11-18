"""Plain names for the codes SAM.gov uses.

Most small business owners don't know NAICS codes, so the site shows trade
names like "Roofing" and maps them to codes here.
"""

# Plain trade name -> NAICS codes. A code can start with any of these.
TRADES = {
    "roofing": ("Roofing", ["238160"]),
    "plumbing-hvac": ("Plumbing, heating, and cooling", ["238220"]),
    "electrical": ("Electrical work", ["238210"]),
    "painting": ("Painting", ["238320"]),
    "flooring": ("Flooring", ["238330"]),
    "drywall": ("Drywall and insulation", ["238310"]),
    "concrete": ("Concrete and paving", ["238110", "237310"]),
    "building": ("Building and repairs", ["236220", "236118", "238990", "238190"]),
    "landscaping": ("Lawn care and landscaping", ["561730"]),
    "janitorial": ("Cleaning and janitorial", ["561720"]),
    "building-services": ("Snow removal and building services", ["561790", "561210"]),
    "pest-control": ("Pest control", ["561710"]),
    "security": ("Security guards", ["561612"]),
    "waste": ("Trash and waste removal", ["562111", "562119", "562219"]),
    "trucking": ("Moving and trucking", ["484110", "484121", "484210", "484220"]),
    "it": ("IT and computer help", ["541511", "541512", "541513", "541519"]),
    "engineering": ("Engineering", ["541330"]),
    "office-supplies": ("Office supplies", ["424120", "339940"]),
    "food": ("Food and catering", ["722310", "722320", "311991"]),
}

TRADE_CHOICES = [(key, name) for key, (name, codes) in TRADES.items()]

TRADE_ICONS = {
    "roofing": "🏠", "plumbing-hvac": "🌡️", "electrical": "⚡", "painting": "🖌️",
    "flooring": "🧱", "drywall": "🛠️", "concrete": "🚧", "building": "🏗️",
    "landscaping": "🌿", "janitorial": "🧹", "building-services": "❄️", "pest-control": "🐜",
    "security": "🛡️", "waste": "♻️", "trucking": "🚚", "it": "💻",
    "engineering": "📐", "office-supplies": "📎", "food": "🍽️",
}


def trade_for_naics(naics):
    """Return (key, plain name) for a NAICS code, or (None, None)."""
    naics = (naics or "").strip()
    for key, (name, codes) in TRADES.items():
        if any(naics.startswith(c) for c in codes):
            return key, name
    return None, None


def naics_codes(trade_key):
    return TRADES.get(trade_key, ("", []))[1]


# SAM.gov set-aside codes grouped into a few plain choices.
SET_ASIDE_GROUPS = {
    "small": ("Small business", ["SBA", "SBP"]),
    "8a": ("8(a) program", ["8A", "8AN"]),
    "hubzone": ("HUBZone", ["HZC", "HZS"]),
    "sdvosb": ("Veteran-owned (service-disabled)", ["SDVOSBC", "SDVOSBS"]),
    "vosb": ("Veteran-owned", ["VSA", "VSS"]),
    "wosb": ("Woman-owned", ["WOSB", "WOSBSS", "EDWOSB", "EDWOSBSS"]),
    "none": ("Open to anyone", [""]),
}

SET_ASIDE_CHOICES = [(key, name) for key, (name, codes) in SET_ASIDE_GROUPS.items()]


def set_aside_group(code):
    code = (code or "").strip().upper()
    if code in ("", "NONE"):
        return "none"
    for key, (name, codes) in SET_ASIDE_GROUPS.items():
        if code in codes:
            return key
    return None


SET_ASIDE_WHO = {
    "small": "small businesses",
    "8a": "8(a) businesses",
    "hubzone": "HUBZone businesses",
    "sdvosb": "service-disabled veteran-owned businesses",
    "vosb": "veteran-owned businesses",
    "wosb": "woman-owned businesses",
}


SET_ASIDE_ICONS = {"8a": "\U0001F4CB", "hubzone": "\U0001F4CD", "sdvosb": "\U0001F396\uFE0F", "vosb": "\U0001F396\uFE0F",
                   "wosb": "\U0001F469\u200D\U0001F4BC"}


def set_aside_who(code):
    """Plain words for who can bid, like "small businesses". Empty if anyone can."""
    return SET_ASIDE_WHO.get(set_aside_group(code), "")


def set_aside_name(code):
    group = set_aside_group(code)
    if group:
        return SET_ASIDE_GROUPS[group][0]
    return code


# Notice types worth showing to someone who wants to bid.
NOTICE_TYPES = {
    "Solicitation": "Open for bids",
    "Combined Synopsis/Solicitation": "Open for bids",
    "Presolicitation": "Coming soon",
    "Sources Sought": "Looking for businesses",
}


def plain_notice_type(notice_type):
    return NOTICE_TYPES.get(notice_type, notice_type)


STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "Washington, DC", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico", "GU": "Guam",
    "VI": "U.S. Virgin Islands",
}
STATES = list(STATE_NAMES)
STATE_CHOICES = sorted(STATE_NAMES.items(), key=lambda item: item[1])


KEEP_UPPER = {"AFB", "VA", "US", "USA", "USDA", "GSA", "NASA", "DOD", "DHS", "FBI", "IRS", "NAVFAC", "ARNG", "NPS", "II", "III", "JBSA", "JB", "ANGB", "SFB", "USCG", "NAS", "CBOC", "VAMC", "HVAC"}
KEEP_LOWER = {"of", "the", "and", "for", "in", "on", "at", "to"}


def nice_case(text):
    """"DEPT OF THE AIR FORCE" -> "Dept of the Air Force". Keeps known short names like AFB in caps."""
    words = []
    for i, word in enumerate((text or "").split()):
        bare = word.strip(",.()").upper()
        if bare in KEEP_UPPER:
            words.append(word.upper())
        elif i > 0 and word.lower() in KEEP_LOWER:
            words.append(word.lower())
        else:
            words.append(word.capitalize())
    return " ".join(words)
