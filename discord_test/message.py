# Stdlib
import asyncio
import re

# External Libraries
import discord

# discord.py-test
from discord_test import Embed, Reaction, CallMessage


class Attachment(discord.Attachment):
    def __init__(self, *, data):
        self.id = int(data['id'])
        self.size = data['size']
        self.height = data.get('height')
        self.width = data.get('width')
        self.filename = data['filename']
        self.url = data.get('url')
        self.proxy_url = data.get('proxy_url')

    @asyncio.coroutine
    def save(self, fp, *, seek_begin=True):
        raise NotImplementedError


class Message(discord.Message):
    def __init__(self, *, channel, data):
        self.id = int(data['id'])
        self.webhook_id = discord.utils._get_as_snowflake(data, 'webhook_id')
        self.reactions = [
            Reaction(message=self, data=d) for d in data.get('reactions', [])
        ]
        self._update(channel, data)

    def __repr__(self):
        return '<Message id={0.id} pinned={0.pinned} author={0.author!r}>'.format(
            self)

    def _try_patch(self, data, key, transform=None):
        try:
            value = data[key]
        except KeyError:
            pass
        else:
            if transform is None:
                setattr(self, key, value)
            else:
                setattr(self, key, transform(value))

    def _add_reaction(self, data, emoji, user_id):
        raise NotImplementedError

    def _remove_reaction(self, data, emoji, user_id):
        raise NotImplementedError

    def _update(self, channel, data):
        self.channel = channel
        self._edited_timestamp = discord.utils.parse_time(
            data.get('edited_timestamp'))
        self._try_patch(data, 'pinned')
        self._try_patch(data, 'mention_everyone')
        self._try_patch(data, 'tts')
        self._try_patch(
            data, 'type',
            lambda x: discord.enums.try_enum(discord.MessageType, x))
        self._try_patch(data, 'content')
        self._try_patch(
            data, 'attachments',
            lambda x: [Attachment(data=a, state=self._state) for a in x])
        self._try_patch(data, 'embeds',
                        lambda x: list(map(Embed.from_data, x)))
        self._try_patch(data, 'nonce')

        for handler in ('author', 'mentions', 'mention_roles', 'call'):
            try:
                getattr(self, '_handle_%s' % handler)(data[handler])
            except KeyError:
                continue

        # clear the cached properties
        cached = filter(lambda attr: attr.startswith('_cs_'), self.__slots__)
        for attr in cached:
            try:
                delattr(self, attr)
            except AttributeError:
                pass

    def _handle_author(self, author):
        raise NotImplementedError

    def _handle_mentions(self, mentions):
        raise NotImplementedError

    def _handle_mention_roles(self, role_mentions):
        self.role_mentions = []
        if self.guild is not None:
            for role_id in map(int, role_mentions):
                role = discord.utils.get(self.guild.roles, id=role_id)
                if role is not None:
                    self.role_mentions.append(role)

    def _handle_call(self, call):
        if call is None or self.type is not discord.MessageType.call:
            self.call = None
            return

        # we get the participant source from the mentions array or
        # the author

        participants = []
        for uid in map(int, call.get('participants', [])):
            if uid == self.author.id:
                participants.append(self.author)
            else:
                user = discord.utils.find(lambda u: u.id == uid, self.mentions)
                if user is not None:
                    participants.append(user)

        call['participants'] = participants
        self.call = CallMessage(message=self, **call)

    @discord.utils.cached_slot_property('_cs_guild')
    def guild(self):
        return getattr(self.channel, 'guild', None)

    @discord.utils.cached_slot_property('_cs_raw_mentions')
    def raw_mentions(self):
        return [int(x) for x in re.findall(r'<@!?([0-9]+)>', self.content)]

    @discord.utils.cached_slot_property('_cs_raw_channel_mentions')
    def raw_channel_mentions(self):
        return [int(x) for x in re.findall(r'<#([0-9]+)>', self.content)]

    @discord.utils.cached_slot_property('_cs_raw_role_mentions')
    def raw_role_mentions(self):
        return [int(x) for x in re.findall(r'<@&([0-9]+)>', self.content)]

    @discord.utils.cached_slot_property('_cs_channel_mentions')
    def channel_mentions(self):
        if self.guild is None:
            return []
        it = filter(None,
                    map(lambda m: self.guild.get_channel(m),
                        self.raw_channel_mentions))
        return discord.utils._unique(it)

    @discord.utils.cached_slot_property('_cs_clean_content')
    def clean_content(self):
        transformations = {
            re.escape('<#%s>' % channel.id): '#' + channel.name
            for channel in self.channel_mentions
        }

        mention_transforms = {
            re.escape('<@%s>' % member.id): '@' + member.display_name
            for member in self.mentions
        }

        # add the <@!user_id> cases as well..
        second_mention_transforms = {
            re.escape('<@!%s>' % member.id): '@' + member.display_name
            for member in self.mentions
        }

        transformations.update(mention_transforms)
        transformations.update(second_mention_transforms)

        if self.guild is not None:
            role_transforms = {
                re.escape('<@&%s>' % role.id): '@' + role.name
                for role in self.role_mentions
            }
            transformations.update(role_transforms)

        def repl(obj):
            return transformations.get(re.escape(obj.group(0)), '')

        pattern = re.compile('|'.join(transformations.keys()))
        result = pattern.sub(repl, self.content)

        transformations = {
            '@everyone': '@\u200beveryone',
            '@here': '@\u200bhere'
        }

        def repl2(obj):
            return transformations.get(obj.group(0), '')

        pattern = re.compile('|'.join(transformations.keys()))
        return pattern.sub(repl2, result)

    @property
    def created_at(self):
        return discord.utils.snowflake_time(self.id)

    @property
    def edited_at(self):
        return self._edited_timestamp

    @discord.utils.cached_slot_property('_cs_system_content')
    def system_content(self):
        if self.type is discord.MessageType.default:
            return self.content

        if self.type is discord.MessageType.pins_add:
            return '{0.name} pinned a message to this channel.'.format(
                self.author)

        if self.type is discord.MessageType.recipient_add:
            return '{0.name} added {1.name} to the group.'.format(
                self.author, self.mentions[0])

        if self.type is discord.MessageType.recipient_remove:
            return '{0.name} removed {1.name} from the group.'.format(
                self.author, self.mentions[0])

        if self.type is discord.MessageType.channel_name_change:
            return '{0.author.name} changed the channel name: {0.content}'.format(
                self)

        if self.type is discord.MessageType.channel_icon_change:
            return '{0.author.name} changed the channel icon.'.format(self)

        if self.type is discord.MessageType.new_member:
            formats = [
                "{0} just joined the server - glhf!",
                "{0} just joined. Everyone, look busy!",
                "{0} just joined. Can I get a heal?",
                "{0} joined your party.",
                "{0} joined. You must construct additional pylons.",
                "Ermagherd. {0} is here.",
                "Welcome, {0}. Stay awhile and listen.",
                "Welcome, {0}. We were expecting you ( ͡° ͜ʖ ͡°)",
                "Welcome, {0}. We hope you brought pizza.",
                "Welcome {0}. Leave your weapons by the door.",
                "A wild {0} appeared.",
                "Swoooosh. {0} just landed.",
                "Brace yourselves. {0} just joined the server.",
                "{0} just joined. Hide your bananas.",
                "{0} just arrived. Seems OP - please nerf.",
                "{0} just slid into the server.",
                "A {0} has spawned in the server.",
                "Big {0} showed up!",
                "Where’s {0}? In the server!",
                "{0} hopped into the server. Kangaroo!!",
                "{0} just showed up. Hold my beer.",
                "Challenger approaching - {0} has appeared!",
                "It's a bird! It's a plane! Nevermind, it's just {0}.",
                "It's {0}! Praise the sun! [T]/",
                "Never gonna give {0} up. Never gonna let {0} down.",
                "Ha! {0} has joined! You activated my trap card!",
                "Cheers, love! {0}'s here!",
                "Hey! Listen! {0} has joined!",
                "We've been expecting you {0}",
                "It's dangerous to go alone, take {0}!",
                "{0} has joined the server! It's super effective!",
                "Cheers, love! {0} is here!",
                "{0} is here, as the prophecy foretold.",
                "{0} has arrived. Party's over.",
                "Ready player {0}",
                "{0} is here to kick butt and chew bubblegum. And {0} is all out of gum.",
                "Hello. Is it {0} you're looking for?",
                "{0} has joined. Stay a while and listen!",
                "Roses are red, violets are blue, {0} joined this server with you",
            ]

            index = int(self.created_at.timestamp()) % len(formats)
            return formats[index].format(self.author.name)

        if self.type is discord.MessageType.call:
            # we're at the call message type now, which is a bit more complicated.
            # we can make the assumption that Message.channel is a PrivateChannel
            # with the type ChannelType.group or ChannelType.private
            call_ended = self.call.ended_timestamp is not None

            if self.channel.me in self.call.participants:
                return '{0.author.name} started a call.'.format(self)
            elif call_ended:
                return 'You missed a call from {0.author.name}'.format(self)
            else:
                return '{0.author.name} started a call \N{EM DASH} Join the call.'.format(
                    self)

    @asyncio.coroutine
    def delete(self):
        raise NotImplementedError

    @asyncio.coroutine
    def edit(self, **fields):
        raise NotImplementedError

    @asyncio.coroutine
    def pin(self):
        raise NotImplementedError

    @asyncio.coroutine
    def unpin(self):
        raise NotImplementedError

    @asyncio.coroutine
    def add_reaction(self, emoji):
        raise NotImplementedError

    @asyncio.coroutine
    def remove_reaction(self, emoji, member):
        raise NotImplementedError

    @asyncio.coroutine
    def clear_reactions(self):
        raise NotImplementedError

    def ack(self):
        raise NotImplementedError
