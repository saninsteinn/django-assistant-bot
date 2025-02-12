from asgiref.sync import sync_to_async

from assistant.bot.services.context_service.steps.base import ContextProcessingStep


class FillInfoStep(ContextProcessingStep):
    """
    Fill final information for the user question.
    """
    max_tokens_share = 0.15
    max_documents = 3

    async def run(self):
        await sync_to_async(self._run_sync)()

    def _run_sync(self):
        documents = list(self._state.documents)
        if not documents:
            return
        max_tokens = int(self._fast_ai.context_size * self.max_tokens_share)
        output = ''
        n = 0
        while documents and n < self.max_documents:
            document = documents.pop(0)
            new_output = f"{output}# {document.wiki.path}:\n```\n{document.content}\n```\n"
            if output and self._fast_ai.calculate_tokens(new_output) > max_tokens:
                break
            output = new_output
            n += 1
        self._logger.info(f'Filled output with {n} documents with {self._fast_ai.calculate_tokens(output)} tokens.')
        self._state.documents = self._state.documents[:n]
        self._state.final_info = output
        self._state.context_is_ok = True
