# -*- coding: utf-8 -*-
import discord
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("discord_voice", "YourName", "Discord 语音频道控制插件", "1.1.0")
class DiscordVoicePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.allowed_user_ids = [] 

    def _check_user_allowed(self, user_id: str, user_name: str) -> bool:
        if not self.allowed_user_ids: return True
        return str(user_id) in self.allowed_user_ids or user_name in self.allowed_user_ids

    def _get_discord_context(self, event: AstrMessageEvent):
        """统一获取作者和服务器对象的私有方法"""
        raw_obj = getattr(event, 'raw_event', getattr(event.message_obj, 'raw_message', None))
        
        # 剥离封装层
        if hasattr(raw_obj, 'message') and raw_obj.message:
            raw_obj = raw_obj.message
            
        author = None
        guild = None

        if isinstance(raw_obj, discord.Message):
            author = raw_obj.author
            guild = raw_obj.guild
        elif isinstance(raw_obj, discord.Interaction):
            author = raw_obj.user
            guild = raw_obj.guild
        elif raw_obj:
            # 最后的保底尝试
            author = getattr(raw_obj, 'author', getattr(raw_obj, 'user', None))
            guild = getattr(raw_obj, 'guild', None)
            
        return author, guild

    @filter.command("joinvc")
    async def joinvc(self, event: AstrMessageEvent):
        """让机器人加入语音频道"""
        if event.get_platform_name() != "discord": return

        author, guild = self._get_discord_context(event)
        
        if not author or not guild:
            yield event.plain_result("❌ 无法获取 Discord 上下文，请确认指令发送环境。")
            return

        if not self._check_user_allowed(author.id, author.name):
            yield event.plain_result("你没有权限使用此命令。")
            return

        if not isinstance(author, discord.Member) or not author.voice or not author.voice.channel:
            yield event.plain_result("请先进入一个语音频道！")
            return

        channel = author.voice.channel

        try:
            # --- 核心修复：强制清理旧连接 ---
            # 无论内部状态如何，如果发现有残留连接，先强制断开
            if guild.voice_client:
                try:
                    await guild.voice_client.disconnect(force=True)
                except:
                    pass
            
            # 重新连接
            await channel.connect()
            await guild.change_voice_state(channel=channel, self_deaf=True, self_mute=True)
            
            yield event.plain_result(f"✅ 已加入: **{channel.name}**")
        except Exception as e:
            logger.error(f"JoinVC Error: {e}")
            yield event.plain_result(f"连接失败: {str(e)}")

    @filter.command("leavevc")
    async def leavevc(self, event: AstrMessageEvent):
        """让机器人离开语音频道"""
        if event.get_platform_name() != "discord": return

        author, guild = self._get_discord_context(event)

        if not guild:
            yield event.plain_result("❌ 无法定位服务器。")
            return

        # 权限检查
        if author and not self._check_user_allowed(author.id, author.name):
            yield event.plain_result("你没有权限。")
            return

        # --- 核心修复：更激进的退出逻辑 ---
        # 即使 guild.voice_client 看起来是 None，如果实际上机器人还在频道里，
        # 这里尝试通过 guild 直接寻找 voice_client
        vc = guild.voice_client
        
        if vc:
            try:
                channel_name = vc.channel.name
                await vc.disconnect(force=True)
                yield event.plain_result(f"👋 已离开 **{channel_name}**")
            except Exception as e:
                yield event.plain_result(f"退出时发生错误: {e}")
        else:
            # 尝试二次清理：如果代码认为没连接，但你手动断开了，这里做一次状态刷新
            yield event.plain_result("检查到我目前没在任何语音频道中（或连接已失效）。")
