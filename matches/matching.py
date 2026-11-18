"""Find the open contracts that fit a contractor's profile.

1. Hard filters: open, in a state they work in, and a set-aside they can bid on.
2. Text similarity between the profile and each contract (TF-IDF for now).
3. Small bonuses: same trade code, set-aside made for them, enough time to bid.
4. A one-sentence reason built from the rules above.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from contracts import codes
from contracts.filters import can_bid_q, open_contracts

from .models import Match

KEEP = 50
MIN_SCORE = 0.08

TRADE_BONUS = 0.30
SET_ASIDE_BONUS = 0.05
TIME_BONUS = 0.05
SIMILARITY_WEIGHT = 0.6



def profile_text(profile):
    return " ".join(profile.trade_names + [profile.services])


def contract_text(contract):
    parts = [contract.title, contract.trade_name or ""]
    summary = getattr(contract, "summary", None)
    if summary:
        parts += [summary.job, summary.summary, " ".join(summary.skills)]
    parts.append(contract.description_text[:1500])
    return " ".join(p for p in parts if p)


def candidates(profile):
    qs = open_contracts().filter(place_state__in=profile.states).select_related("summary")
    return list(qs.filter(can_bid_q(profile)))


def keyword_similarity(query, texts):
    """TF-IDF cosine similarity between the query and each text, plus the words they share."""
    if not texts:
        return [], []
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    matrix = vectorizer.fit_transform([query] + texts)
    scores = cosine_similarity(matrix[0], matrix[1:])[0]
    words = vectorizer.get_feature_names_out()
    query_words = set(matrix[0].nonzero()[1])
    shared = []
    for i in range(len(texts)):
        row = matrix[i + 1]
        both = [(row[0, j], words[j]) for j in row.nonzero()[1] if j in query_words and " " not in words[j]]
        shared.append([w for _, w in sorted(both, reverse=True)[:2]])
    return list(scores), shared


def trade_match(profile, contract):
    return any(contract.naics_code.startswith(c) for c in profile.naics_codes) if contract.naics_code else False


def build_reason(profile, contract, same_trade, shared_words):
    trade = (contract.trade_name or "").lower()
    state = codes.STATE_NAMES.get(contract.place_state, contract.place_state)
    where = contract.place if contract.place_city else state
    if same_trade:
        sentence = f"Your kind of work in {where}."
    elif shared_words:
        sentence = f"Needs {' and '.join(shared_words)}, in {where}."
    else:
        sentence = f"May fit your work, in {where}."

    who = codes.set_aside_who(contract.set_aside)
    if who:
        sentence += f" Only for {who}."
    elif contract.days_left is not None and contract.days_left >= 7:
        sentence += f" {contract.days_left} days to bid."
    return sentence[:400]


def score_contracts(profile):
    """Return a list of (score, similarity, contract, reason), best first."""
    found = candidates(profile)
    sims, shared = keyword_similarity(profile_text(profile), [contract_text(c) for c in found])
    results = []
    for contract, sim, words in zip(found, sims, shared):
        same_trade = trade_match(profile, contract)
        score = SIMILARITY_WEIGHT * sim
        if same_trade:
            score += TRADE_BONUS
        if codes.set_aside_group(contract.set_aside) not in (None, "none"):
            score += SET_ASIDE_BONUS
        if contract.days_left is not None and contract.days_left >= 7:
            score += TIME_BONUS
        if score < MIN_SCORE or not (same_trade or sim > 0.05):
            continue
        results.append((round(score, 4), float(sim), contract, build_reason(profile, contract, same_trade, words)))
    results.sort(key=lambda r: (-r[0], r[2].due_date))
    return results[:KEEP]


def refresh_matches(profile):
    """Recompute and save the profile's matches. Returns how many were found."""
    results = score_contracts(profile)
    Match.objects.filter(profile=profile).delete()
    Match.objects.bulk_create([
        Match(profile=profile, contract=c, score=score, similarity=sim, reason=reason)
        for score, sim, c, reason in results
    ])
    return len(results)
