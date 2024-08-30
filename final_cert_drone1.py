import asyncio
import websockets
import jwt
import datetime
import logging
from abc import ABC, abstractmethod

logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

SERVER_URL = "ws://localhost:8765"
SECRET_KEY = 'my_secret_key'
USERNAME = 'drone1'
PASSWORD = '333'


def create_jwt_token(username, secret_key):
    token = jwt.encode({
        'username': username,
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30)
    }, secret_key, algorithm="HS256")
    return token


async def websocket_client():
    async with websockets.connect(SERVER_URL) as websocket:
        auth_message = f'LOGIN:{USERNAME},{PASSWORD}'
        await websocket.send(auth_message)

        auth_response = await websocket.recv()

        if auth_response.startswith("JWT:"):
            logging.info("Authorization successful. Waiting for commands...")

            while True:
                try:
                    command_message = await websocket.recv()
                    logging.info(f"Received command: {command_message}")

                    if command_message.startswith("COMMAND:"):
                        command = command_message.split(":")[1]

                        if command == "takeoff":
                            response = "Drone is taking off"
                            remote_control.add_command(take_off)
                            remote_control.execute_command()

                        elif command == "land":
                            remote_control.add_command(land)
                            remote_control.execute_command()
                            response = "Drone is landing"
                        else:
                            response = f"Unknown command: {command}"
                        logging.info(response)

                        # Отправка статуса на сервер
                        await websocket.send(f"STATUS_UPDATE: {USERNAME}: {response}")

                except websockets.ConnectionClosedError:
                    logging.error("Connection with server lost.")
                    break

        else:
            logging.error("Authorization failed.")

#  Реализация паттерна Команда
class Command(ABC):
    @abstractmethod
    def execute(self):
        pass


class Drone:
    def take_off(self):
        logging.info("Command - Drone is taking off")
        # Логика взлета

    def land(self):
        logging.info("Command - Drone is landing")
        # Логика посадки


class TakeOffCommand(Command):
    def __init__(self, drone: Drone):
        self._drone = drone

    def execute(self):
        self._drone.take_off()


class LandCommand(Command):
    def __init__(self, drone: Drone):
        self._drone = drone

    def execute(self):
        self._drone.land()

class RemoteControl:
    def __init__(self):
        self._commands = []
        self._history = []

    def add_command(self, command: Command):
        self._commands.append(command)

    def execute_command(self):
        for command in self._commands:
            command.execute()
            self._history.append(command)
        self._commands.clear()


drone = Drone()
land = LandCommand(drone)
take_off = TakeOffCommand(drone)
remote_control = RemoteControl()

asyncio.get_event_loop().run_until_complete(websocket_client())
