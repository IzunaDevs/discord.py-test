import asyncio
import collections
import copy

import discord

from discord_test import VoiceState, Game, Status, TextChannel, VoiceChannel, CategoryChannel, AuditLogIterator


class Guild(discord.Guild):
    def __init__(self, *, data):
        self._channels = {}
        self._members = {}
        self._voice_states = {}
        self._from_data(data)

    def _add_channel(self, channel):
        self._channels[channel.id] = channel

    def _remove_channel(self, channel):
        self._channels.pop(channel.id, None)

    def _voice_state_for(self, user_id):
        return self._voice_states.get(user_id)

    def _add_member(self, member):
        self._members[member.id] = member

    def _remove_member(self, member):
        self._members.pop(member.id, None)

    def __str__(self):
        return self.name

    def __repr__(self):
        return '<Guild id={0.id} name={0.name!r} chunked={0.chunked}>'.format(self)

    def _update_voice_state(self, data, channel_id):
        user_id = int(data['user_id'])
        channel = self.get_channel(channel_id)
        try:
            # check if we should remove the voice state from cache
            if channel is None:
                after = self._voice_states.pop(user_id)
            else:
                after = self._voice_states[user_id]

            before = copy.copy(after)
            after._update(data, channel)
        except KeyError:
            # if we're here then we're getting added into the cache
            after = VoiceState(data=data, channel=channel)
            before = VoiceState(data=data, channel=None)
            self._voice_states[user_id] = after

        member = self.get_member(user_id)
        return member, before, after

    def _add_role(self, role):
        # roles get added to the bottom (position 1, pos 0 is @everyone)
        # so since self.roles has the @everyone role, we can't increment
        # its position because it's stuck at position 0. Luckily x += False
        # is equivalent to adding 0. So we cast the position to a bool and
        # increment it.
        for r in self.roles:
            r.position += bool(r.position)

        self.roles.append(role)

    def _remove_role(self, role):
        # this raises ValueError if it fails..
        self.roles.remove(role)

        # since it didn't, we can change the positions now
        # basically the same as above except we only decrement
        # the position if we're above the role we deleted.
        for r in self.roles:
            r.position -= r.position > role.position

    def _from_data(self, guild):
        raise NotImplementedError

    def _sync(self, data):
        try:
            self._large = data['large']
        except KeyError:
            pass

        for presence in data.get('presences', []):
            user_id = int(presence['user']['id'])
            member = self.get_member(user_id)
            if member is not None:
                member.status = discord.enums.try_enum(Status, presence['status'])
                game = presence.get('game', {})
                member.game = Game(**game) if game else None

        if 'channels' in data:
            channels = data['channels']
            for c in channels:
                if c['type'] == discord.ChannelType.text.value:
                    self._add_channel(TextChannel(guild=self, data=c))
                elif c['type'] == discord.ChannelType.voice.value:
                    self._add_channel(VoiceChannel(guild=self, data=c))
                elif c['type'] == discord.ChannelType.category.value:
                    self._add_channel(CategoryChannel(guild=self, data=c))

    @property
    def channels(self):
        return list(self._channels.values())

    @property
    def large(self):
        if self._large is None:
            try:
                return self._member_count >= 250
            except AttributeError:
                return len(self._members) >= 250
        return self._large

    @property
    def voice_channels(self):
        r = [ch for ch in self._channels.values() if isinstance(ch, VoiceChannel)]
        r.sort(key=lambda c: (c.position, c.id))
        return r

    @property
    def me(self):
        self_id = self._state.user.id
        return self.get_member(self_id)

    @property
    def voice_client(self):
        raise NotImplementedError

    @property
    def text_channels(self):
        r = [ch for ch in self._channels.values() if isinstance(ch, TextChannel)]
        r.sort(key=lambda c: (c.position, c.id))
        return r

    @property
    def categories(self):
        r = [ch for ch in self._channels.values() if isinstance(ch, CategoryChannel)]
        r.sort(key=lambda c: (c.position, c.id))
        return r

    def by_category(self):
        grouped = collections.defaultdict(list)
        for channel in self._channels.values():
            if isinstance(channel, CategoryChannel):
                continue

            grouped[channel.category_id].append(channel)

        def key(t):
            k, v = t
            return (k.position, k.id) if k else (-1, -1), v

        _get = self._channels.get
        as_list = [(_get(k), v) for k, v in grouped.items()]
        as_list.sort(key=key)
        for _, channels in as_list:
            channels.sort(key=lambda c: (c.position, c.id))
        return as_list

    def get_channel(self, channel_id):
        return self._channels.get(channel_id)

    @property
    def system_channel(self):
        channel_id = self._system_channel_id
        return channel_id and self._channels.get(channel_id)

    @property
    def members(self):
        return list(self._members.values())

    def get_member(self, user_id):
        return self._members.get(user_id)

    @utils.cached_slot_property('_default_role')
    def default_role(self):
        return discord.utils.find(lambda r: r.is_default(), self.roles)

    @property
    def owner(self):
        return self.get_member(self.owner_id)

    @property
    def icon_url(self):
        return self.icon_url_as()

    def icon_url_as(self, *, format='webp', size=1024):
        if not discord.utils.valid_icon_size(size):
            raise discord.InvalidArgument("size must be a power of 2 between 16 and 1024")
        if format not in discord.guild.VALID_ICON_FORMATS:
            raise discord.InvalidArgument("format must be one of {}".format(discord.guild.VALID_ICON_FORMATS))

        if self.icon is None:
            return ''

        return 'https://cdn.discordapp.com/icons/{0.id}/{0.icon}.{1}?size={2}'.format(self, format, size)

    @property
    def splash_url(self):
        if self.splash is None:
            return ''
        return 'https://cdn.discordapp.com/splashes/{0.id}/{0.splash}.jpg?size=2048'.format(self)

    @property
    def member_count(self):
        return self._member_count

    @property
    def chunked(self):
        count = getattr(self, '_member_count', None)
        if count is None:
            return False
        return count == len(self._members)

    @property
    def shard_id(self):
        raise NotImplementedError

    @property
    def created_at(self):
        return discord.utils.snowflake_time(self.id)

    @property
    def role_hierarchy(self):
        return sorted(self.roles, reverse=True)

    def get_member_named(self, name):
        members = self.members
        if len(name) > 5 and name[-5] == '#':
            # The 5 length is checking to see if #0000 is in the string,
            # as a#0000 has a length of 6, the minimum for a potential
            # discriminator lookup.
            potential_discriminator = name[-4:]

            # do the actual lookup and return if found
            # if it isn't found then we'll do a full name lookup below.
            result = discord.utils.get(members, name=name[:-5], discriminator=potential_discriminator)
            if result is not None:
                return result

        def pred(m):
            return m.nick == name or m.name == name

        return discord.utils.find(pred, members)

    def _create_channel(self, name, overwrites, channel_type, category=None, reason=None):
        raise NotImplementedError

    @asyncio.coroutine
    def create_text_channel(self, name, *, overwrites=None, category=None, reason=None):
        data = yield from self._create_channel(name, overwrites, discord.ChannelType.text, category, reason=reason)
        channel = TextChannel(guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    @asyncio.coroutine
    def create_voice_channel(self, name, *, overwrites=None, category=None, reason=None):
        data = yield from self._create_channel(name, overwrites, discord.ChannelType.voice, category, reason=reason)
        channel = VoiceChannel(guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    @asyncio.coroutine
    def create_category(self, name, *, overwrites=None, reason=None):
        data = yield from self._create_channel(name, overwrites, discord.ChannelType.category, reason=reason)
        channel = CategoryChannel(guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    create_category_channel = create_category

    @asyncio.coroutine
    def leave(self):
        raise NotImplementedError

    @asyncio.coroutine
    def delete(self):
        raise NotImplementedError

    @asyncio.coroutine
    def edit(self, *, reason=None, **fields):
        raise NotImplementedError

    @asyncio.coroutine
    def bans(self):
        raise NotImplementedError

    @asyncio.coroutine
    def prune_members(self, *, days, reason=None):
        raise NotImplementedError

    @asyncio.coroutine
    def webhooks(self):
        raise NotImplementedError

    @asyncio.coroutine
    def estimate_pruned_members(self, *, days):
        raise NotImplementedError

    @asyncio.coroutine
    def invites(self):
        raise NotImplementedError

    @asyncio.coroutine
    def create_custom_emoji(self, *, name, image, reason=None):
        raise NotImplementedError

    @asyncio.coroutine
    def create_role(self, *, reason=None, **fields):
        raise NotImplementedError

    @asyncio.coroutine
    def kick(self, user, *, reason=None):
        raise NotImplementedError

    @asyncio.coroutine
    def ban(self, user, *, reason=None, delete_message_days=1):
        raise NotImplementedError

    @asyncio.coroutine
    def unban(self, user, *, reason=None):
        raise NotImplementedError

    @asyncio.coroutine
    def vanity_invite(self):
        raise NotImplementedError

    def ack(self):
        raise NotImplementedError

    def audit_logs(self, *, limit=100, before=None, after=None, reverse=None, user=None, action=None):
        if user:
            user = user.id

        if action:
            action = action.value

        return AuditLogIterator(self, before=before, after=after, limit=limit,
                                reverse=reverse, user_id=user, action_type=action)
