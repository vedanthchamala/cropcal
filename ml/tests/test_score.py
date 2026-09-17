import unittest

from evals.score import (aggregate, field_sim, match_events, rrule_key, score_case,
                         score_pair, text_sim)

EVENT = {
    "title": "CS 314 Exam 1",
    "start": "2026-09-23T18:45:00",
    "end": "2026-09-23T21:15:00",
    "all_day": False,
    "timezone": None,
    "location": "WEL 2.224",
    "description": "Two hour exam",
    "recurrence": None,
    "confidence": "high",
    "notes": None,
}


class TestScorePair(unittest.TestCase):
    def test_identical_events_score_perfect(self):
        result = score_pair(EVENT, EVENT)
        self.assertTrue(all(result[k] for k in result if k != "title_similarity"))
        self.assertEqual(result["title_similarity"], 1.0)

    def test_wrong_year_fails_date_only(self):
        pred = {**EVENT, "start": "2027-09-23T18:45:00"}
        result = score_pair(pred, EVENT)
        self.assertFalse(result["start_date"])
        self.assertTrue(result["start_time"])

    def test_all_day_gold_ignores_time(self):
        gold = {**EVENT, "all_day": True, "start": "2026-09-23T00:00:00", "end": None}
        pred = {**gold, "start": "2026-09-23T09:00:00"}
        result = score_pair(pred, gold)
        self.assertTrue(result["start_time"])
        self.assertTrue(result["end"])

    def test_null_location_mismatch_fails(self):
        pred = {**EVENT, "location": None}
        self.assertFalse(score_pair(pred, EVENT)["location"])


class TestMatching(unittest.TestCase):
    def test_matches_swapped_order(self):
        a = {**EVENT, "title": "Info Session 1", "start": "2026-08-25T19:00:00"}
        b = {**EVENT, "title": "Open Garage 2", "start": "2026-08-27T14:30:00"}
        self.assertEqual(match_events([b, a], [a, b]), [(0, 1), (1, 0)])

    def test_junk_prediction_is_fp_and_fn(self):
        junk = {**EVENT, "title": "Completely Unrelated Thing", "start": "2030-01-01T00:00:00"}
        result = score_case([junk], [EVENT])
        self.assertEqual(result["matched"], 0)
        self.assertEqual(result["false_positives"], 1)
        self.assertEqual(result["false_negatives"], 1)

    def test_empty_prediction_counts_misses(self):
        result = score_case([], [EVENT, EVENT])
        self.assertEqual(result["false_negatives"], 2)


class TestAggregate(unittest.TestCase):
    def test_perfect_run(self):
        case = score_case([EVENT], [EVENT])
        agg = aggregate([case, case])
        self.assertEqual(agg["detection"]["f1"], 1.0)
        self.assertEqual(agg["fields"]["start_date"], 1.0)

    def test_text_sim_null_handling(self):
        self.assertEqual(text_sim(None, None), 1.0)
        self.assertEqual(text_sim("x", None), 0.0)


class TestFieldSim(unittest.TestCase):
    def test_extra_detail_in_prediction_scores_full(self):
        self.assertEqual(
            field_sim("Zilker Park, 2100 Barton Springs Rd, Austin, TX", "Zilker Park"), 1.0
        )
        self.assertEqual(
            field_sim("AI Builders Guild Webinar: Intro to RAG Systems",
                      "Intro to RAG Systems webinar"), 1.0
        )

    def test_missing_gold_content_still_penalized(self):
        self.assertLess(field_sim("Meeting", "CS 314 Exam 1 review meeting"), 0.6)


if __name__ == "__main__":
    unittest.main()


class TestRecurrence(unittest.TestCase):
    def test_byday_order_and_key_order_ignored(self):
        self.assertEqual(rrule_key("RRULE:FREQ=WEEKLY;BYDAY=WE,MO"),
                         rrule_key("BYDAY=MO,WE;FREQ=WEEKLY"))

    def test_until_compares_on_date_only(self):
        self.assertEqual(rrule_key("RRULE:FREQ=WEEKLY;BYDAY=FR;UNTIL=20261204"),
                         rrule_key("RRULE:FREQ=WEEKLY;BYDAY=FR;UNTIL=20261204T235959Z"))
        self.assertNotEqual(rrule_key("RRULE:FREQ=WEEKLY;BYDAY=FR;UNTIL=20261204"),
                            rrule_key("RRULE:FREQ=WEEKLY;BYDAY=FR;UNTIL=20261211"))

    def test_default_interval_and_wkst_dropped(self):
        self.assertEqual(rrule_key("RRULE:FREQ=WEEKLY;INTERVAL=1;WKST=MO;BYDAY=TU"),
                         rrule_key("RRULE:FREQ=WEEKLY;BYDAY=TU"))
        self.assertNotEqual(rrule_key("RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=TU"),
                            rrule_key("RRULE:FREQ=WEEKLY;BYDAY=TU"))

    def test_different_days_or_missing_rule_fails(self):
        self.assertNotEqual(rrule_key("RRULE:FREQ=WEEKLY;BYDAY=TU"),
                            rrule_key("RRULE:FREQ=WEEKLY;BYDAY=TH"))
        self.assertIsNone(rrule_key(None))
        self.assertIsNone(rrule_key(""))
        gold = {**EVENT, "recurrence": "RRULE:FREQ=WEEKLY;BYDAY=TU"}
        self.assertFalse(score_pair({**EVENT, "recurrence": None}, gold)["recurrence"])
        self.assertTrue(score_pair({**EVENT, "recurrence": "FREQ=WEEKLY;BYDAY=TU"}, gold)["recurrence"])
