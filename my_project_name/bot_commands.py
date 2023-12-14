import logging
import requests
import json
from urllib.parse import urljoin
from nio import AsyncClient, MatrixRoom, RoomMessageText
from my_project_name.helper import prepare_msg
from my_project_name.storage import Storage
from my_project_name.config import Config
from my_project_name.chat_functions import react_to_event, send_text_to_room, send_typing_to_room

logger = logging.getLogger()

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
        elif self.command.startswith("cm"):
            await self._query_llm_with_name()
        else:
            await self._query_llm()
            # await self._unknown_command()
    
    async def _query_llm_with_name(self):
        """Make the bot forward the query to llm and wait for an answer"""
        model = None
        if self.args:    
            model = self.args[0]
        
        message = " ".join(self.args[1::])
        await self.send_llm_message(model=model, message=message)
        

    async def _query_llm(self):
        """Make the bot forward the query to llm and wait for an answer"""
        await self.send_llm_message(message=" ".join(self.args))

    async def send_llm_message(self, model=None, message=''):
        await send_typing_to_room(self.client, self.room.room_id, True, 60000)

        llm_param_stop = []
        if self.config.llm_param_stop is not "" and model is None:
            llm_param_stop.append(self.config.llm_param_stop)

        model_name = self.config.llm_model
        if model is not None:
            model_name = model

        try:
            payload = {
                "model": model_name,
                "prompt": prepare_msg(self.config.llm_msg_template, message) if model is None else message,
                "stream": False,
                "options": {
                    "seed": self.config.llm_param_seed,
                    "num_predict": self.config.llm_param_num_predict,
                    "top_k": self.config.llm_param_top_k,
                    "top_p": self.config.llm_param_top_p,
                    "repeat_last_n": self.config.llm_param_repeat_last_n,
                    "temperature": self.config.llm_param_temp,
                    "repeat_penalty": self.config.llm_param_repeat_penalty,
                    "stop": llm_param_stop,
                    "num_ctx": self.config.llm_param_num_ctx,
                }
            }
                
            headers = {
                'Content-Type': 'application/json'
            }
            url = urljoin(self.config.llm_base_url, self.config.llm_url_suffix)
            response = requests.request("POST", url, data=json.dumps(payload), headers=headers, stream=False)

            if (200 <= int(response.status_code) < 300):
                json_data = response.json()
                await send_typing_to_room(self.client, self.room.room_id, False)
                response = (json_data['response'])
                logger.info(response)
                await send_text_to_room(self.client, self.room.room_id, response, markdown_convert=True)

                if "eval_duration" in json_data and "eval_count" in json_data:
                    eval_dur = int(json_data["eval_duration"])
                    eval_cnt = int(json_data['eval_count'])
                    if eval_dur != 0 and eval_cnt != 0:
                        toks_per_sek = eval_cnt / (eval_dur / 1e9)
                        await send_text_to_room(self.client, self.room.room_id, f'>Your request has been answered by `{model_name}` and took {round((eval_dur)/1000000000, 3)} seconds and generated {round(toks_per_sek, 3)} tokens/s')
                    else: 
                        await send_text_to_room(self.client, self.room.room_id,'>Your request took some time but couldn\'t calculate the token generation rate due to zero values of eval_duration or eval_count')
            else:
                await send_typing_to_room(self.client, self.room.room_id, False)
                await send_text_to_room(self.client, self.room.room_id, f"An error occurred while fetching the API({response.status_code}): {response}")
    
        except requests.RequestException as e :  
            await send_typing_to_room(self.client, self.room.room_id, False)
            await send_text_to_room(self.client, self.room.room_id, f"An unknown error: {e}")
            print('Error Occurred', e)

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
