class UserUnavailableError(Exception):
    """Raised when an operation fails because the user is unavailable (blocked, deactivated, etc.)."""
    def __init__(self, chat_id: str, *args):
        self.chat_id = chat_id
        super().__init__(f"User with chat_id {chat_id} is unavailable.", *args)
