"""The browser mode is presentation; only the patient selector changes identity.

These source-level guards complement the native two-container browser run.
They do not claim to verify layout, printing or clinical interpretation.
"""
from html.parser import HTMLParser
import re
import unittest

import support
from scholion import i18n


PAGE = support.SRC / 'scholion/web/index.html'


class HeaderParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.mode_parents = None
        self.stamps = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if attr.get('id') == 'display-mode':
            self.mode_parents = list(self.stack)
        if attr.get('id') in ('container-stamp', 'print-container-stamp'):
            self.stamps.append(attr['id'])
        if tag not in ('img', 'input', 'link', 'meta', 'br', 'hr'):
            self.stack.append((tag, attr.get('class', '')))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


class TestVisitMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = PAGE.read_text(encoding='utf-8')

    def test_the_mode_control_is_outside_the_legacy_fence(self):
        parser = HeaderParser()
        parser.feed(self.page)
        self.assertIsNotNone(parser.mode_parents)
        self.assertFalse(any('pico' in c.split() for _, c in parser.mode_parents))
        self.assertCountEqual(['container-stamp', 'print-container-stamp'], parser.stamps)
        self.assertIn('class="cr-segmented" role="group"', self.page)
        self.assertIn('type="radio" name="display-mode"', self.page)

    def test_mode_changes_no_server_or_patient_state(self):
        body = self.page.split('function setDisplayMode(mode,remount=true){', 1)[1].split('\n}', 1)[0]
        self.assertNotIn('post(', body)
        self.assertNotIn('/api/use', body)
        self.assertNotIn('loadPatients(', body)
        self.assertIn("sessionStorage.setItem('scholion-mode',mode)", body)
        self.assertIn('return mount(current)', body)

    def test_selection_is_visit_only_and_needs_more_than_one_container(self):
        self.assertIn("if(DISPLAY_MODE!=='clinician'||rows.length<2)", self.page)
        self.assertIn("post('/api/use',{id:e.target.value})", self.page)
        self.assertIn('renderContainerStamp(); renderPatients();', self.page)
        stamp = self.page.split('function renderContainerStamp(){', 1)[1].split('\n}', 1)[0]
        self.assertIn('active.id', stamp)
        self.assertIn("id:active&&active.id?active.id:'—'", stamp)
        self.assertIn('_version', stamp)
        self.assertNotIn('.label', stamp)

    def test_nav_order_keeps_the_existing_page_addresses(self):
        order = re.search(r'const NAV_ORDER=\[([^]]+)\]', self.page)
        self.assertIsNotNone(order)
        self.assertEqual([0, 1, 2, 4, 3, 5], [int(x) for x in order[1].split(',')])
        self.assertIn('register=register||DISPLAY_MODE', self.page)
        self.assertNotIn("+'&register=patient'", self.page)
        self.assertIn("b.setAttribute('aria-current','page')", self.page)

    def test_both_languages_name_modes_and_the_technical_stamp(self):
        previous = i18n.lang()
        self.addCleanup(i18n.set_lang, previous)
        for language in i18n.available():
            i18n.set_lang(language)
            with self.subTest(language=language):
                for key in ('web.mode.label', 'web.mode.personal', 'web.mode.visit', 'web.mode.today'):
                    self.assertNotIn('⟦', i18n.t(key))
                stamp = i18n.t('web.header.container_stamp', id='SYNTHETIC_ID', version='0.6.0')
                self.assertIn('SYNTHETIC_ID', stamp)
                self.assertIn('0.6.0', stamp)


if __name__ == '__main__':
    unittest.main()
