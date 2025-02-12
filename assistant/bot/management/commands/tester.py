# Импорт необходимых библиотек и модулей
import argparse
from ftplib import all_errors

import itertools
import os
import asyncio
import logging
import json
import random
from datetime import timedelta
from typing import List

from django.core.management import BaseCommand

from assistant.bot.management.commands.utils import get_instance

from assistant.ai.dialog import AIDialog
from assistant.ai.domain import Message as AIMessage, system_message

from asgiref.sync import sync_to_async
from django.db.models import Max

from assistant.bot.models import Message
from assistant.bot.domain import Update, User, SingleAnswer, MultiPartAnswer, BotPlatform
from assistant.bot.utils import get_bot_class
from assistant.bot.services.dialog_service import get_dialog
from assistant.bot.services.instance_service import InstanceLockAsync
from assistant.bot.resource_manager import ResourceManager
from assistant.utils.repeat_until import repeat_until

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Папка для сохранения диалогов
DIALOGUES_FOLDER = 'test_dialogs'
TESTER_AI_MODEL = 'gpt-4o-mini'
ANALYZER_AI_MODEL = 'gpt-4o'#'gpt-4o-mini'


# Класс платформы для взаимодействия с ботом через AI
class AIDialogPlatform(BotPlatform):
    """Платформа для взаимодействия с ботом, используя AI-сгенерированные сообщения."""

    def __init__(self, bot_codename: str, dialog_log: List[dict]):
        self.bot_codename = bot_codename
        self.dialog_log = dialog_log  # Сохраняет историю диалога

    async def post_answer(self, chat_id: str, answer):
        if isinstance(answer, MultiPartAnswer):
            for part in answer.parts:
                self._log_single_answer(part)
        elif isinstance(answer, SingleAnswer):
            self._log_single_answer(answer)
        else:
            logger.error(f"Бот отправил неизвестный тип ответа: {answer}")

    def _log_single_answer(self, answer: SingleAnswer):
        # Логируем ответ бота
        log_entry = {"role": "assistant", "text": answer.text}
        if answer.buttons:
            log_entry['buttons'] = [
                [
                    {"text": button.text, "callback_data": button.callback_data, "url": button.url}
                    for button in row
                ]
                for row in answer.buttons
            ]
        if answer.reply_keyboard:
            log_entry['reply_keyboard'] = [
                [button for button in row]
                for row in answer.reply_keyboard
            ]
        self.dialog_log.append(log_entry)

    async def get_update(self, request):
        pass  # Не используется в этом контексте

    async def action_typing(self, chat_id):
        pass


class Command(BaseCommand):
    help = 'Интерактивное взаимодействие с ботом через консоль для отладки'

    def add_arguments(self, parser):
        parser.add_argument('command', type=str, choices=('run', 'analyze'), help='Команда для выполнения')
        parser.add_argument('bot_codename', type=str, help='Codename of the bot')
        parser.add_argument('-n', '--number', type=int, default=10, help='Number of dialogs to generate')

    def handle(self, *args, **options):
        if options['command'] == 'run':
            asyncio.run(
                self.run(*args, **options)
            )
        else:
            asyncio.run(
                self.analyze(*args, **options)
            )

    async def run(self, *args, **options):
        bot_codename = options['bot_codename']
        if not os.path.exists(DIALOGUES_FOLDER):
            os.makedirs(DIALOGUES_FOLDER)
        for i in range(options['number']):
            dialog_log = []  # Сохраняет диалог

            # Запускаем диалог
            await self.process_ai_dialog(bot_codename, dialog_log)

            # Сохраняем диалог в JSON файл
            dialog_file = os.path.join(DIALOGUES_FOLDER, f'dialog_{i + 1}.json')
            with open(dialog_file, 'w', encoding='utf-8') as w:
                json.dump(dialog_log, w, ensure_ascii=False, indent=2)

            logger.info(f'Dialog {i + 1} saved to {dialog_file}')

    async def process_ai_dialog(self, bot_codename: str, dialog_log: List[dict]):
        platform_codename = 'ai_platform'
        chat_id = 'tester'

        # Создаем объект пользователя
        user = User(
            id=chat_id,
            username='ai_tester',
            first_name='AI',
            last_name='Tester',
            language_code='ru',
        )

        # Используем кастомную платформу
        platform = AIDialogPlatform(bot_codename=bot_codename, dialog_log=dialog_log)

        # Получаем или создаем экземпляр бота
        instance = await sync_to_async(get_instance)(bot_codename, platform_codename, chat_id, user)

        # Получаем диалог
        dialog = await sync_to_async(get_dialog)(instance, timedelta(days=1))


        try:
            # Создаем экземпляр бота
            bot_cls = get_bot_class(bot_codename)
            bot = bot_cls(
                dialog=dialog,
                platform=platform,
            )

            max_message_id = await sync_to_async(
                lambda: Message.objects.filter(dialog=dialog).aggregate(Max('id'))['id__max'] or 0
            )()

            # Инициализируем AI диалоги для пользователя и контроля продолжения диалога
            ai_user_dialog = AIDialog(model=TESTER_AI_MODEL)
            ai_control_dialog = AIDialog(model=TESTER_AI_MODEL)

            conversation_active = True
            current_turn = 0
            max_turns = 10  # Максимальное количество ходов в диалоге

            while conversation_active and current_turn < max_turns:
                current_turn += 1

                # Подготовка истории диалога для AI
                dialog_messages = [
                    AIMessage(
                        role='user' if entry['role'] == 'assistant' else 'assistant',
                        content=entry['text']
                    )
                    for entry in dialog_log
                ]

                # Генерация сообщения пользователя с помощью AI
                user_prompt = system_message(
                    (
                        "You are a human interacting with a bot.\n"
                        # "Note that user's messages are actually generated by the bot.\n"
                        # "But you must answer as if you are a real human.\n"
                        # "In other words the `assistant` role and the `user` role change places.\n"
                        "You are characterized by the following traits:\n"
                        f"{self.generate_human_description()}\n"
                        f"You must randomly determine any other traits you have that may affect the current dialog.\n"
                        # "Please generate the next your message in the dialog.\n"
                        "Your first message must be \"/start\", but do not repeat it in subsequent messages.\n"
                        "If the bot asks your age, please respond with the following message:\n"
                        "\"/set_age is_over_18\"\n"
                        "You may end the conversation just saying goodbye with some words if it fits organically into the conversation.\n"
                    )
                )
                ai_response = await ai_user_dialog.get_response(
                    messages=[user_prompt] + dialog_messages,
                    max_tokens=150
                )
                user_message = ai_response.result.strip()

                # Логируем сообщение пользователя
                dialog_log.append({"role": "user", "text": user_message})

                update = Update(
                    chat_id=chat_id,
                    message_id=max_message_id + 1,
                    user=user,
                    text=user_message,
                )
                max_message_id += 1  # Увеличиваем ID сообщения

                async with InstanceLockAsync(instance):
                    try:
                        answer = await bot.handle_update(update)
                    except Exception as e:
                        logger.exception(f'Ошибка при обработке обновления: {e}')
                        resource_manager = ResourceManager(
                            codename=bot_codename,
                            language='ru',
                        )
                        error_message = resource_manager.get_phrase('Произошла ошибка при обработке вашего сообщения.')
                        answer = SingleAnswer(error_message, no_store=True)

                if answer:
                    try:
                        await platform.post_answer(chat_id, answer)
                    except Exception as e:
                        logger.exception(f'Ошибка при отправке ответа: {e}')
                        resource_manager = ResourceManager(
                            codename=bot_codename,
                            language='ru',
                        )
                        error_answer = SingleAnswer(resource_manager.get_phrase('Произошла ошибка при отправке ответа.'), no_store=True)
                        await platform.post_answer(chat_id, error_answer)
                    await bot.on_answer_sent(answer)

                if current_turn > 2:
                    # Решение о продолжении диалога
                    control_prompt = system_message(
                        "Based on the previous dialog, guess whether the user will continue the conversation or end it. Respond with \"continue\" or \"end\"."
                    )
                    ai_control_response = await repeat_until(
                        ai_control_dialog.get_response,
                        dialog_messages + [control_prompt],
                        max_tokens=10,
                        # json_format=True,
                        condition=lambda response: response.result.strip().lower() in ['continue', 'end']
                    )
                    end_decision = ai_control_response.result.strip().lower()
                    if 'end' in end_decision:
                        conversation_active = False
                    elif 'continue' in end_decision:
                        conversation_active = True
                    else:
                        # If the response is unclear, end the dialog by default
                        conversation_active = False
        finally:
            await sync_to_async(
                lambda: dialog.delete()
            )()

    def generate_human_description(self):
        personality_traits = {
            "language": ["russian"],
            "age group": ["young adult", "middle-aged", "elderly", "teenager"],
            "knowledge level": ["beginner", "intermediate", "expert", "enthusiast"],
            "communication preference": ["short", "detailed", "storytelling", "precise"],
            "tone preference": ["formal", "casual", "humorous", "serious"],
            "interest level": ["highly interested", "moderately interested", "curious but reserved",
                               "not very interested"],
            "openness to recommendations": ["open-minded", "skeptical", "enthusiastic", "resistant"],
            "typical mood": ["cheerful", "thoughtful", "relaxed", "serious", "adventurous"],
            "preference for stories": ["enjoys historical context", "interested in technical details",
                                       "cares about practical applications", "likes personal anecdotes"],
            "politeness": ["very polite", "neutral", "blunt", "jokingly rude"],
            "use of humor": ["frequent", "occasional", "none", "dry wit"],
            "regional preferences": ["local interests", "international topics", "rare subjects", "classic themes"],
            "openness to new ideas": ["welcomes", "skeptical", "reluctant", "eager"],
            "preference for terminology": ["technical terms", "layman's terms", "balanced mix", "avoids jargon"],
            "interaction style": ["asks many questions", "mostly listens", "engages equally", "seeks approval"],
            "emotional state during interactions": ["calm", "excited", "nervous", "apathetic"],
            "formality level in communication": ["highly formal", "semi-formal", "casual"],
            "use of cultural references": ["likes pop culture", "interested in historical references",
                                           "regional customs", "no specific preference"],
            "engagement with assistant": ["frequent", "occasional", "rare"],
            "interest in events (e.g., workshops)": ["high", "medium", "low"],
            "sensitivity to details": ["sensitive", "neutral", "prefers high-level overview"],
            "interest in related topics": ["high interest", "medium interest", "low interest"],
            "preferred method of learning": ["hands-on experience", "reading descriptions", "storytelling",
                                             "scientific details"]
        }

        personality_profile = {
            key: random.choice(value)
            for key, value in personality_traits.items()
        }

        personality_profile_str = '- ' + '\n- '.join(
            [f"{key}: {value}" for key, value in personality_profile.items()])
        return personality_profile_str

    async def analyze(self, *args, **options):
        dialog_files = sorted(
            [
                f
                for f in os.listdir(DIALOGUES_FOLDER)
                if f.startswith('dialog_') and f.endswith('.json')
            ],
            key=lambda x: int(x.split('_')[1].split('.')[0])
        )
        analysis_results = []
        ai_analyzer = AIDialog(model=ANALYZER_AI_MODEL)
        ai_improvement = AIDialog(model=ANALYZER_AI_MODEL)

        for dialog_file in dialog_files:
            dialog_path = os.path.join(DIALOGUES_FOLDER, dialog_file)
            with open(dialog_path, 'r', encoding='utf-8') as f:
                dialog_log = json.load(f)

            # Formatting dialog for AI
            dialog_text = ''
            for entry in dialog_log:
                role = entry.get('role')
                text = entry.get('text')
                if role == 'user':
                    dialog_text += f"User: {text}\n"
                elif role == 'assistant':
                    dialog_text += f"Bot: {text}\n"

            # Preparing prompt for AI dialog analysis
            ai_prompt = (
                "You are a professional chatbot quality assurance expert.\n"
                "Please analyze the following conversation between a user and the bot, identifying areas for bot improvement to enhance the interaction quality.\n"
                "Focus on:\n"
                "- Linguistic issues (e.g., grammatical errors, incorrect punctuation, inconsistent or awkward formatting).\n"
                "- Contextual issues where the bot misunderstood the question, provided irrelevant or confusing responses, or conveyed incorrect information.\n"
                "- Problems with tone and style if the bot sounds unnatural, rude, or overly formal/informal in context.\n"
                "- Missed opportunities to offer helpful or logical next steps in the conversation.\n"
                "Separate the deficiencies into `warnings` and `errors` categories.\n"
                "Provide a list of identified deficiencies, categorized as `warnings` or `errors`, or an empty list if no issues are found.\n"
                "Formulate them in Russian, using clear and concise language.\n"
                "Each point should be supported by a specific example (with quotes if possible) from the dialogue.\n"
                "Don't be afraid to leave lists empty if the dialogue looks high-quality and natural in terms of user expectations.\n"
                "Please note the following explanations for the following dialogue:\n"
                "- Message `/start` is technical and means the user starts the conversation first time\n"
                "- Message `/set_age is_over_18` is technical and means the user confirms that he is over 18 years old pressing the button\n"
                "Here is the conversation:\n"
                f"{dialog_text}\n"
                f"Answer with a JSON response that strictly matches the following example:\n"
                f"```json\n"
                f"{{\n"
                f"  \"warnings\": ["
                f"    \"...\",\n"
                f"    \"...\"\n"
                f"    ..."
                f"  ]\n,"
                f"  \"errors\": ["
                f"    \"...\",\n"
                f"    \"...\"\n"
                f"    ..."
                f"  ]\n"
                f"}}\n"
                f"```\n"
            )

            # Getting AI response for dialog analysis
            ai_response = await repeat_until(
                ai_analyzer.get_response,
                messages=[system_message(ai_prompt)],
                max_tokens=1024,
                json_format=True,
                condition=lambda response: isinstance(response.result, dict) and isinstance(response.result.get('warnings'), List | None) and isinstance(response.result.get('errors'), List | None)
            )

            warnings = ai_response.result.get('warnings', [])
            errors = ai_response.result.get('errors', [])
            crashes = dialog_text.count('An error occurred ')

            analysis_results.append(
                {
                    'dialog_file': dialog_file,
                    'warnings': warnings,
                    'errors': errors,
                    'crashes': crashes
                }
            )

        # Saving results to a jsonlines file
        output_file = os.path.join(DIALOGUES_FOLDER, 'analysis_results.jsonl')
        with open(output_file, mode='w') as w:
            for analysis_result in analysis_results:
                w.write(json.dumps(analysis_result, ensure_ascii=False) + '\n')

        # Outputting results using Django's command output
        self.stdout.write(self.style.NOTICE('Analysis results:'))
        for i, analysis_result in enumerate(analysis_results):
            self.stdout.write(f"\nDialog `{analysis_result['dialog_file']}`:")
            if not analysis_result.get('warnings') and not analysis_result.get('errors') and not analysis_result.get('crashes'):
                self.stdout.write(self.style.SUCCESS("OK\n"))
            else:
                self.stdout.write("\n")
            for deficiency in analysis_result.get('warnings'):
                self.stdout.write(self.style.WARNING(f"- {deficiency}\n"))
            for deficiency in analysis_result.get('errors'):
                self.stdout.write(self.style.ERROR(f"- {deficiency}\n"))
            if analysis_result.get('crashes'):
                self.stdout.write(self.style.NOTICE(f"- {analysis_result['crashes']} crashes\n"))


        all_warnings = list(itertools.chain(*[result['warnings'] for result in analysis_results]))
        all_errors = list(itertools.chain(*[result['errors'] for result in analysis_results]))
        total_crashes = sum([result['crashes'] for result in analysis_results])

        if all_warnings:
            self.stdout.write(self.style.WARNING(f"\nTotal warnings: {len(all_warnings)}"))
        if all_errors:
            self.stdout.write(self.style.ERROR(f"Total errors: {len(all_errors)}"))
        if total_crashes:
            self.stdout.write(self.style.NOTICE(f"Total crashes: {total_crashes}"))

        warnings_str = '- ' + '\n- '.join([f"\"{warning}\"" for warning in all_warnings])
        errors_str = '- ' + '\n- '.join([f"\"{error}\"" for error in all_errors])


        if all_warnings or all_errors or total_crashes:

            full_improvement_prompt = (
                f"Based on the following list of deficiencies identified in {len(dialog_files)} conversations between the user and the bot, "
                "please suggest one improvement that should be prioritized to enhance the bot's performance.\n"
                "Consider factors like potential user impact, fix complexity, and the value of enhancing the interaction.\n"
                "Using an intuitive understanding of RICE (Reach, Impact, Confidence, Effort), propose only one - the highest-priority improvement."
                "Describe it in details.\n"
                "Answer in Russian.\n"
                "Do not explain your choice in detail (for each RICE item) and do not mention RICE. Explain the choice more informally if you need.\n"
                "Here is the list of warning deficiencies:\n"
                f"{warnings_str}\n"
                "Here is the list of error deficiencies:\n"
                f"{errors_str}\n"
            )
            if total_crashes:
                full_improvement_prompt += (
                    f"Total number of crashes (programming exception during sending the response): {total_crashes}\n"
                    f"Crashes should be fixed as a top priority.\n"
                )


            # Getting AI response for prioritization of improvements
            ai_improvement_response = await ai_improvement.get_response(
                messages=[system_message(full_improvement_prompt)],
                max_tokens=500,
            )

            # Outputting proposed improvement based on RICE prioritization
            self.stdout.write(self.style.SUCCESS("\nProposed improvement:"))
            self.stdout.write(ai_improvement_response.result.strip())
        else:
            self.stdout.write(self.style.SUCCESS("\nNo deficiencies found. The bot is performing correctly."))
