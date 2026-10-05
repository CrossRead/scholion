"""Review requests retain refusals, gaps and the author's next action."""
import unittest

import support  # noqa: F401
from scholion import format_views


class TestBriefReviewRendering(unittest.TestCase):
    def test_a_refusal_is_not_printed_as_an_empty_success(self):
        rendered = format_views.brief_review_report({'ok': False, 'message': 'Unreadable source'})
        self.assertIn('Unreadable source', rendered)
        self.assertTrue(rendered.startswith('✗'))

    def test_a_block_without_new_points_keeps_the_request_and_hint(self):
        rendered = format_views.brief_review_report({'ok': True, 'blocks': [{
            'id': 'example', 'title': 'Synthetic block', 'markers': [],
            'review_hint': 'Check the source before rewriting',
            'request': 'Review this synthetic block',
        }]})
        self.assertIn('Synthetic block', rendered)
        self.assertIn('Check the source before rewriting', rendered)
        self.assertIn('Review this synthetic block', rendered)
        self.assertNotIn('None', rendered)

    def test_focus_keeps_closed_steps_open_questions_and_evidence_limits(self):
        rendered = format_views.render_focus({
            'available': True, 'title': 'Synthetic focus', 'started': '2026-01-01',
            'tracks': [{'title': 'Synthetic track', 'owner': 'person', 'state': 'In progress',
                        'closed_today': ['Synthetic completed step'],
                        'next': ['Synthetic next step']}],
            'evidence': {'count': 1, 'studies': [{
                'date': '2026-01-02', 'kind': 'synthetic', 'conclusion': 'Synthetic observation',
                'answers': ['Synthetic answered question'],
                'does_not_answer': ['Synthetic unanswered question'],
            }], 'open': [{'what': 'Synthetic gap', 'note': 'Still unknown', 'from': 'fixture'}]},
            'questions': ['Free-form question', {'to': 'clinician', 'text': 'Structured question'}],
            'disclaimer': 'Synthetic fixture; no clinical conclusion',
        })
        for text in ('Synthetic completed step', 'Synthetic next step', 'Synthetic observation',
                     'Synthetic answered question', 'Synthetic unanswered question',
                     'Synthetic gap', 'Still unknown', 'Free-form question', 'Structured question',
                     'Synthetic fixture; no clinical conclusion'):
            self.assertIn(text, rendered)
        self.assertIn('✗', rendered)
