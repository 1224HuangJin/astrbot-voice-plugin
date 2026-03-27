# -*- coding: utf-8 -*-
import discord
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("discord_voice", "YourName", "Discord 语音频道控制插件", "1.0.0")
class DiscordVoicePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.allowed_user_ids = [] # 留空代表所有人均可使用

    async def initialize(self):
        """初始化方法"""
        logger.info("DiscordVoicePlugin 已成功加载！")

    def _check_user_allowed(self, user_id: str, user_name: str) -> bool:
        """检查用户是否有权限使用"""
        if not self.allowed_user_ids:
            return True
        return str(user_id) in self.allowed_user_ids or user_name in self.allowed_user_ids

    @filter.command("joinvc")
    async def joinvc(self, event: AstrMessageEvent):
        """让机器人加入你当前所在的 Discord 语音频道"""
        if event.get_platform_name() != "discord":
            yield event.plain_result("此指令仅限 Discord 平台使用！")
            return

        # 1. 获取底层对象
        raw_obj = getattr(event, 'raw_event', getattr(event.message_obj, 'raw_message', None))
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
        
        if not author or not guild:
            yield event.plain_result("❌ 无法解析 Discord 上下文。请确保你在 Discord 频道中发送指令。")
            return

        # 2. 权限检查
        if not self._check_user_allowed(author.id, author.name):
            yield event.plain_result("你没有权限使用此命令。")
            return

        # 3. 获取语音频道
        if not isinstance(author, discord.Member) or not author.voice or not author.voice.channel:
            yield event.plain_result("你需要先进入一个语音频道，我才能去找你！")
            return

        channel = author.voice.channel

        # 4. 执行连接逻辑 (修复核心错误)
        try:
            if guild.voice_client:
                if guild.voice_client.channel.id == channel.id:
                    yield event.plain_result(f"已经在 **{channel.name}** 里了。")
                    return
                await guild.voice_client.disconnect(force=True)

            # --- 修复点：不直接传递 self_deaf 参数 ---
            await channel.connect() 
            
            # --- 修复点：连接后，通过 change_voice_state 设置静音和拒听 ---
            await guild.change_voice_state(channel=channel, self_deaf=True, self_mute=True)
            
            logger.info(f'Bot joined voice channel: {channel.name}')

            # 尝试更新 Presence 状态
            try:
                client = guild.me._state._get_client()
                await client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=channel.name))
            except:
                pass

            yield event.plain_result(f"✅ 已成功加入并静音挂机: **{channel.name}**")

        except Exception as e:
            logger.error(f"语音连接出错: {e}")
            yield event.plain_result(f"连接失败：{str(e)}")

    @filter.command("leavevc")
    async def leavevc(self, event: AstrMessageEvent):
        """让机器人离开当前 Discord 语音频道"""
        if event.get_platform_name() != "discord": return

        raw_obj = getattr(event, 'raw_event', getattr(event.message_obj, 'raw_message', None))
        if hasattr(raw_obj, 'message'): raw_obj = raw_obj.message
        
        guild = getattr(raw_obj, 'guild', None)

        if guild and guild.voice_client:
            channel_name = guild.voice_client.channel.name
            await guild.voice_client.disconnect(force=True)
            
            # 恢复状态
            try:
                client = guild.me._state._get_client()
                await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="等待指令..."))
            except:
                pass
                
            yield event.plain_result(f"👋 已离开 **{channel_name}**")
        else:
            yield event.plain_result("我目前没在任何语音频道里。")
