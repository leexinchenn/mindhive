import unittest
from unittest.mock import patch, MagicMock
from p1 import chat_with_bot, get_session_memory, save_conversation_history
from p1 import llm
from p1 import llm  # Added missing import

class TestChatWithBot(unittest.TestCase):

    @patch('builtins.input', side_effect=['Is there an outlet in Petaling Jaya?', 'exit'])
    @patch('p1.save_conversation_history')
    def test_chat_with_bot_exit(self, mock_save, mock_input):
        with patch.object(type(llm), 'invoke', return_value=MagicMock(content='Yes! Which outlet are you referring to?')) as mock_invoke:
            session_id = 'test-session-id'
            chat_with_bot(session_id)
            mock_save.assert_called_once()

    @patch('builtins.input', side_effect=['', 'SS 2, whats the opening time?', 'exit'])
    @patch('p1.save_conversation_history')
    def test_chat_with_bot_empty_input(self, mock_save, mock_input):
        with patch.object(type(llm), 'invoke', return_value=MagicMock(content='Ah yes, the SS 2 outlet opens at 9.00AM.')) as mock_invoke:
            session_id = 'test-session-id'
            with patch('builtins.print') as mock_print:
                chat_with_bot(session_id)
                mock_print.assert_any_call("Bot: I didn't catch that. Could you please rephrase?")

    @patch('builtins.input', side_effect=['Is there an outlet in Petaling Jaya?', 'SS 2, whats the opening time?', 'exit'])
    @patch('p1.save_conversation_history')
    def test_chat_with_bot_conversation(self, mock_save, mock_input):
        with patch.object(type(llm), 'invoke', return_value=MagicMock(content='Ah yes, the SS 2 outlet opens at 9.00AM.')) as mock_invoke:
            session_id = 'test-session-id'
            with patch('builtins.print') as mock_print:
                chat_with_bot(session_id)
                mock_print.assert_any_call("Bot: Ah yes, the SS 2 outlet opens at 9.00AM.")

if __name__ == '__main__':
    unittest.main()