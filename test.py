#!/usr/bin/env python3
"""
Автоматический скрипт для создания удаленного репозитория на GitHub
и загрузки (push) локального проекта в этот репозиторий.

Перед использованием:
1. Установите зависимости:
   pip install requests
2. Создайте Personal Access Token на GitHub (Settings → Developer settings → Personal access tokens)
   и экспортируйте его в переменную окружения GITHUB_TOKEN:
     (Linux/macOS) export GITHUB_TOKEN="ваш_token"
     (Windows PowerShell)  $env:GITHUB_TOKEN="ваш_token"

Запуск:
    python deploy_to_github.py

Скрипт выполнит следующие шаги:
 1. Проверит наличие токена в GITHUB_TOKEN.
 2. Получит логин пользователя через GitHub API.
 3. Запросит у пользователя название нового репозитория, описание и видимость.
 4. Создаст репозиторий на GitHub через API.
 5. Инициализирует локальный git-репозиторий (если ещё не инициализирован).
 6. Создаст первый commit (если нет коммитов).
 7. Свяжет локальный репозиторий с удаленным (origin) и отправит (push) ветку main.
"""

import os
import sys
import subprocess
import requests
import json
from pathlib import Path

GITHUB_API = "https://api.github.com"


def get_github_token():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("Ошибка: переменная окружения GITHUB_TOKEN не найдена.")
        print(
            "Создайте Personal Access Token на GitHub и экспортируйте его в GITHUB_TOKEN.")
        sys.exit(1)
    return token


def get_github_username(token):
    headers = {"Authorization": f"token {token}"}
    response = requests.get(f"{GITHUB_API}/user", headers=headers)
    if response.status_code == 200:
        return response.json().get("login")
    else:
        print(
            f"Не удалось получить информацию о пользователе: {response.status_code} {response.text}")
        sys.exit(1)


def create_github_repo(token, repo_name, description, private):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "name": repo_name,
        "description": description,
        "private": private
    }
    response = requests.post(f"{GITHUB_API}/user/repos", headers=headers,
                             data=json.dumps(payload))
    if response.status_code in (201, 202):
        print(f"Репозиторий '{repo_name}' успешно создан на GitHub.")
        return response.json().get("clone_url")
    else:
        print(
            f"Ошибка при создании репозитория: {response.status_code} {response.text}")
        sys.exit(1)


def run_git_command(args, cwd=None):
    """Запускаем git-команду через subprocess. При ошибке прерываем выполнение."""
    result = subprocess.run(["git"] + args, cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(
            f"Ошибка при выполнении 'git {' '.join(args)}':\n{result.stderr.strip()}")
        sys.exit(1)
    return result.stdout.strip()


def is_git_repo(path: Path):
    return (path / ".git").exists()


def main():
    print("=== Автоматический деплой проекта на GitHub ===\n")

    # Шаг 1: Получаем токен и имя пользователя
    token = get_github_token()
    username = get_github_username(token)
    print(f"Текущий GitHub-пользователь: {username}\n")

    # Шаг 2: Запрашиваем данные будущего репозитория
    repo_name = input(
        "Введите название нового репозитория (например: daily-planner): ").strip()
    if not repo_name:
        print("Название репозитория не может быть пустым.")
        sys.exit(1)

    description = input(
        "Введите описание репозитория (или оставьте пустым): ").strip()

    vis_input = input("Сделать репозиторий приватным? [y/N]: ").strip().lower()
    private = vis_input == "y"

    # Шаг 3: Создаем репозиторий на GitHub
    print("\nСоздаём репозиторий на GitHub...")
    clone_url = create_github_repo(token, repo_name, description, private)
    print(f"URL для клонирования (HTTPS): {clone_url}\n")

    # Шаг 4: Переходим в директорию проекта (текущая работающая директория)
    project_path = Path.cwd()
    print(f"Рабочая директория: {project_path}\n")

    # Шаг 5: Инициализируем git, если ещё не инициализирован
    if not is_git_repo(project_path):
        print("Инициализируем локальный git-репозиторий...")
        run_git_command(["init"], cwd=project_path)
    else:
        print("Локальный git-репозиторий уже инициализирован.")

    # Шаг 6: Настраиваем .gitignore (если не существует)
    gitignore_file = project_path / ".gitignore"
    if not gitignore_file.exists():
        print("Создаем базовый .gitignore...")
        with gitignore_file.open("w", encoding="utf-8") as f:
            f.write(
                """.venv/
                __pycache__/
                *.pyc
                users.json
                theme.json
                """)
        run_git_command(["add", ".gitignore"], cwd=project_path)
    else:
        print(".gitignore уже существует.")

    # Шаг 7: Делаем первый commit, если нет ни одного коммита
    try:
        # проверим, есть ли уже коммиты
        run_git_command(["rev-parse", "--quiet", "--verify", "HEAD"],
                        cwd=project_path)
        has_commits = True
    except SystemExit:
        has_commits = False

    if not has_commits:
        print("Создаем первый коммит...")
        run_git_command(["add", "."], cwd=project_path)
        run_git_command(["commit", "-m", "Initial commit"], cwd=project_path)
    else:
        print("Коммиты уже есть в локальном репозитории.")

    # Шаг 8: Настраиваем удаленный origin и пушим
    # Проверим, настроен ли уже origin
    remotes = run_git_command(["remote"], cwd=project_path)
    if "origin" in remotes.split():
        print("Удаленный 'origin' уже настроен, сбрасываем URL...")
        run_git_command(["remote", "set-url", "origin", clone_url],
                        cwd=project_path)
    else:
        print("Добавляем удаленный 'origin'...")
        run_git_command(["remote", "add", "origin", clone_url],
                        cwd=project_path)

    # Переименуем ветку master в main (если нужно)
    run_git_command(["branch", "-M", "main"], cwd=project_path)

    print("Делаем push локальной ветки main → origin/main...")
    run_git_command(["push", "-u", "origin", "main"], cwd=project_path)

    print("\nПроект успешно загружен на GitHub!")
    print(f"Перейдите по ссылке: https://github.com/{username}/{repo_name}")


if __name__ == "__main__":
    main()
