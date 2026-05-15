# -*- coding: utf-8 -*-
import os
import asyncio
import discord
import edge_tts
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.event.filter import EventContext

@register("discord_voice_ai", "YourName", "Discord 语音 AI 自主对话插件", "2.0.0")
class DiscordVoiceAIPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.allowed_user_ids = [] 
        self.tts_voice = "zh-CN-XiaoxiaoNeural" # 默认晓晓女声
        # 绑定的文字频道 ID，只有在这个频道发消息（或者艾特）才会触发语音回复
        # 留空代表在任意文字频道艾特机器人，或者在机器人私聊里都会触发
        self.bind_text_channel_id = None 

    def _get_discord_context(self, event: AstrMessageEvent):
        raw_obj = getattr(event, 'raw_event', getattr(event.message_obj, 'raw_message', None))
        if hasattr(raw_obj, 'message') and raw_obj.message:
            raw_obj = raw_obj.message
        author, guild, channel = None, None, None
        if isinstance(raw_obj, discord.Message):
            author, guild, channel = raw_obj.author, raw_obj.guild, raw_obj.channel
        elif isinstance(raw_obj, discord.Interaction):
            author, guild, channel = raw_obj.user, raw_obj.guild, raw_obj.channel
        return author, guild, channel

    async def speak_text(self, guild, text: str):
        """核心封装：让机器人在当前语音频道把文字读出来"""
        if not guild or not guild.voice_client:
            return False
        
        # 如果正在说话，等待上一次说话结束（简单的防排队机制）
        while guild.voice_client.is_playing():
            await asyncio.sleep(0.5)

        filename = f"tts_{guild.id}.mp3"
        try:
            communicate = edge_tts.Communicate(text, self.tts_voice)
            await communicate.save(filename)
            
            # 驱动播放
            guild.voice_client.play(
                discord.FFmpegPCMAudio(filename), 
                after=lambda e: os.remove(filename) if os.path.exists(filename) else None
            )
            return True
        except Exception as e:
            if os.path.exists(filename): os.remove(filename)
            logger.error(f"语音合成或播放失败: {e}")
            return False

    @filter.command("joinvc")
    async def joinvc(self, event: AstrMessageEvent):
        """让机器人加入语音频道"""
        if event.get_platform_name() != "discord": return
        author, guild, _ = self._get_discord_context(event)
        if not author or not guild:
            yield event.plain_result("❌ 无法获取 Discord 上下文。")
            return
        if not isinstance(author, discord.Member) or not author.voice or not author.voice.channel:
            yield event.plain_result("请先进入一个语音频道！")
            return
        channel = author.voice.channel
        try:
            if guild.voice_client:
                try: await guild.voice_client.disconnect(force=True)
                except: pass
            await channel.connect()
            await guild.change_voice_state(channel=channel, self_deaf=True, self_mute=False)
            yield event.plain_result(f"✅ AI 语音已就绪！现在在文字频道艾特我，我会在 **{channel.name}** 里语音回答你。")
        except Exception as e:
            yield event.plain_result(f"连接失败: {str(e)}")

    @filter.on_decorating_result()
    async def on_ai_reply(self, ctx: EventContext):
        """【核心魔法】拦截 AI 的回复，并将其同步转换为语音播放"""
        event = ctx.event
        if event.get_platform_name() != "discord": return
        
        author, guild, text_channel = self._get_discord_context(event)
        
        # 如果机器人根本没进语音频道，就不折腾语音，直接让它正常走文字回复
        if not guild or not guild.voice_client:
            return

        # 获取 AI 准备回复的文本内容
        result = ctx.get_result()
        if not result or not result.chain:
            return

        # 提取出纯文本回复
        ai_text = result.get_plain_text()
        if not ai_text:
            return

        # 异步调用语音播放（不阻塞原有的文字发送，它会同时发文字 + 说话）
        asyncio.create_task(self.speak_text(guild, ai_text))

    @filter.command("leavevc")
    async def leavevc(self, event: AstrMessageEvent):
        """让机器人离开语音频道"""
        if event.get_platform_name() != "discord": return
        _, guild, _ = self._get_discord_context(event)
        if guild and guild.voice_client:
            channel_name = guild.voice_client.channel.name
            await guild.voice_client.disconnect(force=True)
            yield event.plain_result(f"👋 语音对话已关闭。")
        else:
            yield event.plain_result("我目前没在任何语音频道里。")
