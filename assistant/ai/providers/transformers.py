import torch
from typing import List
from transformers import AutoTokenizer, AutoModelForCausalLM
from assistant.ai.providers.base import AIProvider
from assistant.ai.domain import Message, AIResponse
from assistant.ai.utils.transformers import get_torch_device


class TransformersProvider(AIProvider):

    def __init__(self, model_name: str):
        """
        Инициализирует локальную модель с заданным именем и максимальной длиной вывода.

        :param model_name: Имя модели в формате Hugging Face.
        """
        self._model_name = model_name
        self._tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
        self._device = get_torch_device()
        self._model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16, local_files_only=True).to(self._device)

    @property
    def context_size(self) -> int:
        return 8000  # TODO: get by model

    def calculate_tokens(self, text: str) -> int:
        """
        Вычисляет количество токенов в тексте.

        :param text: Входной текст.
        :return: Количество токенов.
        """
        return len(self._tokenizer.tokenize(text))

    async def get_response(
            self,
            messages: List[Message],
            max_tokens=1024,
            json_format: bool = False
    ) -> AIResponse:
        """
        Генерирует ответ на основе входных сообщений.

        :param messages: Список сообщений.
        :param max_tokens: Максимальное количество токенов для генерации.
        :param json_format: Форматирование JSON (опционально).
        :return: Ответ модели в формате AIResponse.
        """
        # Конкатенируем сообщения в единый prompt
        prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])

        # Токенизируем входные данные
        inputs = self._tokenizer(prompt, return_tensors="pt", truncation=True)
        input_ids = inputs.input_ids.to(self._device)

        # Генерируем ответ
        with torch.no_grad():
            outputs = self._model.generate(
                input_ids,
                attention_mask=inputs["attention_mask"],
                max_length=max_tokens,
                do_sample=True,
                top_p=0.95,
                top_k=50,
                pad_token_id=self._tokenizer.eos_token_id
            )

        # Декодируем результат и извлекаем только сгенерированную часть
        response_text = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
        response_content = response_text[len(prompt):].strip()

        # Parse the response as JSON if required
        if json_format:
            import json
            try:
                result = json.loads(response_content)
            except json.JSONDecodeError:
                # Handle parsing error (you may choose to raise an exception or return the raw string)
                result = response_content  # or you can set result = None or raise an exception
        else:
            result = response_content

        # Формируем ответ AIResponse
        ai_response = AIResponse(
            result=result,
            usage={
                'model': self._model_name,
                'prompt_tokens': len(inputs["input_ids"][0]),
                'completion_tokens': len(outputs[0]) - len(inputs["input_ids"][0]),
            },
            length_limited=(len(outputs[0]) >= max_tokens)
        )

        return ai_response
