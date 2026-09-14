"""Interactive local setup: stores only non-secret provider configuration."""
import json
import subprocess
import sys
import os
from secret_dialog import ask_keys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = Path(os.environ.get('BRB_RUNTIME_DIR') or ROOT / 'runtime')

def valid_endpoint(value):
    parsed = urlparse(value)
    return (parsed.scheme == 'https' and bool(parsed.hostname)
            and not parsed.username and not parsed.password
            and not parsed.query and not parsed.fragment)

def main():
    print('БРБ: запуск обсуждений с ИИ')
    print('ВНИМАНИЕ: если бот уже работает контейнером на сервере — не запускать.')
    print('Два приёмника Telegram одновременно дают HTTP 409 и потерю сообщений.')
    print('Перед запуском закройте старое окно start.cmd. Ноутбук должен оставаться включённым.')
    path = RUNTIME / 'config' / 'discussion-config.json'
    if not path.exists():
        print('Нужны API-адрес выбранного провайдера и идентификатор модели.')
        print('Если аккаунта модели ещё нет, закройте это окно и завершите регистрацию.')
        endpoint = input('Полный HTTPS адрес Chat Completions API (без ключа): ').strip()
        if not valid_endpoint(endpoint):
            print('Некорректный адрес. Настройки не сохранены.')
            return 1
        model = input('Идентификатор модели из кабинета провайдера: ').strip()
        if not model:
            print('Модель не указана. Настройки не сохранены.')
            return 1
        print('При обращении к боту последние сообщения группы и состав команды будут передаваться на:')
        print(urlparse(endpoint).hostname)
        if input('Для использования этого подключения введите ДА: ').strip() != 'ДА':
            print('Настройки не сохранены.')
            return 1
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'model_endpoint': endpoint, 'model': model,
                                   'allow_context_transfer': True}, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Открывается отдельное окно ввода ключей. В консоль вводить ключи не нужно.')
    keys = ask_keys()
    if not keys:
        print('Ввод отменён. Бот не запущен.')
        return 1
    child_env = os.environ.copy()
    child_env.update(keys)
    try:
        return subprocess.call([sys.executable, '-X', 'utf8', str(ROOT / 'src' / 'discussion.py')], env=child_env)
    finally:
        keys.clear()
        child_env.clear()

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print('\nЗапуск отменён.')
