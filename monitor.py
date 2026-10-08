"""Conservative evidence gate. RSS headlines are candidates, never confirmations."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from urllib.parse import urlparse

FUELS = {'motorin': 'Motorin', 'benzin': 'Benzin', 'lpg': 'LPG'}
STATES = {'expected_increase', 'expected_decrease', 'increase', 'decrease'}


def timestamp(value):
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timezone required')
    return dt.astimezone(timezone.utc)


def verified_events(observations, registry, now):
    """Registry maps vetted original source IDs to domain and ownership group.

    Only server-reviewed observations are accepted. Three URLs, publishers or
    a legacy verificationCount field alone are deliberately insufficient.
    """
    groups = defaultdict(list)
    for row in observations:
        try:
            source = registry[row['originId']]
            if source.get('enabled') is not True or row.get('reviewed') is not True:
                continue
            if not row.get('reviewedBy') or not source.get('independenceGroup'):
                continue
            url = urlparse(row['url'])
            if url.scheme != 'https' or url.hostname not in source['domains']:
                continue
            fuel, state = row['fuelId'], row['state']
            if fuel not in FUELS or state not in STATES:
                continue
            amount = Decimal(str(row['changeTl']))
            if not amount.is_finite() or amount == 0 or abs(amount) > 30:
                continue
            if amount != amount.quantize(Decimal('.01')):
                continue
            if (amount > 0) != state.endswith('increase'):
                continue
            published, effective = timestamp(row['publishedAt']), timestamp(row['effectiveAt'])
            if not now - timedelta(hours=72) <= published <= now + timedelta(minutes=5):
                continue
            expected = state.startswith('expected_')
            if expected and not now < effective <= now + timedelta(days=7):
                continue
            if not expected and not now - timedelta(hours=48) <= effective <= now:
                continue
            key = (fuel, state, str(amount.quantize(Decimal('.01'))), effective.isoformat())
            groups[key].append((source['independenceGroup'], row))
        except (KeyError, ValueError, TypeError, InvalidOperation, AttributeError):
            continue

    # Conflicting amounts/directions for the same fuel, stage and time block publication.
    conflicts = defaultdict(set)
    for key in groups:
        conflicts[(key[0], key[1].startswith('expected_'), key[3])].add((key[1], key[2]))
    result = []
    for key, evidence in groups.items():
        fuel, state, amount, effective = key
        if len(conflicts[(fuel, state.startswith('expected_'), effective)]) != 1:
            continue
        unique = {origin: row for origin, row in evidence}
        if len(unique) < 3:
            continue
        event_id = sha256('|'.join(key).encode()).hexdigest()
        result.append(dict(eventId=event_id, fuelId=fuel, fuelName=FUELS[fuel],
                           state=state, changeTl=float(amount), effectiveAt=effective,
                           verificationCount=len(unique), sources=sorted({r['url'] for r in unique.values()}),
                           headline=('Beklenen ' if state.startswith('expected_') else 'Gerçekleşen ') +
                           ('zam' if state.endswith('increase') else 'indirim')))
    return sorted(result, key=lambda e: (e['effectiveAt'], e['state']))
