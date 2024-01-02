import logging
import requests
import json
from urllib.parse import urljoin
from nio import AsyncClient, MatrixRoom, RoomMessageText
from llm_to_matrix.conversation_store import ConversationStore, MessageType, Role
from llm_to_matrix.helper import prepare_msg, validate_url
from llm_to_matrix.parser.parser import get_main_content
# from llm_to_matrix.storage import Storage
from llm_to_matrix.config import Config
from llm_to_matrix.chat_functions import react_to_event, send_text_to_room, send_typing_to_room

logger = logging.getLogger()

class Command:
    def __init__(
        self,
        client: AsyncClient,
        store: ConversationStore,
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
        elif self.command.startswith("li"):
            await self._query_llm_for_summery()
        elif self.command.startswith("ls"):
            await self._query_for_available_llms()
        elif self.command.startswith("code"):
            await self._query_for_code()
        else:
            await self._query_llm()
            # await self._unknown_command()

    async def _query_for_code(self):
        """Make the bot forward the query to llm for code generation and wait for an answer"""
        model = "deepseek-coder-6.7b-instruct:latest"
        message = " ".join(self.args[0::]).strip()
        prompt = f"Please generate a short and accurate code snippet based on the following specifications. The code should be precise, efficient, and adhere closely to the requirements. Ensure the solution is concise and to the point.\n{message}"
        logger.info(self.event.event_id)
        self.store.add_message(message, self.event.sender, Role.USER, MessageType.CODE, None, prompt, self.event.event_id)
        await self.send_llm_message(model=model, message=prompt, messageType=MessageType.CODE, event_id=self.event.event_id)

    async def _query_for_available_llms(self):
        await send_typing_to_room(self.client, self.room.room_id, True)
        try:
            headers = {
                'Content-Type': 'application/json'
            }
            url = urljoin(self.config.llm_base_url, self.config.llm_tags_suffix)
            response = requests.request("GET", url, headers=headers, stream=False)

            if (200 <= int(response.status_code) < 300):
                json_data = response.json()
                await send_typing_to_room(self.client, self.room.room_id, False)
                model_names = [model['name'] for model in json_data['models']]
                model_names = '\n'.join(f"⭑ {name}" for name in model_names)
                await send_text_to_room(self.client, self.room.room_id, f"Available models:\n{model_names}", markdown_convert=True)
        except requests.RequestException as e :
            await send_typing_to_room(self.client, self.room.room_id, False)
            await send_text_to_room(self.client, self.room.room_id, f"An unknown error: {e}")
            print('Error Occurred', e)


    async def _query_llm_for_summery(self):
        """Make the bot forward the query to llm for summerization and wait for an answer"""
        link = None
        if self.args:
            link = self.args[0]

        message = " ".join(self.args[1::]).strip()

        if len(message) > 0:
            await send_text_to_room(self.client, self.room.room_id, f"This part of the message will be ignored\n>{message}", markdown_convert=True)

        is_valid_url, parsed_url = validate_url(link)

        if not is_valid_url:
            await send_text_to_room(self.client, self.room.room_id, f"The given URL is invalid\n>{link}", markdown_convert=True)

        content = get_main_content(parsed_url)
        model = "mistral-7b-instruct:latest"
        prompt = f"Please provide a brief summary of the following content, ensuring to use the same language as the original. Keep the summary concise.\n\n---\n{content}\n---\nEnd of content."
        self.store.add_message(parsed_url, self.event.sender, Role.USER, MessageType.LINK, None, prompt, self.event.event_id)
        await self.send_llm_message(model=model, message=prompt, messageType=MessageType.LINK, event_id=self.event.event_id)

    async def _query_llm_with_name(self):
        """Make the bot forward the query to a specific llm and wait for an answer"""
        model = None
        if self.args:
            model = self.args[0]

        message = " ".join(self.args[1::])

        self.store.add_message(message, self.event.sender, Role.USER, MessageType.CUSTOM, None, None, self.event.event_id)
        await self.send_llm_message(model=model, message=message, messageType=MessageType.CUSTOM, event_id=self.event.event_id)


    async def _query_llm(self):
        """Make the bot forward the query to llm and wait for an answer"""
        message = " ".join(self.args)
        self.store.add_message(message, self.event.sender, Role.USER, MessageType.DEFAULT, None, None, self.event.event_id)
        await self.send_llm_message(message=message, event_id=self.event.event_id)

    async def send_llm_message(self, model=None, message='', messageType=MessageType.DEFAULT, event_id=None):
        await send_typing_to_room(self.client, self.room.room_id, True, 60000)

        llm_param_stop = []
        if self.config.llm_param_stop != "" and model is None:
            llm_param_stop.append(self.config.llm_param_stop)

        model_name = self.config.llm_model
        if model is not None:
            model_name = model

        prompt = prepare_msg(self.config.llm_msg_template, message) if model is None else message

        try:
            payload = {
                "model": model_name,
                "prompt": prompt,
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
                response = response.replace('<0x0A>', '\n') # some models have inconsistencies and use <0x0A> as \n
                
                self.store.add_message(response, self.client.user_id, Role.ASSISTANT, messageType, model_name, prompt, event_id)
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
                f"Hello, I am {self.config.llm_name}! Use `help commands` to view "
                "available commands."
            )
            await send_text_to_room(self.client, self.room.room_id, text)
            return

        topic = self.args[0]
        if topic == "rules":
            text = "These are the rules!"
        elif topic == "commands":
            text = (
                "Available commands: \n"
                "• `ls`: Lists all available models.\n"
                "• `cm`: Queries a custom model. Example: `cm stablelm-zephyr-3b:latest _your query_`.\n"
                "• `li`: Summarizes the content of a link. Example: `li https://www.example.com`.\n"
                "• `code`: Generates code based on a given prompt. Example: `code give me a typescript function that mirrors a given string`.\n"
                )
        else:
            text = "Unknown help topic!"
        await send_text_to_room(self.client, self.room.room_id, text)

    async def _unknown_command(self):
        await send_text_to_room(
            self.client,
            self.room.room_id,
            f"Unknown command '{self.command}'. Try the 'help' command for more information.",
        )
