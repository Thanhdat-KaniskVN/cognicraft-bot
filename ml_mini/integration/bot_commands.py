# ml_mini/integration/bot_commands.py
"""
ML Bot Commands - Discord commands cho ML Mini
"""
import discord
from discord.ext import commands
from .ml_manager import get_ml_manager


def setup_ml_commands(bot, is_admin):
    """Setup ML commands vào bot"""
    
    @bot.command(name="ml_status")
    async def ml_status_cmd(ctx):
        """Xem trạng thái ML Mini"""
        if not is_admin(ctx):
            await ctx.send("❌ Chỉ Admin.")
            return
        
        manager = get_ml_manager()
        status = manager.get_status()
        stats = manager.get_stats()
        
        embed = discord.Embed(
            title="🧠 ML MINI STATUS",
            description=f"**Sandboxes:** {status['total_sandboxes']} | **Links:** {status['total_links']}",
            color=discord.Color.purple(),
        )
        
        # Stats
        embed.add_field(
            name="📊 Health",
            value=(
                f"🟢 Healthy: {stats['healthy']}\n"
                f"🟡 Recovering: {stats['recovering']}\n"
                f"🔴 Down: {stats['down']}\n"
                f"⚫ Dead: {stats['dead']}"
            ),
            inline=True,
        )
        
        # Sandbox details
        sb_text = ""
        for sid, sb in status["sandboxes"].items():
            icon = {"healthy": "🟢", "down": "🔴", "recovering": "🟡"}.get(sb["state"], "⚪")
            sb_text += f"{icon} **{sb['name']}**\n"
            sb_text += f"   Restarts: {sb['restart_count']} | HB: {sb['heartbeat_interval']}s\n"
        
        embed.add_field(name="🔌 Sandboxes", value=sb_text[:1000], inline=False)
        
        embed.set_footer(text=f"Heartbeat: adaptive 1-15s")
        await ctx.send(embed=embed)
    
    @bot.command(name="ml_predict")
    async def ml_predict_cmd(ctx, member: str, weeks: int = 4):
        """Dự đoán điểm số tuần tới"""
        if not is_admin(ctx):
            await ctx.send("❌ Chỉ Admin.")
            return
        
        manager = get_ml_manager()
        result = await manager.predict_score(member, weeks)
        
        if "error" in result:
            await ctx.send(f"❌ {result['error']}")
            return
        
        embed = discord.Embed(
            title=f"🔮 DỰ ĐOÁN – {member.upper()}",
            description=f"**Model:** `{result.get('model')}`",
            color=discord.Color.purple(),
        )
        
        embed.add_field(
            name="📊 Hiện tại",
            value=(
                f"Điểm gần nhất: **{result.get('current_score')}**\n"
                f"Cohort avg: **{result.get('cohort_avg')}**\n"
                f"Trend: **{result.get('trend')}**\n"
                f"Slope: **{result.get('slope')}**\n"
                f"R²: **{result.get('r2_score')}**"
            ),
            inline=False,
        )
        
        # Predictions
        pred_text = ""
        for p in result.get("predictions", []):
            pred_text += f"**W+{p['week_ahead']}**: {p['predicted_score']}/5\n"
        
        embed.add_field(
            name=f"🔮 {weeks} tuần tới",
            value=pred_text or "Không có dự đoán",
            inline=False,
        )
        
        if result.get("note"):
            embed.add_field(name="ℹ️ Note", value=result["note"], inline=False)
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)
    
    @bot.command(name="ml_anomaly")
    async def ml_anomaly_cmd(ctx, member: str = None):
        """Check anomaly"""
        if not is_admin(ctx):
            await ctx.send("❌ Chỉ Admin.")
            return
        
        manager = get_ml_manager()
        result = await manager.detect_anomalies(member)
        
        if member:
            # Single member
            embed = discord.Embed(
                title=f"🚨 ANOMALY – {member.upper()}",
                color=discord.Color.green() if not result.get("is_anomaly") else discord.Color.red(),
            )
            
            embed.add_field(
                name="📊 Stats",
                value=(
                    f"Latest: **{result.get('latest_score')}**\n"
                    f"Mean: **{result.get('mean')}**\n"
                    f"Std: **{result.get('std')}**\n"
                    f"N samples: **{result.get('n_samples')}**"
                ),
                inline=False,
            )
            
            anomalies = result.get("anomalies", [])
            if not anomalies:
                embed.add_field(
                    name="✅ Kết quả",
                    value="Không phát hiện bất thường",
                    inline=False,
                )
            else:
                anom_text = ""
                for a in anomalies:
                    icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(a["severity"], "⚪")
                    anom_text += f"{icon} **{a['type']}**: {a['message']}\n"
                
                embed.add_field(name=f"⚠️ Phát hiện ({len(anomalies)})", value=anom_text[:1000], inline=False)
        else:
            # All members
            embed = discord.Embed(
                title="🚨 ANOMALY SCAN – TOÀN COHORT",
                description=f"Members: {result.get('total_members')} | Anomalies: {result.get('anomalies_found')}",
                color=discord.Color.orange() if result.get('anomalies_found', 0) > 0 else discord.Color.green(),
            )
            
            for r in result.get("results", [])[:5]:
                if not r.get("is_anomaly"):
                    continue
                
                anom_text = "\n".join(
                    f"• {a['type']}: {a['message'][:60]}"
                    for a in r.get("anomalies", [])
                )
                embed.add_field(
                    name=f"⚠️ {r['member']} ({r.get('latest_score')}/5)",
                    value=anom_text[:200],
                    inline=False,
                )
        
        await ctx.send(embed=embed)
    
    @bot.command(name="ml_tokens")
    async def ml_tokens_cmd(ctx, task: str, prompt_length: int = 1500):
        """Dự đoán tokens cho task"""
        if not is_admin(ctx):
            await ctx.send("❌ Chỉ Admin.")
            return
        
        manager = get_ml_manager()
        result = await manager.predict_tokens(task, prompt_length)
        
        embed = discord.Embed(
            title=f"⚡ TOKEN PREDICTION – {task}",
            description=f"**Model:** `{result.get('model')}`",
            color=discord.Color.blue(),
        )
        
        embed.add_field(
            name="📊 Prediction",
            value=(
                f"Predicted: **{result.get('predicted_tokens'):,}** tokens\n"
                f"Confidence: **{result.get('confidence')}**\n"
                f"Prompt: **{prompt_length:,}** chars"
            ),
            inline=False,
        )
        
        breakdown = result.get("breakdown", {})
        if breakdown:
            embed.add_field(
                name="🔧 Breakdown",
                value=(
                    f"Base: {breakdown.get('base'):,}\n"
                    f"Multiplier: {breakdown.get('multiplier')}x\n"
                    f"Final: {breakdown.get('final'):,}"
                ),
                inline=False,
            )
        
        await ctx.send(embed=embed)
    
    @bot.command(name="ml_sandboxes")
    async def ml_sandboxes_cmd(ctx):
        """List tất cả sandboxes"""
        if not is_admin(ctx):
            await ctx.send("❌ Chỉ Admin.")
            return
        
        manager = get_ml_manager()
        status = manager.get_status()
        
        msg = "# 🔌 ML MINI SANDBOXES\n\n"
        
        for sid, sb in status["sandboxes"].items():
            icon = {"healthy": "🟢", "down": "🔴", "recovering": "🟡"}.get(sb["state"], "⚪")
            msg += f"{icon} **{sb['name']}** (`{sid}`)\n"
            msg += f"   State: `{sb['state']}`\n"
            msg += f"   Restarts: {sb['restart_count']}\n"
            msg += f"   Heartbeat: {sb['heartbeat_interval']}s\n\n"
        
        msg += f"**Links:** {status['total_links']}\n"
        for link in status.get("links", []):
            msg += f"  {link[0]} ↔ {link[1]}\n"
        
        await ctx.send(msg)
    
    @bot.command(name="ml_events")
    async def ml_events_cmd(ctx, limit: int = 15):
        """Xem event log"""
        if not is_admin(ctx):
            await ctx.send("❌ Chỉ Admin.")
            return
        
        manager = get_ml_manager()
        events = manager.get_events(limit)
        
        if not events:
            await ctx.send("📭 Chưa có events.")
            return
        
        msg = f"# 📋 ML MINI EVENTS (last {limit})\n\n"
        for e in events:
            time = e["time"][11:19]
            msg += f"`{time}` **{e['type']}** – {e['sandbox']}\n"
            msg += f"  _{e['message']}_\n\n"
        
        await ctx.send(msg[:2000])
    
    @bot.command(name="ml_restart")
    async def ml_restart_cmd(ctx, sandbox_id: str):
        """Force restart 1 sandbox"""
        if not is_admin(ctx):
            await ctx.send("❌ Chỉ Admin.")
            return
        
        manager = get_ml_manager()
        
        if sandbox_id not in manager.coordinator.sandboxes:
            await ctx.send(f"❌ Sandbox `{sandbox_id}` không tồn tại.")
            return
        
        await ctx.send(f"🔄 Restarting `{sandbox_id}`...")
        
        try:
            await manager.coordinator.force_restart(sandbox_id)
            await ctx.send(f"✅ Đã trigger restart `{sandbox_id}`")
        except Exception as e:
            await ctx.send(f"❌ Lỗi: {e}")
    
    @bot.command(name="ml_health")
    async def ml_health_cmd(ctx):
        """Health check toàn ML Mini"""
        if not is_admin(ctx):
            await ctx.send("❌ Chỉ Admin.")
            return
        
        manager = get_ml_manager()
        coordinator = manager.coordinator
        
        # Check all sandboxes
        results = await coordinator.registry.health_check_all() if hasattr(coordinator, "registry") else {}
        
        msg = "# 🏥 ML MINI HEALTH CHECK\n\n"
        
        for sid, data in coordinator.sandboxes.items():
            instance = data["instance"]
            try:
                alive = await instance.health_check()
                icon = "💚" if alive else "💔"
                msg += f"{icon} **{instance.NAME}** – {'ALIVE' if alive else 'DOWN'}\n"
            except Exception as e:
                msg += f"❌ **{instance.NAME}** – ERROR: {e}\n"
        
        await ctx.send(msg)
    
    print("[MLCommands] ✅ ML commands loaded")