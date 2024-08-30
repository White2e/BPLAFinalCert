import asyncio
import websockets
import jwt
import datetime
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

SECRET_KEY = 'my_secret_key'
users_db = {
    "user1": "111",
    "user2": "222",
    "drone1": "333",
    "drone2": "444",
}

connected_drones = {}  # Отслеживание подключенных дронов
connected_users = {}  # Отслеживание подключенных операторов

def create_jwt_token(username):
    payload = {
        "sub": username,
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verify_jwt_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

async def notify_users(status_update):
    """Оповещение операторов о статусе дронов"""
    if connected_users:
        drones_status = {drone: "connected" for drone in connected_drones}
        logging.info(f'Sending drones status to users: {drones_status}')
        for user_ws in connected_users.values():
            logging.info(status_update)
            await user_ws.send(status_update)
            await user_ws.send(f"DRONES_STATUS:{drones_status}")


async def handle_client(websocket, path):
    async for data in websocket:
        if data.startswith("LOGIN:"):
            credentials = data[6:].split(",")
            username = credentials[0]
            password = credentials[1]
            logging.info(f'Login attempt: {username}')

            if username in users_db and users_db[username] == password:
                token = create_jwt_token(username)
                await websocket.send(f"JWT:{token}")
                #logging.info(f'Token sent: {token}')

                if username.startswith('drone'):
                    connected_drones[username] = websocket
                    logging.info(f'Drone {username} connected')
                    await notify_users(f'LOGIN:{username}, connected')  # Обновляем статус дронов у всех операторов

                if username.startswith('user'):
                    connected_users[username] = websocket
                    logging.info(f'Operator {username} connected')
                    await notify_users(f'LOGIN:{username}, connected')  # Отправляем оператору статус дронов

            else:
                await websocket.send("ERROR: Неверные имя пользователя или пароль")

        elif data.startswith("COMMAND:"):
            credentials = data[8:].split(",")
            token = credentials[0]
            drone_name = credentials[1]
            command = credentials[2]

            username = verify_jwt_token(token)
            if username:
                logging.info(f'Command received: {command} for {drone_name} from {username}')
                drone_ws = connected_drones.get(drone_name)

                if drone_ws:
                    await drone_ws.send(f"COMMAND:{command}")
                    await websocket.send(f"AUTHORIZED: Команда {command} отправлена на дрон {drone_name}")
                else:
                    await websocket.send(f"ERROR: Дрон {drone_name} не подключен")

            else:
                await websocket.send("ERROR: Неверный или просроченный токен")

        elif data.startswith("STATUS_UPDATE:"):
            status_update = data[len("STATUS_UPDATE: "):]
            await notify_users(f'STATUS_UPDATE:{status_update}')
            logging.info(f"Status update from drone: {status_update}")

        else:
            await websocket.send("ERROR: Неверная команда")


async def cleanup():
    while True:
        # отслеживаем отключенных дронов
        await asyncio.sleep(10)
        disconnected_drones = [name for name, ws in connected_drones.items() if ws.closed]
        for drone in disconnected_drones:
            del connected_drones[drone]
            logging.info(f'Drone {drone} disconnected')
            await notify_users(f'STATUS_UPDATE:{drone}, disconnected')

        # отслеживаем отключенных операторов
        disconnected_users = [name for name, ws in connected_users.items() if ws.closed]
        for user in disconnected_users:
            del connected_users[user]
            logging.info(f'Operator {user} disconnected')
            await notify_users(f'STATUS_UPDATE:{user}, disconnected')


print("Starting WebSocket server...")
start_server = websockets.serve(handle_client, "localhost", 8765)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().create_task(cleanup())
asyncio.get_event_loop().run_forever()
