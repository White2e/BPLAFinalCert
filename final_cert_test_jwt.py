import unittest
import jwt
import datetime
from final_cert_srv1 import JWTManager  # импортируем класс для работы с JWT-токенами


class TestJWTManager(unittest.TestCase):

    def setUp(self):
        # Инициализация JWTManager с секретным ключом для тестов
        self.jwt_manager = JWTManager('my_secret_key')

    def test_create_jwt_token(self):
        # Проверяем, что токен правильно создан и содержит ожидаемую информацию
        token = self.jwt_manager.create_jwt_token("user1")
        decoded = jwt.decode(token, "test_secret_key", algorithms=["HS256"])

        # Проверяем, что имя пользователя и время создания в токене верны
        self.assertEqual(decoded["sub"], "user1")
        self.assertIn("iat", decoded)
        self.assertIn("exp", decoded)

    def test_verify_valid_jwt_token(self):
        # Проверяем, что токен, созданный для пользователя, правильно верифицируется
        token = self.jwt_manager.create_jwt_token("user1")
        result = self.jwt_manager.verify_jwt_token(token)
        self.assertEqual(result, "user1")

    def test_verify_expired_jwt_token(self):
        # Создаем истекший токен и проверяем, что он не проходит верификацию
        expired_token = jwt.encode({
            "sub": "user1",
            "iat": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2),
            "exp": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
        }, "test_secret_key", algorithm="HS256")

        result = self.jwt_manager.verify_jwt_token(expired_token)
        self.assertIsNone(result)

    def test_verify_invalid_jwt_token(self):
        # Проверяем, что неверный токен не проходит верификацию
        invalid_token = "invalid.token.value"
        result = self.jwt_manager.verify_jwt_token(invalid_token)
        self.assertIsNone(result)

    def test_verify_tampered_jwt_token(self):
        # Создаем валидный токен и затем модифицируем его, чтобы проверить верификацию
        token = self.jwt_manager.create_jwt_token("user1")
        parts = token.split('.')
        tampered_token = parts[0] + '.' + parts[1] + '.' + 'tampered_signature'

        result = self.jwt_manager.verify_jwt_token(tampered_token)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
