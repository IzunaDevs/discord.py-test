import asyncio
import copy

import discord

from discord_test import Game, Colour


class VoiceState(discord.VoiceState):
    # Just a dataclass, works fine
    pass


class Member(discord.Member):
    def __init__(self, *, data, guild):
        # self._state = state
        # self._user = state.store_user(data['user'])
        self.guild = guild
        self.joined_at = discord.utils.parse_time(data.get('joined_at'))
        self._update_roles(data)
        self.status = discord.Status.offline
        game = data.get('game', {})
        self.game = Game(**game) if game else None
        self.nick = data.get('nick', None)

    def __str__(self):
        return str(self._user)

    def __repr__(self):
        return '<Member id={1.id} name={1.name!r} discriminator={1.discriminator!r}' \
               ' bot={1.bot} nick={0.nick!r} guild={0.guild!r}>'.format(self, self._user)

    def __eq__(self, other):
        return isinstance(other, discord.User) and other.id == self.id

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self._user.id)

    @asyncio.coroutine
    def _get_channel(self):
        ch = yield from self.create_dm()
        return ch

    def _update_roles(self, data):
        # update the roles
        self.roles = [self.guild.default_role]
        for roleid in map(int, data['roles']):
            role = discord.utils.find(lambda r: r.id == roleid, self.guild.roles)
            if role is not None:
                self.roles.append(role)

        # sort the roles by hierarchy since they can be "randomised"
        self.roles.sort()

    def _update(self, data, user=None):
        if user:
            self._user.name = user['username']
            self._user.discriminator = user['discriminator']
            self._user.avatar = user['avatar']
            self._user.bot = user.get('bot', False)

        # the nickname change is optional,
        # if it isn't in the payload then it didn't change
        try:
            self.nick = data['nick']
        except KeyError:
            pass

        self._update_roles(data)

    def _presence_update(self, data, user):
        self.status = discord.enums.try_enum(Status, data['status'])
        game = data.get('game', {})
        self.game = Game(**game) if game else None
        u = self._user
        u.name = user.get('username', u.name)
        u.avatar = user.get('avatar', u.avatar)
        u.discriminator = user.get('discriminator', u.discriminator)

    def _copy(self):
        c = copy.copy(self)
        c._user = copy.copy(self._user)
        return c

    @property
    def colour(self):
        roles = self.roles[1:]  # remove @everyone

        # highest order of the colour is the one that gets rendered.
        # if the highest is the default colour then the next one with a colour
        # is chosen instead
        for role in reversed(roles):
            if role.colour.value:
                return role.colour
        return Colour.default()

    color = colour

    @property
    def mention(self):
        if self.nick:
            return '<@!%s>' % self.id
        return '<@%s>' % self.id

    @property
    def display_name(self):
        return self.nick if self.nick is not None else self.name

    def mentioned_in(self, message):
        if self._user.mentioned_in(message):
            return True

        for role in message.role_mentions:
            has_role = discord.utils.get(self.roles, id=role.id) is not None
            if has_role:
                return True

        return False

    def permissions_in(self, channel):
        return channel.permissions_for(self)

    @property
    def top_role(self):
        return self.roles[-1]

    @property
    def guild_permissions(self):
        if self.guild.owner == self:
            return discord.Permissions.all()

        base = discord.Permissions.none()
        for r in self.roles:
            base.value |= r.permissions.value

        if base.administrator:
            return discord.Permissions.all()

        return base

    @property
    def voice(self):
        return self.guild._voice_state_for(self._user.id)

    @asyncio.coroutine
    def ban(self, **kwargs):
        yield from self.guild.ban(self, **kwargs)

    @asyncio.coroutine
    def unban(self, *, reason=None):
        yield from self.guild.unban(self, reason=reason)

    @asyncio.coroutine
    def kick(self, *, reason=None):
        yield from self.guild.kick(self, reason=reason)

    @asyncio.coroutine
    def edit(self, *, reason=None, **fields):
        raise NotImplementedError

    @asyncio.coroutine
    def move_to(self, channel, *, reason=None):
        yield from self.edit(voice_channel=channel, reason=reason)

    @asyncio.coroutine
    def add_roles(self, *roles, reason=None, atomic=True):
        raise NotImplementedError

    @asyncio.coroutine
    def remove_roles(self, *roles, reason=None, atomic=True):
        raise NotImplementedError
