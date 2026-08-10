"""Unit tests for PdfValueFormatter."""

from pdf_probe.values import PdfValueFormatter
from tests.framework import UnitTestCase


class TestHumanize(UnitTestCase):
    def test_none(self):
        self.assertIsNone(PdfValueFormatter.humanize(None))

    def test_bool(self):
        self.assertEqual(PdfValueFormatter.humanize(True), "Yes")
        self.assertEqual(PdfValueFormatter.humanize(False), "No")

    def test_number(self):
        self.assertEqual(PdfValueFormatter.humanize(42), "42")
        self.assertEqual(PdfValueFormatter.humanize(3.14), "3.14")

    def test_string(self):
        self.assertEqual(PdfValueFormatter.humanize("hello"), "hello")
        self.assertEqual(PdfValueFormatter.humanize("  hello  world  "), "hello world")

    def test_list(self):
        self.assertEqual(PdfValueFormatter.humanize([1, 2, 3]), "1, 2, 3")

    def test_dict_xdefault(self):
        self.assertEqual(PdfValueFormatter.humanize({"x-default": "value"}), "value")

    def test_empty_dict_is_none(self):
        self.assertIsNone(PdfValueFormatter.humanize({}))


class TestPickFirst(UnitTestCase):
    def test_first_non_null_value(self):
        self.assertEqual(PdfValueFormatter.pick_first(None, "value", "other"), "value")
        self.assertEqual(PdfValueFormatter.pick_first(None, None, "value"), "value")

    def test_all_none(self):
        self.assertIsNone(PdfValueFormatter.pick_first(None, None, None))


class TestCountEntries(UnitTestCase):
    def test_none(self):
        self.assertEqual(PdfValueFormatter.count_entries(None), 0)

    def test_list(self):
        self.assertEqual(PdfValueFormatter.count_entries([1, 2, 3]), 3)

    def test_string(self):
        self.assertEqual(PdfValueFormatter.count_entries("hello"), 5)


class TestFormatDate(UnitTestCase):
    def test_plain_pdf_date(self):
        self.assertEqual(PdfValueFormatter.format_date("D:20240115120000"), "2024-01-15T12:00:00")

    def test_utc_pdf_date(self):
        self.assertEqual(
            PdfValueFormatter.format_date("D:20240115120000Z"), "2024-01-15T12:00:00+00:00"
        )

    def test_offset_pdf_date(self):
        self.assertEqual(
            PdfValueFormatter.format_date("D:20240115120000+02'00"),
            "2024-01-15T12:00:00+02:00",
        )

    def test_non_date_passthrough(self):
        self.assertEqual(PdfValueFormatter.format_date("not a date"), "not a date")


class TestDecodeBytes(UnitTestCase):
    def test_utf8_text(self):
        result = PdfValueFormatter.decode_bytes("héllo".encode("utf-8"))
        self.assertEqual(result["text"], "héllo")
        self.assertEqual(result["type"], "bytes")


class TestGetMappingValue(UnitTestCase):
    def test_returns_first_present_key(self):
        self.assertEqual(PdfValueFormatter.get_mapping_value({"a": 1, "b": 2}, "c", "b"), 2)

    def test_non_dict_returns_none(self):
        self.assertIsNone(PdfValueFormatter.get_mapping_value(None, "a"))


class TestNormalize(UnitTestCase):
    def test_self_referential_dict_is_short_circuited(self):
        cyclic: dict = {"name": "root"}
        cyclic["self"] = cyclic

        result = PdfValueFormatter.normalize(cyclic)

        self.assertEqual(result["self"], "<already-shown-elsewhere>")

    def test_shared_object_reached_from_many_branches_is_not_reexpanded(self):
        # Mirrors a PDF where many pages all reference the same resource
        # (e.g. a font) rather than each holding their own copy. Dedup must
        # be global, not per-path, or fan-out across branches that all
        # reach the same object makes traversal blow up combinatorially.
        shared = {"kind": "font"}
        branches = [{"resources": shared, "index": i} for i in range(200)]
        root = {"pages": branches}

        result = PdfValueFormatter.normalize(root)

        resources_seen = [branch["resources"] for branch in result["pages"]]
        self.assertEqual(resources_seen[0], {"kind": "font"})
        self.assertTrue(all(entry == "<already-shown-elsewhere>" for entry in resources_seen[1:]))
