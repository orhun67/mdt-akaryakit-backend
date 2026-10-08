import unittest
from datetime import datetime, timedelta, timezone
from monitor import verified_events


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 8, 14, tzinfo=timezone.utc)
        self.registry = {str(i): dict(enabled=True, independenceGroup=str(i),
                                     domains=[f'{i}.example.com']) for i in range(4)}
        self.rows = [dict(originId=str(i), reviewed=True, reviewedBy='admin',
                          url=f'https://{i}.example.com/news', fuelId='motorin',
                          state='expected_decrease', changeTl=-1.5,
                          effectiveAt=self.now + timedelta(hours=7), publishedAt=self.now)
                     for i in range(3)]

    def check(self, count):
        self.assertEqual(len(verified_events(self.rows, self.registry, self.now)), count)

    def test_three_independent_origins(self): self.check(1)

    def test_same_agency_not_three_confirmations(self):
        for source in self.registry.values(): source['independenceGroup'] = 'same-agency'
        self.check(0)

    def test_duplicate_article_does_not_count(self):
        self.rows = [self.rows[0]] * 3
        self.check(0)

    def test_unreviewed_news_not_evidence(self):
        self.rows[0]['reviewed'] = False
        self.check(0)

    def test_foreign_domain_not_evidence(self):
        self.rows[0]['url'] = 'https://other.example.org/news'
        self.check(0)

    def test_conflicting_amount_blocks_alert(self):
        self.rows.append(dict(self.rows[0], originId='3', url='https://3.example.com/news', changeTl=-2))
        self.check(0)

    def test_stale_news_rejected(self):
        self.rows[0]['publishedAt'] = self.now - timedelta(days=4)
        self.check(0)

    def test_wrong_sign_rejected(self):
        self.rows[0]['changeTl'] = 1.5
        self.check(0)

    def test_naive_date_rejected(self):
        self.rows[0]['effectiveAt'] = '2026-10-08T21:00:00'
        self.check(0)

    def test_elapsed_expected_never_becomes_actual(self):
        self.assertEqual(verified_events(self.rows, self.registry, self.now + timedelta(hours=8)), [])

    def test_actual_requires_actual_evidence(self):
        for row in self.rows:
            row.update(state='decrease', effectiveAt=self.now - timedelta(hours=1))
        self.check(1)

    def test_event_id_stable_across_source_order(self):
        a = verified_events(self.rows, self.registry, self.now)[0]['eventId']
        b = verified_events(list(reversed(self.rows)), self.registry, self.now)[0]['eventId']
        self.assertEqual(a, b)

    def test_unknown_registry_fails_closed(self):
        self.registry = {}
        self.check(0)

    def test_legacy_verification_count_not_trusted(self):
        self.rows = [dict(fuelId='motorin', verificationCount=3, state='expected_decrease')]
        self.check(0)

    def test_invalid_amount_rejected(self):
        for value in ('NaN', 'Infinity', 0, 0.001):
            with self.subTest(value=value):
                self.rows[0]['changeTl'] = value
                self.check(0)


if __name__ == '__main__': unittest.main()
