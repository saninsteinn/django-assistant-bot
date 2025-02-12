from assistant.bot.services.context_service.steps.base import ContextProcessingStep


class InterruptIfSmallTalkStep(ContextProcessingStep):
    """
    Check if the user's question is a small talk. Context is not needed in this case.
    """

    async def run(self):
        if self._state.topic is None:
            self._state.done = True

