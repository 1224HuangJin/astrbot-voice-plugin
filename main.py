# -*- coding: utf-8 -*-
import discord
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("discord_voice", "YourName", "Discord 语音频道控制插件", "1.0.0")
class DiscordVoicePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 在这里配置你的白名单机制
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
        # 1. 平台检查
        if event.get_platform_name() != "discord":
            yield event.plain_result("此指令仅限 Discord 平台使用！")
            return

        # 2. 【核心修复】多重尝试获取底层 Discord 对象
        raw_obj = None
        
        # 尝试 A: 从 raw_event 获取 (最直接)
        if hasattr(event, 'raw_event') and event.raw_event:
            raw_obj = event.raw_event
        # 尝试 B: 从 message_obj.raw_message 获取
        elif hasattr(event.message_obj, 'raw_message') and event.message_obj.raw_message:
            raw_obj = event.message_obj.raw_message

        # 如果拿到的对象是封装层，再往里剥一层
        if hasattr(raw_obj, 'message') and raw_obj.message:
            raw_obj = raw_obj.message

        # 3. 解析对象属性 (适配 Message 和 Interaction)
        author = None
        guild = None

        if isinstance(raw_obj, discord.Message):
            author = raw_obj.author
            guild = raw_obj.guild
        elif isinstance(raw_obj, discord.Interaction):
            author = raw_obj.user
            guild = raw_obj.guild
        elif raw_obj is None:
            # 如果还是 None，打印整个 event 结构供调试
            logger.error(f"无法获取底层对象。Event 包含的属性: {dir(event)}")
            yield event.plain_result("❌ 错误：底层对象为 None。请查看后台日志。")
            return
        else:
            # 走到这里说明抓到了对象但不是预期的类型
            logger.error(f"抓取对象类型异常: {type(raw_obj)}")
            # 尝试暴力获取
            author = getattr(raw_obj, 'author', getattr(raw_obj, 'user', None))
            guild = getattr(raw_obj, 'guild', None)

        if not author or not guild:
            yield event.plain_result(f"解析用户信息失败 (类型: {type(raw_obj).__name__})")
            return

        # 4. 权限检查
        if not self._check_user_allowed(author.id, author.name):
            yield event.plain_result(f"你没有权限使用此命令。")
            return

        # 5. 获取语音频道
        if not isinstance(author, discord.Member) or not author.voice or not author.voice.channel:
            yield event.plain_result("你需要先进入一个语音频道，我才能去找你！")
            return

        channel = author.voice.channel
        if isinstance(channel, discord.StageChannel):
            yield event.plain_result("不支持直接加入舞台频道。")
            return

        # 6. 执行加入逻辑
        try:
            if guild.voice_client:
                if guild.voice_client.channel.id == channel.id:
                    yield event.plain_result(f"已经在 **{channel.name}** 里了。")
                    return
                await guild.voice_client.disconnect(force=True)

            await channel.connect(self_deaf=True, self_mute=True)
            
            # 更新状态 (尝试执行)
            try:
                client = guild.me._state._get_client()
                await client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=channel.name))
            except:
                pass

            yield event.plain_result(f"✅ 已成功加入 **{channel.name}**")

        except Exception as e:
            logger.error(f"语音连接出错: {e}")
            yield event.plain_result(f"连接失败: {str(e)}")

    @filter.command("leavevc")
    async def leavevc(self, event: AstrMessageEvent):
        """让机器人离开当前 Discord 语音频道"""
        if event.get_platform_name() != "discord": return

        # 同样使用强力抓取
        raw_obj = getattr(event, 'raw_event', getattr(event.message_obj, 'raw_message', None))
        if hasattr(raw_obj, 'message'): raw_obj = raw_obj.message
        
        guild = getattr(raw_obj, 'guild', None)

        if guild and guild.voice_client:
            channel_name = guild.voice_client.channel.name
            await guild.voice_client.disconnect(force=True)
            yield event.plain_result(f"👋 已离开 **{channel_name}**")
        else:
            yield event.plain_result("我目前没在任何语音频道里。")
