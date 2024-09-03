import asyncio
import websockets
import jwt
import datetime
import logging
import async_timeout

# Настройка логирования для записи событий в консоль
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

# Секретный ключ для подписи JWT-токенов
SECRET_KEY = 'my_secret_key'

# Простейшая база данных пользователей
users_db = {
    "user1": "111",
    "user2": "222",
    "drone1": "333",
    "drone2": "444",
}

# Словари для отслеживания подключенных дронов и операторов
connected_drones = {}  # Хранение подключенных WebSocket-дронов
connected_users = {}  # Хранение подключенных WebSocket-операторов

# Функция для создания JWT-токена
def create_jwt_token(username):
    payload = {
        "sub": username,  # Идентификатор пользователя
        "iat": datetime.datetime.now(datetime.timezone.utc),  # Время создания токена
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)  # Время истечения токена
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

# Функция для проверки JWT-токена
def verify_jwt_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["sub"]  # Возвращает имя пользователя из токена
    except jwt.ExpiredSignatureError:
        return None  # Токен истек
    except jwt.InvalidTokenError:
        return None  # Неверный токен

# Функция для уведомления всех операторов о статусе дронов
async def notify_users(status_update):
    """Оповещение операторов о статусе дронов"""
    if connected_users:
        drones_status = {drone: "connected" for drone in connected_drones}
        logging.info(f'Sending drones status to users: {drones_status}')
        for user_ws in connected_users.values():
            logging.info(status_update)
            await user_ws.send(status_update)  # Отправляем статус дронов операторам
            status_notifier.notify_observers(f"DRONES_STATUS:{drones_status}")

# Функция для обработки входящих данных от клиентов
async def handle_client(websocket, path):
    async for data in websocket:
        await process_client_data(data, websocket)

# Функция для обработки команд и сообщений от клиентов
async def process_client_data(data, websocket):
    try:
        # Ограничиваем время выполнения операции 5 секундами
        with async_timeout.timeout(5):

            if data.startswith("LOGIN:"):
                # Обработка команды авторизации
                credentials = data[6:].split(",")
                username = credentials[0]
                password = credentials[1]
                logging.info(f'Login attempt: {username}')

                if username in users_db and users_db[username] == password:
                    token = create_jwt_token(username)  # Создаем JWT-токен
                    await websocket.send(f"JWT:{token}")  # Отправляем токен клиенту
                    logging.info(f'Token sent: {token}')

                    if username.startswith('drone'):
                        connected_drones[username] = websocket  # Регистрируем дрон
                        logging.info(f'Drone {username} connected')
                        await notify_users(f'LOGIN:{username}, connected')  # Обновляем статус дронов у всех операторов

                    if username.startswith('user'):
                        connected_users[username] = websocket  # Регистрируем оператора
                        status_notifier.add_observer(Operator(websocket))  # Добавляем оператора как наблюдателя
                        logging.info(f'Operator {username} connected')
                        await notify_users(f'LOGIN:{username}, connected')  # Отправляем оператору статус дронов

                else:
                    await websocket.send("ERROR: Неверные имя пользователя или пароль")

            elif data.startswith("COMMAND:"):
                # Обработка команды управления дроном
                credentials = data[8:].split(",")
                token = credentials[0]
                drone_name = credentials[1]
                command = credentials[2]

                username = verify_jwt_token(token)
                if username:
                    logging.info(f'Command received: {command} for {drone_name} from {username}')
                    drone_ws = connected_drones.get(drone_name)

                    if drone_ws:
                        await drone_ws.send(f"COMMAND:{command}")  # Отправляем команду дрону
                        await websocket.send(f"AUTHORIZED: Команда {command} отправлена на дрон {drone_name}")
                    else:
                        await websocket.send(f"ERROR: Дрон {drone_name} не подключен")

                else:
                    await websocket.send("ERROR: Неверный или просроченный токен")

            elif data.startswith("STATUS_UPDATE:"):
                # Обработка обновлений статуса от дронов
                status_update = data[len("STATUS_UPDATE: "):]
                await notify_users(f'STATUS_UPDATE:{status_update}')  # Уведомляем операторов об изменении статуса
                logging.info(f"Status update from drone: {status_update}")

            else:
                await websocket.send("ERROR: Неверная команда")

    except asyncio.TimeoutError:
        await websocket.send("ERROR: Operation timed out")

# Функция для очистки и обработки отключенных клиентов
async def cleanup():
    while True:
        # Отслеживаем отключенных дронов
        await asyncio.sleep(10)
        disconnected_drones = [name for name, ws in connected_drones.items() if ws.closed]
        for drone in disconnected_drones:
            del connected_drones[drone]
            logging.info(f'Drone {drone} disconnected')
            await notify_users(f'STATUS_UPDATE:{drone}, disconnected')  # Уведомляем операторов

        # Отслеживаем отключенных операторов
        disconnected_users = [name for name, ws in connected_users.items() if ws.closed]
        for user in disconnected_users:
            del connected_users[user]
            logging.info(f'Operator {user} disconnected')
            await notify_users(f'STATUS_UPDATE:{user}, disconnected')  # Уведомляем других операторов

# Реализация паттерна Observer для наблюдения за статусом дронов
class DroneObserver:
    def update(self, drone_status):
        pass

# Класс оператора, который является наблюдателем
class Operator(DroneObserver):
    def __init__(self, websocket):
        self.websocket = websocket

    async def update(self, drone_status):
        logging.info(f'observer - {drone_status}')
        await self.websocket.send(drone_status)  # Отправка статуса оператору

# Класс уведомителя, который управляет наблюдателями
class DroneStatusNotifier:
    def __init__(self):
        self._observers = []

    def add_observer(self, observer):
        self._observers.append(observer)

    def notify_observers(self, drone_status):
        for observer in self._observers:
            asyncio.create_task(observer.update(drone_status))  # Асинхронное уведомление наблюдателей

# Реализация паттерна Singleton (Одиночка) для сервера WebSocket
class WebSocketServer:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(WebSocketServer, cls).__new__(cls)
        return cls._instance

    def __init__(self, host='localhost', port=8765):
        self.host = host
        self.port = port

    async def start_server(self, handle_client):
        server = await websockets.serve(handle_client, self.host, self.port)
        await server.wait_closed()  # Ожидаем завершения работы сервера

# Создание экземпляра уведомителя
status_notifier = DroneStatusNotifier()

# Запуск WebSocket сервера
print("Starting WebSocket server...")
server_instance = WebSocketServer()
asyncio.get_event_loop().run_until_complete(server_instance.start_server(handle_client))
asyncio.get_event_loop().create_task(cleanup())
asyncio.get_event_loop().run_forever()
