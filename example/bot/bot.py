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
    """
    A bot for managing tasks. Supports creating and listing tasks.
    """

    async def get_answer_to_messages(self, messages, debug_info, do_interrupt) -> Answer:
        """
        Process incoming messages and return appropriate response.

        :param messages: List of message dictionaries containing the conversation history
        :param debug_info: Dictionary for storing debug information
        :param do_interrupt: Function to check if processing should be interrupted
        :return: Response to the user's message
        :rtype: Answer
        """
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
        """
        Classify the user's intent based on their message.

        :param messages: List of message dictionaries containing the conversation history
        :param debug_info: Dictionary for storing debug information
        :return: Classified intent tag (#create_task, #list_tasks, or #other)
        :rtype: str
        """
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

        :param result: The classification response from the AI
        :type result: str
        :return: True if the result contains a valid classification tag, False otherwise
        :rtype: bool
        """
        valid_intents = ['#create_task', '#list_tasks', '#other']
        return any(intent in result for intent in valid_intents)

    def _clean_thinking(self, result: str) -> str:
        """
        Extract the classification tag from the AI response, removing any reasoning or additional text.

        :param result: The raw classification response from the AI
        :type result: str
        :return: The extracted classification tag
        :rtype: str
        """
        for intent in ['#create_task', '#list_tasks', '#other']:
            if intent in result:
                return intent
        return '#other'  # Default fallback

    async def initiate_task_creation(self):
        """
        Start the task creation process.

        :return: Prompt for the task name
        :rtype: SingleAnswer
        """
        await self.update_state({
            'awaiting_input': 'task_title',
            'new_task': {}
        })
        return SingleAnswer(
            "📝 Enter task name:",
            buttons=[[Button('Cancel', callback_data='/cancel')]]
        )

    async def handle_state_input(self, messages, debug_info):
        """
        Handle user input based on the current state of task creation.

        :param messages: List of message dictionaries containing the conversation history
        :param debug_info: Dictionary for storing debug information
        :return: Response based on the current state and user input
        :rtype: Answer
        """
        last_message = messages[-1]['content']

        if self.instance.state['awaiting_input'] == 'task_title':
            await self.update_state({
                'awaiting_input': 'task_priority',
                'new_task': {'title': last_message}
            })

            return SingleAnswer(
                "Choose priority:",
                buttons=[
                    [Button('❗High', callback_data='/priority high')],
                    [Button('🔰 Medium', callback_data='/priority medium')],
                    [Button('🐌 Low', callback_data='/priority low')]
                ]
            )

        return SingleAnswer("Invalid state", no_store=True)

    @AssistantBot.command('/priority (high|medium|low)')
    async def set_priority(self, match: re.Match, message_id: Optional[str] = None):
        """
        Handle priority selection for a task.

        :param match: Regex match object containing the selected priority
        :type match: re.Match
        :param message_id: Optional message ID
        :type message_id: Optional[str]
        :return: Confirmation of priority selection and task creation prompt
        :rtype: MultiPartAnswer
        """
        if self.instance.state.get('awaiting_input') != 'task_priority':
            return SingleAnswer("Invalid operation state")

        priority = match.group(1)
        task_data = self.instance.state['new_task']
        task_data['priority'] = priority

        await self.update_state({
            'awaiting_input': 'confirming',
            'new_task': task_data
        })

        return MultiPartAnswer([
            SingleAnswer(f"Selected priority: {priority}"),
            await self._confirm_task_creation()
        ])

    async def _confirm_task_creation(self):
        """
        Create confirmation message for task creation.

        :return: Task creation confirmation prompt with buttons
        :rtype: SingleAnswer
        """
        task = self.instance.state['new_task']
        return SingleAnswer(
            f"Create task?\n{task['title']} ({task['priority']} priority)",
            buttons=[
                [Button('✅ Confirm', callback_data='/confirm_task')],
                [Button('❌ Cancel', callback_data='/cancel')]
            ]
        )

    @AssistantBot.command('/confirm_task')
    async def finalize_task(self, match: Optional[re.Match] = None, message_id: Optional[str] = None):
        """
        Finalize task creation after user confirmation.

        :param match: Optional regex match object
        :type match: Optional[re.Match]
        :param message_id: Optional message ID
        :type message_id: Optional[str]
        :return: Task creation success message and next action buttons
        :rtype: MultiPartAnswer
        """
        if self.instance.state.get('awaiting_input') != 'confirming':
            return SingleAnswer("Invalid operation state")

        task = self.instance.state['new_task']
        logger.info(f"Creating task: {task}")

        # Store the task in the state
        tasks = self.instance.state.get('tasks', [])
        tasks.append(task)
        await self.update_state({'tasks': tasks})

        # Clear the task creation state
        await self.update_state({
            'awaiting_input': None,
            'new_task': None
        })

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
        """
        Handle general queries that don't match specific intents.

        :param messages: List of message dictionaries containing the conversation history
        :param debug_info: Dictionary for storing debug information
        :return: AI-generated response to the query
        :rtype: SingleAnswer
        """
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
        """
        Cancel the current operation and clear state.

        :param match: Optional regex match object
        :type match: Optional
        :param message_id: Optional message ID
        :type message_id: Optional
        :return: Operation cancelled message with main menu button
        :rtype: SingleAnswer
        """
        await self.clear_state()
        return SingleAnswer(
            "❌ Operation cancelled",
            buttons=[[Button('Main menu', callback_data='/start')]]
        )

    @AssistantBot.command('/start')
    async def command_start(self, *args, **kwargs):
        """
        Handle the start command.

        :return: Welcome message and main menu buttons
        :rtype: MultiPartAnswer
        """
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
        """
        Handle the list command.

        :return: Task list display
        :rtype: Answer
        """
        return await self.show_task_list()

    async def show_task_list(self):
        """
        Display the list of tasks.

        :return: Task list with action buttons
        :rtype: SingleAnswer
        """
        # Initialize tasks list if not present
        tasks = self.instance.state.get('tasks', [])

        if not tasks:
            task_list_text = "📋 Task list:\n\nCurrently, the task list is empty."
        else:
            task_list_text = "📋 Task list:\n\n"
            for i, task in enumerate(tasks, 1):
                priority_icon = {
                    'high': '❗',
                    'medium': '🔰',
                    'low': '🐌'
                }.get(task['priority'], '')

                task_list_text += f"{i}. {task['title']} {priority_icon}\n"

        return SingleAnswer(
            task_list_text,
            buttons=[
                [Button('➕ New task', callback_data='/new_task')],
                [Button('🏠 Main menu', callback_data='/start')]
            ]
        )

    @AssistantBot.command('/help')
    async def command_help(self, *args, **kwargs):
        """
        Handle the help command.

        :return: Help message with available commands and action buttons
        :rtype: SingleAnswer
        """
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

    @AssistantBot.command('/new_task')
    async def command_new_task(self, *args, **kwargs):
        """
        Handle the new task command.

        :return: Start task creation process
        :rtype: Answer
        """
        return await self.initiate_task_creation()
