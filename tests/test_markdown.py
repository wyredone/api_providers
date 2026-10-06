import unittest
from unittest.mock import Mock
from api_providers.ui.markdown import blocks, code_blocks, inline, insert


class MarkdownTests(unittest.TestCase):
    def test_heading_bold_italic_inline_code(self):
        self.assertIn(('heading', 'Title\n'), list(blocks('# Title\n')))
        parts = list(inline('**bold** *italic* `code`'))
        self.assertIn(('bold', 'bold'), parts)
        self.assertIn(('italic', 'italic'), parts)
        self.assertIn(('code', 'inline_code'), parts)

    def test_fenced_code_preserved_exactly(self):
        text = 'Text\n```python\nx = 1\nprint(x)\n```\n'
        self.assertEqual(code_blocks(text), [('python', 'x = 1\nprint(x)\n')])

    def test_tilde_fence_and_unclosed_code(self):
        self.assertEqual(code_blocks('~~~json\n{"a":1}\n~~~\n'), [('json', '{"a":1}\n')])
        self.assertEqual(code_blocks('```\npartial'), [('code', 'partial')])

    def test_links_are_only_display_text(self):
        self.assertEqual(list(inline('[site](https://example.com)')), [('site (https://example.com)', 'link')])
        widget = Mock()
        insert(widget, '<script>run()</script>\n![img](https://example.com/image.png)')
        self.assertTrue(widget.insert.called)
        # Renderer only inserts text; it does not execute markup or fetch URLs.
        self.assertEqual(set(call[0] for call in widget.method_calls), {'insert'})

    def test_code_has_distinct_tag(self):
        widget = Mock()
        insert(widget, '```python\nprint("hi")\n```')
        self.assertIn(unittest.mock.call('end', 'print("hi")\n', ('code',)), widget.insert.call_args_list)


if __name__ == '__main__':
    unittest.main()
