import logging
import re
from typing import Optional

from assistant.ai.domain import AIResponse
from assistant.ai.providers.base import AIDebugger
from assistant.bot.domain import SingleAnswer, MultiPartAnswer, Button
from assistant.bot.assistant_bot import AssistantBot
from assistant.utils.repeat_until import repeat_until

from assistant.bot.domain import Answer
from assistant.bot.services.context_service.utils import add_system_message

logger = logging.getLogger(__name__)


class TaskManagerBot(AssistantBot):
    async def get_answer_to_messages(self, messages, debug_info, do_interrupt) -> Answer:
        if self.instance.state.get('awaiting_input'):
            return await self.handle_state_input(messages, debug_info)

        category = await self._classify_intent(messages, debug_info)

        if category == '#create_task':
            return await self.initiate_task_creation()
        elif category == '#list_tasks':
            return await self.show_task_list()
        else:
            return await self.handle_general_query(messages, debug_info)

    async def _classify_intent(self, messages, debug_info) -> str:
        with AIDebugger(self._fast_ai, debug_info, 'intent_classification') as debugger:
            system_msg = """Классифицируй запрос:
            #create_task - создание новой задачи
            #list_tasks - запрос списка задач
            #other - другие запросы"""

            response = await repeat_until(
                debugger.ai.get_response,
                add_system_message(messages, system_msg),
                condition=lambda r: self._validate_classification(r.result),
                max_attempts=5
            )

            intent = self._clean_thinking(response.result).strip()
            debugger.info['detected_intent'] = intent
            return intent

    async def initiate_task_creation(self):
        await self.update_state({
            'awaiting_input': 'task_title',
            'new_task': {}
        })
        return SingleAnswer(
            "📝 Введите название задачи:",
            buttons=[Button('Отмена', callback_data='/cancel')]
        )

    async def handle_state_input(self, messages, debug_info):
        state = self.instance.state
        last_message = messages[-1]['content']

        if state['awaiting_input'] == 'task_title':
            state['new_task']['title'] = last_message
            state['awaiting_input'] = 'task_priority'

            await self.update_state(state)
            return SingleAnswer(
                "Выберите приоритет:",
                buttons=[
                    Button('❗Высокий', callback_data='/priority high'),
                    Button('🔰 Средний', callback_data='/priority medium'),
                    Button('🐌 Низкий', callback_data='/priority low')
                ]
            )

        elif state['awaiting_input'] == 'task_priority':
            return SingleAnswer(
                "✅ Задача успешно создана!",
                no_store=True
            )

    @AssistantBot.command('/priority (high|medium|low)')
    async def set_priority(self, match: re.Match):
        priority = match.group(1)
        self.instance.state['new_task']['priority'] = priority
        await self.update_state(self.instance.state)

        return MultiPartAnswer([
            SingleAnswer(f"Выбран приоритет: {priority}"),
            await self._confirm_task_creation()
        ])

    async def _confirm_task_creation(self):
        task = self.instance.state['new_task']
        return SingleAnswer(
            f"Создать задачу?\n{task['title']} ({task['priority']} приоритет)",
            buttons=[
                Button('✅ Подтвердить', callback_data='/confirm_task'),
                Button('❌ Отмена', callback_data='/cancel')
            ]
        )

    @AssistantBot.command('/confirm_task')
    async def finalize_task(self):
        task = self.instance.state['new_task']
        logger.info(f"Creating task: {task}")
        await self.clear_state()

        return MultiPartAnswer([
            SingleAnswer("🎉 Задача создана!"),
            SingleAnswer(
                "Что дальше?",
                buttons=[
                    Button('➕ Новая задача', callback_data='/new_task'),
                    Button('📋 Список задач', callback_data='/list')
                ]
            )
        ])

    async def handle_general_query(self, messages, debug_info):
        with AIDebugger(self._strong_ai, debug_info, 'general_response') as debugger:
            response = await repeat_until(
                debugger.ai.get_response,
                messages,
                max_attempts=3,
                condition=lambda r: len(r.result) < 500
            )

            formatted_response = f"🤖 {response.result}"
            debugger.info['response_metrics'] = {
                'length': len(formatted_response),
                'contains_emoji': '✅' if '🤖' in formatted_response else '❌'
            }

        return SingleAnswer(formatted_response)

    @AssistantBot.command('/cancel')
    async def cancel_operation(self):
        await self.clear_state()
        return SingleAnswer(
            "❌ Операция отменена",
            buttons=[Button('Главное меню', callback_data='/start')]
        )

    @AssistantBot.command('/start')
    async def command_start(self, *args, **kwargs):
        return MultiPartAnswer([
            SingleAnswer("🖖 Добро пожаловать в TaskBot!"),
            SingleAnswer(
                "Выберите действие:",
                buttons=[
                    [Button('➕ Новая задача', callback_data='/new_task')],
                    [Button('📋 Мои задачи', callback_data='/list')],
                    [Button('❓ Помощь', callback_data='/help')]
                ]
            )
        ])
