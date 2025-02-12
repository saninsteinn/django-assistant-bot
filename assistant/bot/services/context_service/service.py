import asyncio
import logging
from typing import List, Dict, Callable, Awaitable, Type, Union

from assistant.ai.domain import Message
from assistant.bot.models import Bot
from assistant.bot.services.context_service.state import ContextProcessingState
from assistant.bot.services.context_service.steps.base import ContextProcessingStep
from assistant.bot.services.context_service.steps.choose_known_question import ChooseKnownQuestionStep
from assistant.bot.services.context_service.steps.classify import ClassifyStep
from assistant.bot.services.context_service.steps.embeddings import EmbeddingsStep
from assistant.bot.services.context_service.steps.fill_info import FillInfoStep
from assistant.bot.services.context_service.steps.final_prompt import FinalPromptStep
from assistant.bot.services.context_service.steps.interruptions import InterruptIfSmallTalkStep

logger = logging.getLogger(__name__)


class ContextService:

    def __init__(
            self,
            bot: Bot,
            fast_ai_model: str,
            strong_ai_model: str,
            messages: List[Message],
            debug_info: Dict = None,
            do_interrupt: Callable[..., Awaitable[bool]] = None
    ):
        self._bot = bot
        self._fast_ai_model = fast_ai_model
        self._strong_ai_model = strong_ai_model
        self._messages = messages
        self._debug_info = debug_info
        self._do_interrupt = do_interrupt
        self._state = ContextProcessingState()
        self._state.messages = messages

    async def enrich(self) -> List[Message]:
        """
        Enriches the context of the messages.
        """
        await self._pipeline([
            [ClassifyStep, EmbeddingsStep],
            # ReformulateQuestionStep,
            InterruptIfSmallTalkStep,
            ChooseKnownQuestionStep,
            # ChooseDocsStep,
            FillInfoStep,
            # CheckContextStep,
            FinalPromptStep
        ])
        return self._state.messages

    async def _pipeline(
            self,
            pipeline: List[Union[Type[ContextProcessingStep], List[Type[ContextProcessingStep]]]]
    ):
        """
        Runs the pipeline of the steps.
        """
        for steps in pipeline:
            if not isinstance(steps, list):
                steps = [steps]
            await self._run_steps(steps)
            if self._do_interrupt and await self._do_interrupt():
                break
            if self._state.done:
                break

    async def _run_steps(self, step_cls_list: List[Type[ContextProcessingStep]]):
        steps = [
            step_cls(
                bot=self._bot,
                state=self._state,
                fast_ai_model=self._fast_ai_model,
                strong_ai_model=self._strong_ai_model,
                debug_info=self._debug_info
            )
            for step_cls in step_cls_list
        ]
        tasks = [step.run() for step in steps]
        await asyncio.gather(*tasks)
