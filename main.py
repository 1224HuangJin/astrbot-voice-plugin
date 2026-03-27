# -*- coding: utf-8 -*-
import discord
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("discord_voice", "YourName", "Discord 语音频道控制插件", "1.0.0")
class DiscordVoicePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 在这里配置你的白名单机制 (可以根据需要改写为从配置文件读取)
        self.allowed_user_ids = [] # 留空代表所有人均可使用

    async def initialize(self):
        """初始化方法"""
        logger.info("DiscordVoicePlugin 已成功加载！")

    def _check_user_allowed(self, user_id: str, user_name: str) -> bool:
        """检查用户是否有权限使用"""
        if not self.allowed_user_ids:
            return True
        return user_id in self.allowed_user_ids or user_name in self.allowed_user_ids
@filter.command("joinvc")
    async def joinvc(self, event: AstrMessageEvent):
        # 1. 平台检查
        if event.get_platform_name() != "discord":
            yield event.plain_result("此指令仅限 Discord 平台使用！")
            return

        # 2. 改进后的底层对象获取方式
        # 尝试从不同的地方抓取 discord.Message
        raw_msg = None
        if hasattr(event.message_obj, 'raw_message'):
            raw_msg = event.message_obj.raw_message
        
        # 如果拿到的是封装过的对象，尝试进一步提取
        if hasattr(raw_msg, 'message'): 
            raw_msg = raw_msg.message

        if not isinstance(raw_msg, discord.Message):
            # 最后的调试手段：打印出类型看看它到底是什么
            logger.error(f"Debug: raw_msg type is {type(raw_msg)}")
            yield event.plain_result(f"获取底层对象失败。类型: {type(raw_msg).__name__}")
            return

        # --- 以下逻辑保持不变 ---
        author = raw_msg.author
        guild = raw_msg.guild
        # ... 后面接你之前的代码

        # 3. 权限检查
        if not self._check_user_allowed(str(author.id), author.name):
            yield event.plain_result(f"你没有权限使用此命令。*(UserID: `{author.id}`, UserName: `{author.name}`)*")
            return

        # 4. 获取用户当前的语音频道
        if not isinstance(author, discord.Member) or not author.voice or not author.voice.channel:
            yield event.plain_result("你需要先加入一个语音频道！")
            return

        channel = author.voice.channel
        if isinstance(channel, discord.StageChannel):
            yield event.plain_result("目前不支持直接加入舞台频道 (StageChannel)。")
            return

        # 5. 执行加入逻辑
        try:
            if guild.voice_client:
                # 机器人已在语音频道
                if guild.voice_client.channel.id == channel.id:
                    yield event.plain_result(f"我已经呆在 **{channel.name}** 里啦。")
                    return
                # 在其他频道则先断开
                await guild.voice_client.disconnect(force=False)

            # 连接并默认静音/拒听
            await channel.connect(self_deaf=True, self_mute=True)
            logger.info(f'Bot joined voice channel: {channel.name} (ID: {channel.id})')
            
            # (可选) 尝试更新机器人状态
            # 注意: 此处依赖于底层 Client，如果 AstrBot 层面封装较深可能不会生效
            if guild.me and guild.me.guild.voice_client:
                client = guild.me._state._get_client()
                await client.change_presence(
                    activity=discord.Activity(
                        type=discord.ActivityType.listening,
                        name=channel.name
                    )
                )

            yield event.plain_result(f"✅ 已成功加入 **{channel.name}**")

        except discord.errors.ConnectionClosed as exc:
            if exc.code == 4017:
                yield event.plain_result("频道要求 DAVE 加密端到端连接，但连接失败。")
            else:
                logger.error(f'Connection closed: {exc}')
                yield event.plain_result(f"连接断开：{exc}")
        except discord.ClientException as e:
            logger.error(f'Failed to join voice channel: {e}')
            yield event.plain_result(f"连接失败：{e}")
        except Exception as e:
            logger.error(f'Unexpected error in joinvc: {type(e).__name__}: {e}')
            yield event.plain_result(f"发生未知错误：{type(e).__name__}")

    @filter.command("leavevc")
    async def leavevc(self, event: AstrMessageEvent):
        """让机器人离开当前 Discord 语音频道"""
        platform = event.get_platform_name()
        if platform != "discord":
            yield event.plain_result("此指令仅限 Discord 平台使用！")
            return

        raw_msg = event.message_obj.raw_message
        if not isinstance(raw_msg, discord.Message):
            yield event.plain_result("获取 Discord 底层消息对象失败。")
            return

        author = raw_msg.author
        guild = raw_msg.guild

        # 权限检查
        if not self._check_user_allowed(str(author.id), author.name):
            yield event.plain_result("你没有权限使用此命令。")
            return

        if not guild or not guild.voice_client:
            yield event.plain_result("我目前没在任何语音频道里。")
            return

        channel_name = guild.voice_client.channel.name
        await guild.voice_client.disconnect(force=False)
        logger.info(f'Bot left voice channel: {channel_name}')
        
        # (可选) 恢复机器人状态
        if guild.me:
            try:
                client = guild.me._state._get_client()
                await client.change_presence(
                    activity=discord.Activity(
                        type=discord.ActivityType.watching,
                        name="等待指令..."
                    )
                )
            except Exception:
                pass

        yield event.plain_result(f"👋 已离开 **{channel_name}**")
