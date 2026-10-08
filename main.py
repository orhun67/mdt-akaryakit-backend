import json
import os
from datetime import datetime, timezone, timedelta
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from google.api_core.exceptions import AlreadyExists
from google.cloud.firestore_v1.base_query import FieldFilter
from feeds import collect
from monitor import verified_events


def initialize_firebase():
    secret = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    if not secret:
        raise RuntimeError('Firebase servis anahtari bulunamadi.')
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(credentials.Certificate(json.loads(secret)))
    return firestore.client()


def publish(db, event, now):
    """Claim once before sending. An uncertain send is never automatically retried.

    This favors no duplicate alerts over guaranteed delivery. See README.
    """
    ref = db.collection('fuel_alerts').document(event['eventId'])
    try:
        ref.create(dict(event, delivery='claimed', claimedAt=now))
    except AlreadyExists:
        return False
    status_ref = db.collection('fuel_status').document(event['fuelId'])
    @firestore.transactional
    def save_status(transaction):
        old = status_ref.get(transaction=transaction).to_dict() or {}
        from monitor import timestamp
        try:
            old_time = timestamp(old['effectiveAt'])
        except (KeyError, ValueError, TypeError, AttributeError):
            old_time = datetime.min.replace(tzinfo=timezone.utc)
        event_time = timestamp(event['effectiveAt'])
        same_time_downgrade = (old_time == event_time and
                              old.get('state') in ('increase', 'decrease') and
                              event['state'].startswith('expected_'))
        if old_time > event_time or same_time_downgrade:
            return False
        transaction.set(status_ref, dict(event, updatedAt=now), merge=True)
        return True
    if not save_status(db.transaction()):
        ref.update({'delivery': 'superseded'})
        return False
    body = f"{event['fuelName']}: {event['headline']} {event['changeTl']:+.2f} TL/L. {event['effectiveAt']}"
    try:
        message_id = messaging.send(messaging.Message(
            topic='akaryakit_alerts',
            notification=messaging.Notification(title='MDT Akaryakıt Takip', body=body),
            data={k: str(event[k]) for k in ('eventId', 'fuelId', 'state', 'changeTl', 'effectiveAt')},
            android=messaging.AndroidConfig(priority='high', ttl=timedelta(hours=6),
                notification=messaging.AndroidNotification(channel_id='fuel_alerts', tag=event['eventId']))))
        ref.update(dict(delivery='sent', messageId=message_id, sentAt=now))
        return True
    except Exception:
        ref.update(dict(delivery='uncertain', failedAt=now))
        raise


def main():
    now = datetime.now(timezone.utc)
    db = initialize_firebase()
    candidates, health = collect(now)
    for key, candidate in candidates.items():
        try:
            db.collection('fuel_candidates').document(key).create(candidate)
        except AlreadyExists:
            pass
    registry = {doc.id: doc.to_dict() for doc in db.collection('fuel_source_registry').stream()}
    observations = [doc.to_dict() for doc in db.collection('fuel_observations').where(
        filter=FieldFilter('publishedAt', '>=', now - timedelta(hours=72))).stream()]
    events = verified_events(observations, registry, now)
    sent = 0
    for event in events:
        sent += int(publish(db, event, now))
    status = dict(checkedAt=now, feeds=health, candidates=len(candidates),
                  reviewedObservations=len(observations), verifiedEvents=len(events), sent=sent,
                  verificationReady=bool(registry),
                  status='needs_source_setup' if not registry else 'monitoring')
    db.collection('monitor_health').document('latest').set(status)
    print(json.dumps(status, default=str, ensure_ascii=False))
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as out:
            out.write('## MDT Akaryakıt Takip\n\n')
            out.write('| Kontrol | Sonuç |\n|---|---|\n')
            out.write(f'| Haber adayı | {len(candidates)} |\n| Teyitli olay | {len(events)} |\n| Gönderilen | {sent} |\n')
            for source, state in health.items():
                out.write(f"| {source} | {'Erişildi' if state['ok'] else 'Erişim hatası'} |\n")
            if not registry:
                out.write('\nBağımsız kaynak sicili kurulmadı. RSS haberleri teyit sayılmaz; bildirim gönderilmez.\n')
    if not any(s['ok'] for s in health.values()):
        raise RuntimeError('Tum haber kaynaklari erisilemez; veri yok sonucu degisiklik yok anlamina gelmez.')


if __name__ == '__main__':
    main()
