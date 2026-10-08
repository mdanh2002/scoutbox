from bs4 import BeautifulSoup
from django.test import SimpleTestCase

from portal.services.tracking import (
    _page_title_from_soup,
    article_title_needs_refresh,
    clean_article_title,
)


class Release01191TrackingTitleTests(SimpleTestCase):
    def test_markdown_link_title_is_not_presented_as_a_title(self):
        value='[Pictts](https://toughdev.com/blog/pictts)'
        self.assertEqual(clean_article_title(value),'Pictts')
        self.assertTrue(article_title_needs_refresh(value))

    def test_link_shaped_html_title_prefers_page_metadata(self):
        soup=BeautifulSoup(
            '<html><head><title>[Pictts](https://toughdev.com/blog/pictts)</title>'
            '<meta property="og:title" content="PIC Text-to-Speech on Embedded Hardware"></head>'
            '<body><h1>Fallback heading</h1></body></html>',
            'html.parser',
        )
        self.assertEqual(_page_title_from_soup(soup),'PIC Text-to-Speech on Embedded Hardware')

    def test_repeated_markdown_metadata_is_skipped_for_real_heading(self):
        placeholder='[Pictts](https://toughdev.com/blog/pictts)'
        soup=BeautifulSoup(
            f'<html><head><title>{placeholder}</title>'
            f'<meta property="og:title" content="{placeholder}">'
            f'<meta name="twitter:title" content="{placeholder}"></head>'
            '<body><h1>PIC Text-to-Speech on Embedded Hardware</h1></body></html>',
            'html.parser',
        )
        self.assertEqual(_page_title_from_soup(soup),'PIC Text-to-Speech on Embedded Hardware')

    def test_normal_html_title_remains_primary(self):
        soup=BeautifulSoup(
            '<html><head><title>Primary Document Title</title>'
            '<meta property="og:title" content="Secondary title"></head><body></body></html>',
            'html.parser',
        )
        self.assertEqual(_page_title_from_soup(soup),'Primary Document Title')
