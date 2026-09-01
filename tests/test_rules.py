import unittest

from aquant_limitup.rules import is_main_board, limit_down_price, limit_up_price


class RuleTests(unittest.TestCase):
    def test_main_board_codes(self):
        self.assertTrue(is_main_board("000001"))
        self.assertTrue(is_main_board("002185"))
        self.assertTrue(is_main_board("600000"))
        self.assertFalse(is_main_board("300001"))
        self.assertFalse(is_main_board("688001"))
        self.assertFalse(is_main_board("920001"))

    def test_price_limit_round_half_up(self):
        self.assertEqual(limit_up_price(10.05), 11.06)
        self.assertEqual(limit_down_price(10.05), 9.05)
        self.assertEqual(limit_up_price(10.05, is_st=True), 10.55)


if __name__ == "__main__":
    unittest.main()

