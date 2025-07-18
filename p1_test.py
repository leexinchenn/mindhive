import unittest
from unittest.mock import patch, MagicMock
from p1 import chat_with_bot, get_session_memory, save_conversation_history, llm


class TestChatWithBot(unittest.TestCase):
    """Happy path tests"""

    @patch(
        "builtins.input",
        side_effect=[
            "Is there an outlet in Petaling Jaya?",
            "SS 2, whats the opening time?",
            "exit",
        ],
    )
    @patch("p1.save_conversation_history")
    def test_chat_with_bot_full_conversation(self, mock_save, mock_input):
        """Test a full conversation flow with the bot."""
        with patch.object(
            type(llm),
            "invoke",
            return_value=MagicMock(content="Ah yes, the SS 2 outlet opens at 9.00AM."),
        ):
            session_id = "test-session-id"
            with patch("builtins.print") as mock_print:
                chat_with_bot(session_id)
                mock_print.assert_any_call(
                    "Bot: Ah yes, the SS 2 outlet opens at 9.00AM."
                )

    """Interrupted chat session tests"""

    @patch(
        "builtins.input", side_effect=["Is there an outlet in Petaling Jaya?", "exit"]
    )
    @patch("p1.save_conversation_history")
    def test_chat_with_bot_exit_saves_history(self, mock_save, mock_input):
        """Test that conversation history is saved when user exits."""
        with patch.object(
            type(llm),
            "invoke",
            return_value=MagicMock(content="Yes! Which outlet are you referring to?"),
        ):
            session_id = "test-session-id"
            chat_with_bot(session_id)
            mock_save.assert_called_once()

    @patch("builtins.input", side_effect=["", "SS 2, whats the opening time?", "exit"])
    @patch("p1.save_conversation_history")
    def test_chat_with_bot_handles_empty_input(self, mock_save, mock_input):
        """Test that bot prompts user to rephrase on empty input."""
        with patch.object(
            type(llm),
            "invoke",
            return_value=MagicMock(content="Ah yes, the SS 2 outlet opens at 9.00AM."),
        ):
            session_id = "test-session-id"
            with patch("builtins.print") as mock_print:
                chat_with_bot(session_id)
                mock_print.assert_any_call(
                    "Bot: I didn't catch that. Could you please rephrase?"
                )

    def test_get_session_memory_returns_history_obj(self):
        """Test get_session_memory returns an InMemoryChatMessageHistory object for a new session."""
        session_id = "new-session-id"
        memory = get_session_memory(session_id)
        # Import from the correct module for newer langchain versions
        from langchain.memory.chat_message_histories import ChatMessageHistory

        self.assertIsInstance(memory, ChatMessageHistory)

    @patch("builtins.open")
    @patch("json.dump")
    def test_save_conversation_history_calls_json_dump(self, mock_json_dump, mock_open):
        """Test save_conversation_history calls json.dump with correct arguments."""
        session_id = "test-session-id"
        save_conversation_history(session_id)
        mock_json_dump.assert_called_once()


if __name__ == "__main__":
    unittest.main()
