"""Служебные операции: перезапуск, остановка, обновление.

Аналог ``heroku/_internal.py``.
"""

from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import sys
import typing

logger = logging.getLogger(__name__)


def restart(*argv: str) -> typing.NoReturn:
    """Перезапускает процесс юзербота, сохраняя аргументы командной строки."""
    logger.info("Restarting Maxli...")

    if "HEROKU_DOCKER" in os.environ or "MAXLI_DOCKER" in os.environ:
        sys.exit(0)

    with contextlib.suppress(Exception):
        os.execl(
            sys.executable,
            sys.executable,
            "-m",
            "maxli",
            *filter(lambda x: x != "--no-web", sys.argv[1:]),
            *argv,
        )

    sys.exit(0)


def die() -> typing.NoReturn:
    """Полностью останавливает юзербота."""
    logger.info("Shutting down Maxli...")

    if "MAXLI_SYSTEMD" in os.environ:
        subprocess.run(["systemctl", "stop", "maxli"], check=False)

    sys.exit(0)


def get_repo_dir() -> str:
    """Каталог с git-репозиторием Maxli.

    Это всегда каталог рядом с пакетом ``maxli`` — в отличие от
    ``utils.get_base_dir()``, который в Docker указывает на ``/data``.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_git_hash() -> str | None:
    """Короткий хэш текущего коммита, если Maxli стоит из git."""
    with contextlib.suppress(Exception):
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
                cwd=get_repo_dir(),
            )
            .decode()
            .strip()
        )
    return None


def get_commit_count() -> int | None:
    """Количество коммитов — используется как build number."""
    with contextlib.suppress(Exception):
        return int(
            subprocess.check_output(
                ["git", "rev-list", "--count", "HEAD"],
                stderr=subprocess.DEVNULL,
                cwd=get_repo_dir(),
            )
            .decode()
            .strip()
        )
    return None


def pull() -> bool:
    """Обновляет исходники через ``git pull``."""
    with contextlib.suppress(Exception):
        subprocess.run(
            ["git", "pull", "--ff-only"],
            check=True,
            cwd=get_repo_dir(),
        )
        return True
    return False


def install_requirements(path: str = "requirements.txt") -> bool:
    """Ставит зависимости из requirements.txt."""
    with contextlib.suppress(Exception):
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", path, "--upgrade"],
            check=True,
            cwd=get_repo_dir(),
        )
        return True
    return False
