import unittest

from tdex.ui.text import pad, text_width, truncate, wrap


class TextTest(unittest.TestCase):
    def test_width(self):
        self.assertEqual(text_width("abc"), 3)
        self.assertEqual(text_width("Привет"), 6)
        self.assertEqual(text_width("日本"), 4)

    def test_truncate(self):
        self.assertEqual(truncate("Мониторинг", 6), "Монит…")
        self.assertEqual(truncate("abc", 3), "abc")
        self.assertEqual(truncate("日本語", 4), "日…")
        self.assertEqual(truncate("abc", 0), "")

    def test_pad(self):
        self.assertEqual(pad("ab", 4), "ab  ")
        self.assertEqual(text_width(pad("Очень длинная строка", 8)), 8)

    def test_wrap(self):
        self.assertEqual(wrap("один два три", 8), ["один два", "три"])
        self.assertEqual(wrap("один два три", 7), ["один", "два три"])
        self.assertEqual(wrap("a\n\nb", 10), ["a", "", "b"])
        self.assertEqual(wrap("abcdefghij", 4), ["abcd", "efgh", "ij"])
        for line in wrap("/very/long/path/to/some/file/name and words", 10):
            self.assertLessEqual(text_width(line), 10)


if __name__ == "__main__":
    unittest.main()
