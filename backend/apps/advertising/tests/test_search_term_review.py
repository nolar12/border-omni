from django.test import SimpleTestCase

from apps.advertising.services.search_term_review_service import find_irrelevant_terms


def _term(text, match_type='BROAD', clicks=0, impressions=0, cost=0.0):
    return {'search_term': text, 'match_type': match_type, 'clicks': clicks, 'impressions': impressions, 'cost': cost}


class FindIrrelevantTermsTests(SimpleTestCase):
    def test_flags_broad_term_without_breed_that_got_clicks(self):
        found = find_irrelevant_terms([_term('filhotes mais lindos do mundo', clicks=5, cost=4.0)])
        self.assertEqual([t['search_term'] for t in found], ['filhotes mais lindos do mundo'])

    def test_never_flags_terms_mentioning_the_breed_even_misspelled(self):
        terms = [
            _term('cachorro border collie', clicks=3), _term('bordr colie filhote', clicks=2),
            _term('bordercollie preço', clicks=2), _term('golden collie', clicks=2),
        ]
        self.assertEqual(find_irrelevant_terms(terms), [])

    def test_ignores_non_broad_matches(self):
        self.assertEqual(find_irrelevant_terms([_term('cachorro', match_type='EXACT', clicks=3)]), [])

    def test_needs_a_click_or_enough_impressions(self):
        self.assertEqual(find_irrelevant_terms([_term('cachorro', impressions=3)]), [])
        self.assertEqual(len(find_irrelevant_terms([_term('cachorro', impressions=2555)])), 1)

    def test_skips_already_negated_and_aggregates_duplicates(self):
        terms = [_term('cachorro', clicks=1, cost=1.0), _term('cachorro', clicks=2, cost=2.0), _term('filhotes a venda', clicks=1)]
        found = find_irrelevant_terms(terms, already_negated={'filhotes a venda'})
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0]['clicks'], found[0]['cost']), (3, 3.0))
