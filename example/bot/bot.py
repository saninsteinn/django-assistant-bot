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
            system_msg = """Classify the user request above:
            #create_task - creating a new task
            #list_tasks - request task list
            #other - other requests"""

            response = await repeat_until(
                debugger.ai.get_response,
                add_system_message(messages, system_msg),
                condition=lambda r: self._validate_classification(r.result),
                max_attempts=5
            )

            intent = self._clean_thinking(response.result).strip()
            debugger.info['messages'] = messages
            debugger.info['detected_intent'] = intent
            return intent

    def _validate_classification(self, result: str) -> bool:
        """
        Validate that the classification result contains one of the expected intent tags.

        Args:
            result: The classification response from the AI

        Returns:
            bool: True if the result contains a valid classification tag, False otherwise
        """
        valid_intents = ['#create_task', '#list_tasks', '#other']
        return any(intent in result for intent in valid_intents)

    def _clean_thinking(self, result: str) -> str:
        """
        Extract the classification tag from the AI response, removing any reasoning or additional text.

        Args:
            result: The raw classification response from the AI

        Returns:
            str: The extracted classification tag
        """
        for intent in ['#create_task', '#list_tasks', '#other']:
            if intent in result:
                return intent
        return '#other'  # Default fallback

    async def initiate_task_creation(self):
        await self.update_state({
            'awaiting_input': 'task_title',
            'new_task': {}
        })
        return SingleAnswer(
            "📝 Enter task name:",
            buttons=[[Button('Cancel', callback_data='/cancel')]]
        )

    async def handle_state_input(self, messages, debug_info):
        state = self.instance.state
        last_message = messages[-1]['content']

        if state['awaiting_input'] == 'task_title':
            state['new_task']['title'] = last_message
            state['awaiting_input'] = 'task_priority'

            await self.update_state(state)
            return SingleAnswer(
                "Choose priority:",
                buttons=[
                    [Button('❗High', callback_data='/priority high')],
                    [Button('🔰 Medium', callback_data='/priority medium')],
                    [Button('🐌 Low', callback_data='/priority low')]
                ]
            )

        elif state['awaiting_input'] == 'task_priority':
            return SingleAnswer(
                "✅ Task created successfully!",
                no_store=True
            )

    @AssistantBot.command('/priority (high|medium|low)')
    async def set_priority(self, match: re.Match):
        priority = match.group(1)
        self.instance.state['new_task']['priority'] = priority
        await self.update_state(self.instance.state)

        return MultiPartAnswer([
            SingleAnswer(f"Selected priority: {priority}"),
            await self._confirm_task_creation()
        ])

    async def _confirm_task_creation(self):
        task = self.instance.state['new_task']
        return SingleAnswer(
            f"Create task?\n{task['title']} ({task['priority']} priority)",
            buttons=[
                [Button('✅ Confirm', callback_data='/confirm_task')],
                [Button('❌ Cancel', callback_data='/cancel')]
            ]
        )

    @AssistantBot.command('/confirm_task')
    async def finalize_task(self):
        task = self.instance.state['new_task']
        logger.info(f"Creating task: {task}")
        await self.clear_state()

        return MultiPartAnswer([
            SingleAnswer("🎉 Task created!"),
            SingleAnswer(
                "What's next?",
                buttons=[
                    [Button('➕ New task', callback_data='/new_task')],
                    [Button('📋 Task list', callback_data='/list')]
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
    async def cancel_operation(self, match=None, message_id=None):
        await self.clear_state()
        return SingleAnswer(
            "❌ Operation cancelled",
            buttons=[[Button('Main menu', callback_data='/start')]]
        )

    @AssistantBot.command('/start')
    async def command_start(self, *args, **kwargs):
        return MultiPartAnswer([
            SingleAnswer("🖖 Welcome to TaskBot!"),
            SingleAnswer(
                "Choose action:",
                buttons=[
                    [Button('➕ New task', callback_data='/new_task')],
                    [Button('📋 My tasks', callback_data='/list')],
                    [Button('❓ Help', callback_data='/help')]
                ]
            )
        ])

    @AssistantBot.command('/list')
    async def command_list(self, *args, **kwargs):
        return await self.show_task_list()

    async def show_task_list(self):
        return SingleAnswer(
            "📋 Task list:\n\n"
            "Currently, the task list is empty.",
            buttons=[
                [Button('➕ New task', callback_data='/new_task')],
                [Button('🏠 Main menu', callback_data='/start')]
            ]
        )

    @AssistantBot.command('/help')
    async def command_help(self, *args, **kwargs):
        return SingleAnswer(
            "🤖 *TaskBot - Task Management*\n\n"
            "📝 *Commands:*\n\n"
            "• /new_task - Create a task\n"
            "• /list - Task list\n"
            "• /cancel - Cancel operation\n"
            "• /start - Main menu",
            buttons=[
                [Button('🏠 Main menu', callback_data='/start')],
                [Button('➕ New task', callback_data='/new_task')]
            ]
        )
