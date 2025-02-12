import pytest

from assistant.utils.language import has_cjk_characters


@pytest.mark.parametrize("input_str,expected", [
    # Позитивные случаи (должны возвращать True)
    ("漢字", True),  # Китайские иероглифы
    ("こんにちは", True),  # Японские хирагана
    ("カタカナ", True),  # Японские катакана
    ("한글", True),  # Корейский хангыль
    ("Hello 你好", True),  # Смесь латиницы и китайского
    ("ＨＥＬＬＯ", True),  # Символы полной ширины (FF00-FFEF)
    ("\u4e00", True),  # Граничное значение: начало CJK Unified Ideographs
    ("\u9fff", True),  # Граничное значение: конец CJK Unified Ideographs
    ("\u3400", True),  # Начало CJK Extension A
    ("\u4DBF", True),  # Конец CJK Extension A
    # реальные примеры:
    ("Привет!很高兴见到你。有什么可以帮助你的吗？", True),
    ("Я可以帮助您处理订单相关的问题，包括查询订单状态、取消订单或向骑手留言。请告诉我您的具体需求。", True),
    ("Хорошо,谢谢 за интерес! Как я могу вам помочь?", True),
    ("Спасибо за ваш вопрос! Я хорошо,谢谢. Как я могу вам помочь с вашим заказом?", True),
    ("您好！我目前的任务是帮助您处理与“Dixy”订单相关的问题，具体包括以下几种方式：", True),
    ("Вы можете问我 о статусе вашего заказа", True),

    # Негативные случаи (должны возвращать False)
    ("", False),  # Пустая строка
    ("Hello World", False),  # Только латиница
    ("Привет", False),  # Кириллица
    ("12345!@#", False),  # Цифры и спецсимволы
    ("αβγδε", False),  # Греческие буквы
    ("😀🎉", False),  # Эмодзи
    ("Привет! 👋 Я ваш новый виртуальный ассистент", False),
])
def test_has_cjk_characters(input_str, expected):
    assert has_cjk_characters(input_str) == expected
