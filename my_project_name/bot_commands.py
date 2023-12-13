from nio import AsyncClient, MatrixRoom, RoomMessageText, RoomSendResponse

from my_project_name.chat_functions import react_to_event, send_text_to_room
from my_project_name.config import Config
from my_project_name.storage import Storage

import requests
import json



class Command:
    def __init__(
        self,
        client: AsyncClient,
        store: Storage,
        config: Config,
        command: str,
        room: MatrixRoom,
        event: RoomMessageText,
    ):
        """A command made by a user.

        Args:
            client: The client to communicate to matrix with.

            store: Bot storage.

            config: Bot configuration parameters.

            command: The command and arguments.

            room: The room the command was sent in.

            event: The event describing the command.
        """
        self.client = client
        self.store = store
        self.config = config
        self.command = command
        self.room = room
        self.event = event
        self.args = self.command.split()[1:]

    async def process(self):
        """Process the command"""
        if self.command.startswith("echo"):
            await self._echo()
        elif self.command.startswith("react"):
            await self._react()
        elif self.command.startswith("help"):
            await self._show_help()
        elif self.command.startswith("q"):
            await self._query_llm_with_name()
        else:
            await self._query_llm()
            # await self._unknown_command()
    
    async def _query_llm_with_name(self):
        """Make the bot forward the query to llm and wait for an answer"""
        # model = 'stablelm-zephyr-3b:latest'
        # if self.args:    
        #     model = self.args[0]
        response = 'Not yet implemented'
        await send_text_to_room(self.client, self.room.room_id, response)

    async def _query_llm(self):
        """Make the bot forward the query to llm and wait for an answer"""
        model = 'stablelm-zephyr-3b:latest'
        payload = {
            "model": model,
            "prompt": "".join(self.args),
            "stream": False
        }
        headers = {
            "content-type": "application/json",
            "cache-control": "no-cache",
        }
        url = "http://host.docker.internal:11434/api/generate"
        
        response = requests.request("POST", url, data=json.dumps(payload), headers=headers)
        json_data = response.json()  # Verwendet die .json()-Methode, um den JSON-Inhalt zu analysieren

        response = (json_data['response'])
        await send_text_to_room(self.client, self.room.room_id, response)

        toks_per_sek = round(int(json_data["eval_count"]) / int(json_data["eval_duration"]),2)

        await send_text_to_room(self.client, self.room.room_id, f'>Your request took {round(int(json_data["eval_duration"])/1000000000,3)} seconds and generated {toks_per_sek} tokens/s')

    async def _echo(self):
        """Echo back the command's arguments"""
        response = " ".join(self.args[1:])
        await send_text_to_room(self.client, self.room.room_id, response)

    async def _react(self):
        """Make the bot react to the command message"""
        # React with a start emoji
        reaction = "⭐"
        await react_to_event(
            self.client, self.room.room_id, self.event.event_id, reaction
        )

        # React with some generic text
        reaction = "Some text"
        await react_to_event(
            self.client, self.room.room_id, self.event.event_id, reaction
        )

    async def _show_help(self):
        """Show the help text"""
        if not self.args:
            text = (
                "Hello, I am a bot made with matrix-nio! Use `help commands` to view "
                "available commands."
            )
            await send_text_to_room(self.client, self.room.room_id, text)
            return

        topic = self.args[0]
        if topic == "rules":
            text = "These are the rules!"
        elif topic == "commands":
            text = "Available commands: `q`: special query to llm (not yet implemented): q stablelm-zephyr-3b:latest _your query_"
        else:
            text = "Unknown help topic!"
        await send_text_to_room(self.client, self.room.room_id, text)

    async def _unknown_command(self):
        await send_text_to_room(
            self.client,
            self.room.room_id,
            f"Unknown command '{self.command}'. Try the 'help' command for more information.",
        )
