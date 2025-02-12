from typing import Callable, Awaitable, Any

from assistant.bot.utils import logger, MaxAttemptsExceededError


async def repeat_until(
    func: Callable[..., Awaitable[Any]],
    *args: Any,
    max_attempts: int = 5,
    condition: Callable[[Any], bool],
    **kwargs: Any
) -> Any:
    """
    Repeat the given async function until the condition is met or max_attempts is reached.

    :param func: The async function to repeat.
    :param condition: The condition to check that applies to the `func` response.
    :param max_attempts: The maximum number of attempts.
    :param args: The positional arguments to pass to the function.
    :param kwargs: The keyword arguments to pass to the function.
    """
    attempt = 0
    while attempt < max_attempts:
        response = await func(*args, **kwargs)
        if condition(response):
            return response
        attempt += 1
        logger.warning(f"Attempt {attempt} failed for response: {response}, retrying...")
    raise MaxAttemptsExceededError(f"Condition not met after {max_attempts} attempts")


async def retry_call(
    func: Callable[..., Awaitable[Any]],
    *args: Any,
    max_attempts: int = 5,
    **kwargs: Any
) -> Any:
    """
    Retry the given async function until it succeeds or max_attempts is reached.

    :param func: The async function to retry.
    :param max_attempts: The maximum number of attempts.
    :param args: The positional arguments to pass to the function.
    :param kwargs: The keyword arguments to pass to the function.
    """
    attempt = 0
    while attempt < max_attempts:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            attempt += 1
            if attempt >= max_attempts:
                raise MaxAttemptsExceededError(f"Function failed after {max_attempts} attempts") from e
