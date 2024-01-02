
from typing import Dict
from llm_to_matrix.storage import Storage
from enum import Enum


class Role(Enum):
    USER = 'user'
    SYSTEM = 'system'
    ASSISTANT = 'assistant'

class MessageType(Enum):
   LINK = 'link'
   CODE = 'code'
   CUSTOM = 'custome'
   DEFAULT = 'default'


class ConversationStore(Storage):
    def __init__(self, database_config: Dict[str, str]):
      super().__init__(database_config)
      self._init_db()

    def _init_db(self):
      # Create the messages table if it doesn't exist
      self._execute('''
          CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT,
            user TEXT,
            model TEXT,
            messageType TEXT,
            prompt TEXT,
            event_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
          )
      ''')

    def add_message(self, content, user, role: Role, messageType: MessageType, model=None, prompt=None, event_id=None):
      # Ensure that the role is an instance of the Role enum
      if not isinstance(role, Role):
        raise ValueError("role must be an instance of Role enum")
      
      if not isinstance(messageType, MessageType):
        raise ValueError("messageType must be an instance of MessageType enum")

      self._execute('''
          INSERT INTO messages (role, content, user, model, messageType, prompt, event_id)
          VALUES (?, ?, ?, ?, ?, ?, ?)
      ''', (role.value, content, user, model, messageType.value, prompt, event_id))

    def get_last_five_messages(self, user=None, messageType=None, limit=5):

      if user is None and messageType is None:
         raise('Please provide any search criteria.')

      query = "SELECT role, content, user, model, messageType, prompt, event_id FROM messages "
      params = ()
      if user is not None and messageType is not None:
          query += "WHERE user = ? and messageType = ?"
          params = (user, messageType)
      if user is not None and messageType is None:
          query += "WHERE user = ? "
          params = (user,)
      if user is None and messageType is not None:
        query += "WHERE messageType = ? "
        params = (messageType,)
      query += f"ORDER BY id DESC LIMIT {limit}"

      self._execute(query, params)
      return list(reversed(self.cursor.fetchall()))
