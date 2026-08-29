"""Права доступа к командам.

Аналог ``heroku/security.py``, адаптированный под MAX: групповые роли Telegram
заменены на роли MAX (владелец чата / участник / личка).
"""

from __future__ import annotations

import logging
import time
import typing

from pymax import Message

from . import utils

logger = logging.getLogger(__name__)

Command = typing.Callable[..., typing.Awaitable[typing.Any]]

OWNER = 1 << 0
SUDO = 1 << 1
SUPPORT = 1 << 2
CHAT_OWNER = 1 << 3
CHAT_ADMIN = 1 << 4
CHAT_MEMBER = 1 << 5
PM = 1 << 6
EVERYONE = 1 << 7

BITMAP = {
    "OWNER": OWNER,
    "SUDO": SUDO,
    "SUPPORT": SUPPORT,
    "CHAT_OWNER": CHAT_OWNER,
    "CHAT_ADMIN": CHAT_ADMIN,
    "CHAT_MEMBER": CHAT_MEMBER,
    "PM": PM,
    "EVERYONE": EVERYONE,
}

DEFAULT_PERMISSIONS = OWNER
PUBLIC_PERMISSIONS = CHAT_OWNER | CHAT_ADMIN | CHAT_MEMBER | PM
ALL = (1 << 8) - 1


class SecurityGroup(typing.NamedTuple):
    """Именованная группа пользователей с набором прав."""

    name: str
    users: list[int]
    permissions: int


def _sec(func: Command, flags: int) -> Command:
    func.security = flags
    return func


def owner(func: Command) -> Command:
    """Команда доступна только владельцу юзербота."""
    return _sec(func, OWNER)


def sudo(func: Command) -> Command:
    """Команда доступна владельцу и sudo-пользователям."""
    return _sec(func, OWNER | SUDO)


def support(func: Command) -> Command:
    """Команда доступна владельцу, sudo и support."""
    return _sec(func, OWNER | SUDO | SUPPORT)


def chat_owner(func: Command) -> Command:
    """Команда доступна владельцу чата."""
    return _sec(func, OWNER | CHAT_OWNER)


def chat_admin(func: Command) -> Command:
    """Команда доступна администраторам чата."""
    return _sec(func, OWNER | CHAT_OWNER | CHAT_ADMIN)


def chat_member(func: Command) -> Command:
    """Команда доступна любому участнику чата."""
    return _sec(func, OWNER | CHAT_OWNER | CHAT_ADMIN | CHAT_MEMBER)


def pm(func: Command) -> Command:
    """Команда доступна в личных сообщениях."""
    return _sec(func, OWNER | PM)


def unrestricted(func: Command) -> Command:
    """Команда доступна всем."""
    return _sec(func, ALL)


class SecurityManager:
    """Проверяет, имеет ли отправитель право выполнить команду."""

    def __init__(self, client, db):
        self._client = client
        self._db = db
        self._reload_rights()

    # ------------------------------------------------------------------ #
    #                                 state                               #
    # ------------------------------------------------------------------ #

    def _reload_rights(self) -> None:
        self._owner = list(set(self._db.get(__name__, "owner", []) or []))
        self._sudo = list(set(self._db.get(__name__, "sudo", []) or []))
        self._support = list(set(self._db.get(__name__, "support", []) or []))
        self._tsec = self._db.get(__name__, "tsec", {}) or {}

    @property
    def owner(self) -> list[int]:
        """Список ID владельцев (кроме самого аккаунта)."""
        self._reload_rights()
        return self._owner

    @property
    def sudo(self) -> list[int]:
        """Список sudo-пользователей."""
        self._reload_rights()
        return self._sudo

    @property
    def support(self) -> list[int]:
        """Список support-пользователей."""
        self._reload_rights()
        return self._support

    def add_owner(self, user_id: int) -> bool:
        """Добавляет владельца."""
        owners = set(self.owner) | {int(user_id)}
        return self._db.set(__name__, "owner", list(owners))

    def remove_owner(self, user_id: int) -> bool:
        """Убирает владельца."""
        owners = set(self.owner) - {int(user_id)}
        return self._db.set(__name__, "owner", list(owners))

    def add_sudo(self, user_id: int) -> bool:
        """Добавляет sudo-пользователя."""
        return self._db.set(__name__, "sudo", list(set(self.sudo) | {int(user_id)}))

    def remove_sudo(self, user_id: int) -> bool:
        """Убирает sudo-пользователя."""
        return self._db.set(__name__, "sudo", list(set(self.sudo) - {int(user_id)}))

    def add_support(self, user_id: int) -> bool:
        """Добавляет support-пользователя."""
        return self._db.set(__name__, "support", list(set(self.support) | {int(user_id)}))

    def remove_support(self, user_id: int) -> bool:
        """Убирает support-пользователя."""
        return self._db.set(__name__, "support", list(set(self.support) - {int(user_id)}))

    # ------------------------------------------------------------------ #
    #                            security groups                          #
    # ------------------------------------------------------------------ #

    @property
    def sgroups(self) -> dict[str, SecurityGroup]:
        """Именованные группы пользователей с общими правами."""
        raw = self._db.get(__name__, "sgroups", {}) or {}

        return {
            name: SecurityGroup(
                name=name,
                users=list(data.get("users", [])),
                permissions=int(data.get("permissions", 0)),
            )
            for name, data in raw.items()
        }

    def _save_sgroups(self, groups: dict[str, SecurityGroup]) -> bool:
        return self._db.set(
            __name__,
            "sgroups",
            {
                name: {"users": group.users, "permissions": group.permissions}
                for name, group in groups.items()
            },
        )

    def create_sgroup(self, name: str, permissions: int = 0) -> bool:
        """Создаёт группу безопасности."""
        groups = self.sgroups

        if name in groups:
            return False

        groups[name] = SecurityGroup(name=name, users=[], permissions=permissions)
        return self._save_sgroups(groups)

    def delete_sgroup(self, name: str) -> bool:
        """Удаляет группу безопасности."""
        groups = self.sgroups

        if groups.pop(name, None) is None:
            return False

        return self._save_sgroups(groups)

    def sgroup_add_user(self, name: str, user_id: int) -> bool:
        """Добавляет пользователя в группу."""
        groups = self.sgroups
        group = groups.get(name)

        if group is None:
            return False

        groups[name] = group._replace(users=list(set(group.users) | {int(user_id)}))
        return self._save_sgroups(groups)

    def sgroup_remove_user(self, name: str, user_id: int) -> bool:
        """Убирает пользователя из группы."""
        groups = self.sgroups
        group = groups.get(name)

        if group is None:
            return False

        groups[name] = group._replace(users=list(set(group.users) - {int(user_id)}))
        return self._save_sgroups(groups)

    def sgroup_set_permissions(self, name: str, permissions: int) -> bool:
        """Меняет права группы."""
        groups = self.sgroups
        group = groups.get(name)

        if group is None:
            return False

        groups[name] = group._replace(permissions=int(permissions))
        return self._save_sgroups(groups)

    def get_sgroup_permissions(self, user_id: int) -> int:
        """Суммарные права пользователя из всех его групп."""
        result = 0

        for group in self.sgroups.values():
            if user_id in group.users:
                result |= group.permissions

        return result

    # ------------------------------------------------------------------ #
    #                            targeted security                        #
    # ------------------------------------------------------------------ #

    def add_rule(
        self,
        target_type: str,
        target_id: int,
        rule: str,
        duration: int = 0,
    ) -> bool:
        """Выдаёт конкретному пользователю или чату доступ к команде/модулю.

        Args:
            target_type: ``user`` или ``chat``.
            target_id: ID цели.
            rule: Имя команды или ``$module`` для целого модуля.
            duration: Время жизни правила в секундах, ``0`` — бессрочно.
        """
        if target_type not in {"user", "chat"}:
            raise ValueError("target_type must be 'user' or 'chat'")

        self._reload_rights()
        bucket = self._tsec.setdefault(target_type, {}).setdefault(str(target_id), [])
        bucket.append(
            {
                "rule": rule,
                "expires": round(time.time()) + duration if duration else 0,
            }
        )
        return self._db.set(__name__, "tsec", self._tsec)

    def remove_rules(self, target_type: str, target_id: int) -> bool:
        """Убирает все правила для цели."""
        self._reload_rights()
        if str(target_id) in self._tsec.get(target_type, {}):
            del self._tsec[target_type][str(target_id)]
            return self._db.set(__name__, "tsec", self._tsec)
        return False

    def check_tsec(self, user_id: int, command: str, module: str = "") -> bool:
        """Проверяет персональные правила пользователя."""
        self._reload_rights()
        rules = self._tsec.get("user", {}).get(str(user_id), [])
        now = round(time.time())

        for rule in rules:
            if rule.get("expires") and rule["expires"] < now:
                continue

            value = rule.get("rule", "")
            if value == command.lower():
                return True
            if value.startswith("$") and value[1:].lower() == module.lower():
                return True

        return False

    # ------------------------------------------------------------------ #
    #                                 check                               #
    # ------------------------------------------------------------------ #

    def get_flags(self, func: Command | int) -> int:
        """Возвращает битовую маску прав команды."""
        if isinstance(func, int):
            return func

        owner_cls = getattr(getattr(func, "__self__", None), "__class__", None)
        if owner_cls is not None:
            configured = self._db.get(__name__, "masks", {}).get(
                f"{owner_cls.__name__}.{func.__name__}"
            )
            if configured is not None:
                return int(configured)

        if hasattr(func, "security"):
            return func.security

        return self._db.get(__name__, "default_permissions", DEFAULT_PERMISSIONS)

    def set_flags(self, func: Command, flags: int) -> bool:
        """Переопределяет права команды и сохраняет в БД."""
        masks = self._db.get(__name__, "masks", {})
        masks[f"{func.__self__.__class__.__name__}.{func.__name__}"] = int(flags)
        return self._db.set(__name__, "masks", masks)

    async def check(
        self,
        message: Message | None,
        func: Command | int,
        *,
        user_id: int | None = None,
    ) -> bool:
        """Проверяет, разрешено ли выполнение команды."""
        self._reload_rights()

        flags = self.get_flags(func)
        if not flags:
            return False

        if flags & EVERYONE:
            return True

        if user_id is None:
            user_id = utils.get_sender_id(message) if message else None

        if user_id is None:
            return False

        me = utils.get_me_id()
        if me is not None and user_id == me:
            return True

        if flags & OWNER and user_id in self._owner:
            return True

        if flags & SUDO and user_id in self._sudo:
            return True

        if flags & SUPPORT and user_id in self._support:
            return True

        if flags & self.get_sgroup_permissions(user_id):
            return True

        command = getattr(func, "__name__", "").removesuffix("cmd").lower()
        module = getattr(getattr(func, "__self__", None), "__class__", type(None)).__name__
        if self.check_tsec(user_id, command, module):
            return True

        if message is None:
            return False

        chat = await utils.get_chat(message)
        if chat is None:
            return False

        if flags & PM and utils.is_private(chat):
            return True

        if flags & CHAT_OWNER and getattr(chat, "owner", None) == user_id:
            return True

        if flags & CHAT_ADMIN and user_id in (getattr(chat, "admins", None) or []):
            return True

        if flags & CHAT_MEMBER and user_id in (getattr(chat, "participants", None) or {}):
            return True

        return False
