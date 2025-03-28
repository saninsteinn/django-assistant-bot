import pytest

from assistant.utils.language import has_cjk_characters


@pytest.mark.parametrize("input_str,expected", [
    # Positive cases (should return True)
    ("漢字", True),  # Chinese characters
    ("こんにちは", True),  # Japanese hiragana
    ("カタカナ", True),  # Japanese katakana
    ("한글", True),  # Korean hangul
    ("Hello 你好", True),  # Mix of Latin and Chinese
    ("ＨＥＬＬＯ", True),  # Symbols of full width (FF00-FFEF)
    ("\u4e00", True),  # Boundary value: start of CJK Unified Ideographs
    ("\u9fff", True),  # Boundary value: end of CJK Unified Ideographs
    ("\u3400", True),  # Start of CJK Extension A
    ("\u4DBF", True),  # End of CJK Extension A
    # real examples:
    ("Привет!很高兴见到你。有什么可以帮助你的吗？", True),
    ("Я可以帮助您处理订单相关的问题，包括查询订单状态、取消订单或向骑手留言。请告诉我您的具体需求。", True),
    ("Хорошо,谢谢 за интерес! Как я могу вам помочь?", True),
    ("Спасибо за ваш вопрос! Я хорошо,谢谢. Как я могу вам помочь с вашим заказом?", True),
    ("您好！我目前的任务是帮助您处理与"Dixy"订单相关的问题，具体包括以下几种方式：", True),
    ("Вы можете问我 о статусе вашего заказа", True),

    # Negative cases (should return False)
    ("", False),  # Empty string
    ("Hello World", False),  # Only Latin
    ("Привет", False),  # Cyrillic
    ("12345!@#", False),  # Digits and special characters
    ("αβγδε", False),  # Greek letters
    ("😀🎉", False),  # Emojis
    ("Привет! 👋 Я ваш новый виртуальный ассистент", False),
])
def test_has_cjk_characters(input_str, expected):
    assert has_cjk_characters(input_str) == expected
