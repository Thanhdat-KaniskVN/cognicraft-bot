# bot.py
import discord
from discord.ext import commands, tasks
from datetime import datetime, time
import pytz
import asyncio

from config import (
    DISCORD_TOKEN, CHECKPOINT_CHANNEL, ADMIN_REVIEW_CHANNEL,
    REPORT_CHANNEL, ADMIN_ROLE, ALL_MEMBERS, TIMEZONE,
    AI_SCORING_DAY, REPORT_DAY, TASK_HOUR, TASK_MINUTE,
)
from database import (
    init_db, save_score, get_week_scores, get_pending_score,
    update_score_source, save_participation, get_week_participation,
    get_score_history,
)
from collector import CheckpointCollector
from ai_scorer import AIScorer
from scorer import Scorer
from coverage import CoverageAnalyzer
from knowledge_bar import KnowledgeBar
from reporter import Reporter
from distiller import Distiller
from time_tracker import TimeTracker
from solution_proposer import SolutionProposer
from exercise_generator import ExerciseGenerator
from spaced_repetition import SpacedRepetition
from error_tracker import ErrorTracker
from resource_recommender import ResourceRecommender
from access_control import AccessControl
from socratic_tutor import SocraticTutor
from practice_quiz import PracticeQuiz
from progress_predictor import ProgressPredictor
from chat_bot import ChatBot
from weekly_planner import WeeklyPlanner
from advanced_mode import AdvancedMode
from slash_commands import setup_slash_commands
import httpx  # Cho Switch Board API call
from plugin_loader import PluginLoader
from core_api import CoreAPI
from event_bus import event_bus
from plugin_commands import setup_plugin_commands
from plugin_hub import PluginHub
from hub_commands import setup_hub_commands
import logging

# Tắt warning "Clock drift" spam
logging.getLogger("discord.ext.tasks").setLevel(logging.ERROR)
# ML Mini
from ml_mini.integration.ml_manager import get_ml_manager
from ml_mini.integration.bot_commands import setup_ml_commands
from ml_mini.integration.switch_hook import MLSwitchHook


# ============ SETUP ============

# Root directory for module caches.
CACHE_DIR = "cache"
# Switch Board URL (chạy ở terminal riêng)
SWITCH_BOARD_URL = "http://localhost:8000"
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
TZ = pytz.timezone(TIMEZONE)

# Modules
collector = CheckpointCollector(bot, ALL_MEMBERS)
ai_scorer = AIScorer()
scorer = Scorer()
coverage_analyzer = CoverageAnalyzer("roadmap.json")
reporter = Reporter()
distiller = Distiller()
time_tracker = TimeTracker()
solution_proposer = SolutionProposer()
exercise_generator = ExerciseGenerator()
spaced_repetition = SpacedRepetition()
error_tracker = ErrorTracker()
resource_recommender = ResourceRecommender()
access_control = AccessControl()
socratic_tutor = SocraticTutor()
practice_quiz = PracticeQuiz()
progress_predictor = ProgressPredictor()
chat_bot = ChatBot()
weekly_planner = WeeklyPlanner()
advanced_mode = AdvancedMode()
# Plugin System
plugin_loader = PluginLoader(plugins_dir="plugins")
plugin_hub = PluginHub(
    registry_file="hub_registry.json",
    plugins_dir="plugins",

)
# Init SheetsSync
try:
    from sheets_sync import SheetsSync
    sheets = SheetsSync(max_retries=5)
    print("[Bot] Google Sheets connected")
except Exception as e:
    print(f"[Bot] WARNING: SheetsSync failed: {e}")
    print("[Bot] Bot se chay nhung KHONG sync Google Sheets")
    sheets = None

# Guard để tránh sync slash commands nhiều lần khi bot reconnect
_synced_once = False


# ============ HELPERS ============

def get_current_week():
    return time_tracker.get_ground_truth_week()


def is_admin(ctx):
    """Kiểm tra quyền admin an toàn (tránh crash trong DM)."""
    roles = getattr(ctx.author, "roles", None)
    if not roles:
        return False
    return any(r.name.lower() == ADMIN_ROLE.lower() for r in roles)


async def generate_final_report(week, channel):
    if channel is None:
        print(f"[Report] Channel not found for week {week}")
        return

    scores = get_week_scores(week)
    participation = get_week_participation(week)

    lines = [f"# 📊 BÁO CÁO TUẦN {week}", ""]
    if not scores:
        lines.append("Chưa có điểm nào được ghi nhận.")
    else:
        for score in scores:
            member = score.get("member", "?")
            total = score.get("total", scorer.calculate_total(score))
            lines.append(f"- **{member}**: {total}/5")

    if participation:
        missing = [m for m, submitted in participation.items() if not submitted]
        if missing:
            lines.extend(["", f"**Chưa nộp:** {', '.join(missing)}"])

    for part in reporter._split("\n".join(lines)):
        await channel.send(part)


# ============ EVENTS ============

# ✅ Flag toàn cục – chỉ sync slash commands 1 lần
_slash_synced = False

@bot.event
async def on_ready():
    init_db()
    print(f"Bot san sang: {bot.user}")
    print(f"Current week: {get_current_week()}")

    debug = time_tracker.debug_info()
    print(f"[TimeTracker] Start date: {debug['roadmap_start_date']}")
    print(f"[TimeTracker] Override: {debug['override_week']}")
    print(f"[TimeTracker] Mode: {debug['current_info']['mode']}")

    # ❌ KHÔNG sync slash commands trong on_ready nữa
    # → Dùng lệnh !sync_commands khi cần
    
    if not ai_scoring_task.is_running():
        ai_scoring_task.start()
    if not report_task.is_running():
        report_task.start()
    if not ml_refresh_task.is_running():
        ml_refresh_task.start()

    # Setup Core API cho plugins
    core_modules = {
        "get_week_scores": get_week_scores,
        "get_pending_score": get_pending_score,
        "save_score": save_score,
        "update_score_source": update_score_source,
        "get_week_participation": get_week_participation,
        "get_score_history": get_score_history,
        "get_current_week": get_current_week,
        "is_admin": is_admin,
        "time_tracker": time_tracker,
        "collector": collector,
        "sheets": sheets,
        "reporter": reporter,
        "scorer": scorer,
        "bot": bot,
        "ALL_MEMBERS": ALL_MEMBERS,
        "CHECKPOINT_CHANNEL": CHECKPOINT_CHANNEL,
        "event_bus": event_bus,
        "plugin_loader": plugin_loader,
    }

    core_api = CoreAPI(core_modules)
    plugin_loader.set_core_api(core_api)

    # Auto-load plugins
    for plugin in plugin_loader.discover_plugins():
        success, msg = plugin_loader.load_plugin(plugin.id)
        if success:
            print(f"[Plugin] {msg}")
        else:
            print(f"[Plugin] ❌ {msg}")

    # Setup plugin commands
    setup_plugin_commands(bot, plugin_loader, is_admin)
    setup_hub_commands(bot, plugin_hub, is_admin)
    print("[Bot] Plugin Hub commands loaded")
    # 🧠 Start ML Mini FIRST (không bị rate limit)
    try:
        ml_manager = get_ml_manager()
        await ml_manager.start()
        
        # Setup ML commands
        setup_ml_commands(bot, is_admin)
        print("[Bot] ✅ ML Mini started + commands loaded")
    except Exception as e:
        print(f"[Bot] ⚠️ ML Mini error: {e}")
        import traceback
        traceback.print_exc()
    
    # ⏭️ Setup Slash Commands (có thể bị rate limit)
    # COMMENT OUT slash sync để tránh block
    try:
        slash_modules = {
            # Modules
            "access_control": access_control,
            "time_tracker": time_tracker,
            "collector": collector,
            "sheets": sheets,
            "reporter": reporter,
            "socratic_tutor": socratic_tutor,
            "practice_quiz": practice_quiz,
            "progress_predictor": progress_predictor,
            "chat_bot": chat_bot,
            "weekly_planner": weekly_planner,
            "advanced_mode": advanced_mode,
            "error_tracker": error_tracker,
            "solution_proposer": solution_proposer,
            "exercise_generator": exercise_generator,
            "spaced_repetition": spaced_repetition,
            "scorer": scorer,
            # Functions
            "get_current_week": get_current_week,
            "is_admin": is_admin,
            "run_ai_scoring": run_ai_scoring,
            "generate_final_report": generate_final_report,
            "save_score": save_score,
            "get_week_scores": get_week_scores,
            "get_pending_score": get_pending_score,
            "update_score_source": update_score_source,
            "get_week_participation": get_week_participation,
            "get_score_history": get_score_history,
            # Constants
            "CHECKPOINT_CHANNEL": CHECKPOINT_CHANNEL,
        }
        
        # Chỉ setup tree, KHÔNG sync (tránh 429)
        setup_slash_commands(bot, slash_modules)
        print(f"[Bot] ✅ Slash commands setup: {len(bot.tree.get_commands())} commands in tree")
        print("[Bot] ℹ️ Dùng !sync_commands để sync slash khi cần")
    except Exception as e:
        print(f"[Bot] Slash setup error: {e}")


@bot.event
async def on_command_error(ctx, error):
    cmd_name = ctx.command.name if ctx.command else "?"
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Thieu tham so `{error.param.name}`. Go `!help {cmd_name}`.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"Tham so khong hop le. Go `!help {cmd_name}`.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"Loi: {error}")
        print(f"[Error] {cmd_name}: {error}")


# ============ TASKS ============

@tasks.loop(time=time(hour=TASK_HOUR, minute=TASK_MINUTE, tzinfo=TZ))
async def ai_scoring_task():
    now = datetime.now(TZ)
    if now.weekday() != AI_SCORING_DAY:
        return
    week = get_current_week()
    if time_tracker.is_break_week(week):
        print(f"[Scoring] Week {week} is BREAK WEEK - skip scoring")
        return
    await run_ai_scoring(week)


@ai_scoring_task.error
async def ai_scoring_task_error(exc):
    print(f"[ai_scoring_task] crashed: {exc!r}")


@tasks.loop(time=time(hour=TASK_HOUR, minute=TASK_MINUTE, tzinfo=TZ))
async def report_task():
    now = datetime.now(TZ)
    if now.weekday() != REPORT_DAY:
        return
    week = get_current_week()
    report_channel = bot.get_channel(REPORT_CHANNEL)
    if report_channel is None:
        print(f"[Report] REPORT_CHANNEL {REPORT_CHANNEL} not found")
        return
    await generate_final_report(week, report_channel)


@report_task.error
async def report_task_error(exc):
    print(f"[report_task] crashed: {exc!r}")
# ============ ML AUTO TASKS ============

@tasks.loop(minutes=5)
async def ml_refresh_task():
    """Auto check ML cache + anomaly mỗi 5 phút"""
    try:
        ml = get_ml_manager()

        # Refresh token optimizer ML cache
        try:
            from token_optimizer import _token_optimizer
            if _token_optimizer:
                await _token_optimizer.refresh_ml_cache()
        except Exception:
            pass

        # Check anomalies toàn cohort
        result = await ml.detect_anomalies()

        if result.get("anomalies_found", 0) > 0:
            admin_channel = bot.get_channel(ADMIN_REVIEW_CHANNEL)
            if not admin_channel:
                return

            # Chỉ gửi HIGH severity
            high_anomalies = []
            for r in result.get("results", []):
                if not r.get("is_anomaly"):
                    continue
                has_high = any(a.get("severity") == "high" for a in r.get("anomalies", []))
                if has_high:
                    high_anomalies.append(r)

            if high_anomalies:
                msg = "# 🚨 ML ANOMALY ALERT\n\n"
                for r in high_anomalies[:5]:
                    msg += f"**{r['member']}** – Điểm: {r.get('latest_score')}/5\n"
                    for a in r.get("anomalies", [])[:2]:
                        if a.get("severity") == "high":
                            msg += f"  🔴 {a.get('message', '')[:80]}\n"
                    msg += "\n"

                await admin_channel.send(msg)

    except Exception as e:
        print(f"[ML Refresh] Error: {e}")


@ml_refresh_task.error
async def ml_refresh_task_error(exc):
    print(f"[ml_refresh_task] crashed: {exc!r}")

# ============ CORE LOGIC ============

async def run_ai_scoring(week):
    cp_channel = bot.get_channel(CHECKPOINT_CHANNEL)
    admin_channel = bot.get_channel(ADMIN_REVIEW_CHANNEL)

    if cp_channel is None:
        print(f"[Scoring] CHECKPOINT_CHANNEL {CHECKPOINT_CHANNEL} not found")
        return
    if admin_channel is None:
        print(f"[Scoring] ADMIN_REVIEW_CHANNEL {ADMIN_REVIEW_CHANNEL} not found")
        return

    submissions, missing = await collector.collect_week(cp_channel, week)

    if not submissions:
        await admin_channel.send(f"Tuan {week}: Khong co bai nop.")
        return

    for m in ALL_MEMBERS:
        save_participation(week, m, m not in missing)

    pending = []
    for sub in submissions:
        existing = get_pending_score(week, sub["member"])
        if existing and existing["source"] in ("confirmed", "human_override"):
            print(f"[Bot] SKIP {sub['member']} (da confirmed/override)")
            continue

        member = sub["member"]
        topic = sub.get("topic", "unknown")
        print(f"[Bot] Processing: {member} ({topic})")

        result = await asyncio.to_thread(
            ai_scorer.score_submission, member, week, sub["content"]
        )
        save_score(
            week, member,
            {k: result[k] for k in ["accuracy", "depth", "connection", "presentation"]},
            self_score=sub.get("self_score"),
            source="ai_suggested",
        )

        total = scorer.calculate_total(result)
        print(f"[Bot] Scored {member}: {total}/5")

        errors = result.get("errors", [])
        if errors:
            error_tracker.save_errors(week, member, topic, errors)
            print(f"[Bot] Saved {len(errors)} errors for {member}")

        error_patterns = error_tracker.get_error_patterns(member)

        recommendation = await asyncio.to_thread(
            resource_recommender.recommend, member, topic, errors, error_patterns
        )

        auto_solutions = None
        auto_exercises = None
        if errors:
            try:
                scores_dict = {k: result[k] for k in
                               ["accuracy", "depth", "connection", "presentation"]}
                auto_solutions = await asyncio.to_thread(
                    solution_proposer.propose,
                    member, topic, sub["content"], scores_dict
                )
                auto_exercises = await asyncio.to_thread(
                    exercise_generator.generate, member, topic, scores_dict
                )
            except Exception as e:
                print(f"[Bot] Auto solutions/exercises error: {e}")

        if sheets is not None:
            try:
                extracted = await asyncio.to_thread(
                    distiller.extract, member, topic, sub["content"]
                )
                await asyncio.to_thread(
                    sheets.sync_insights, week, member, topic, extracted, total
                )
                await asyncio.to_thread(
                    sheets.sync_code_vault, week, member, topic, extracted, total
                )
            except Exception as e:
                print(f"[Distiller] Error for {member}: {e}")

        try:
            spaced_repetition.schedule_review(week, member, topic)
            print(f"[SpacedRep] Scheduled review for {member}")
        except Exception as e:
            print(f"[SpacedRep] Error: {e}")

        # ✅ ML ANALYSIS
        ml_prediction = None
        ml_anomaly = None

        try:
            ml = get_ml_manager()

            # Dự đoán tuần tới
            ml_prediction = await ml.predict_score(member, weeks_ahead=1)

            # Check anomaly
            ml_anomaly = await ml.detect_anomalies(member)

            print(f"[Bot] ✅ ML analyzed {member}")
        except Exception as e:
            print(f"[Bot] ⚠️ ML error for {member}: {e}")

        pending.append({
            "member": member,
            "result": result,
            "errors": errors,
            "error_patterns": error_patterns,
            "recommendation": recommendation,
            "auto_solutions": auto_solutions,
            "auto_exercises": auto_exercises,
            "topic": topic,
            # ✅ ML data
            "ml_prediction": ml_prediction,
            "ml_anomaly": ml_anomaly,
        })

    if not pending:
        await admin_channel.send(f"Tuan {week}: Tat ca da co diem.")
        return

    info = time_tracker.get_current_info()

    header_embed = discord.Embed(
        title=f"📊 AI ĐỀ XUẤT ĐIỂM – TUẦN {week}",
        description=f"**Mode:** {info['mode']} | **Số bài:** {len(pending)}",
        color=discord.Color.blue(),
    )
    await admin_channel.send(embed=header_embed)

    for p in pending:
        member = p["member"]
        r = p["result"]
        total = scorer.calculate_total(r)

        if total >= 4.5:
            color = discord.Color.green()
            icon = "🟢"
        elif total >= 3.5:
            color = discord.Color.gold()
            icon = "🟡"
        else:
            color = discord.Color.red()
            icon = "🔴"

        embed = discord.Embed(
            title=f"{icon} {member} – {total}/5",
            color=color,
        )

        embed.add_field(
            name="📈 Điểm chi tiết",
            value=(
                f"```\n"
                f"Chính xác:  {r['accuracy']}/5\n"
                f"Độ sâu:     {r['depth']}/5\n"
                f"Kết nối:    {r['connection']}/5\n"
                f"Trình bày:  {r['presentation']}/5\n"
                f"```"
            ),
            inline=False,
        )

        if r.get("reason"):
            embed.add_field(
                name="📝 Lý do",
                value=f"_{r['reason'][:500]}_",
                inline=False,
            )

        if r.get("strengths"):
            strengths = "\n".join(f"• {s}" for s in r["strengths"][:3])
            embed.add_field(name="💪 Điểm mạnh", value=strengths[:500], inline=False)

        if r.get("weaknesses"):
            weaknesses = "\n".join(f"• {w}" for w in r["weaknesses"][:3])
            embed.add_field(name="⚠️ Điểm yếu", value=weaknesses[:500], inline=False)

        if p["errors"]:
            errors_text = ""
            for err in p["errors"][:3]:
                sev_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                    err.get("severity", "medium"), "⚪"
                )
                errors_text += f"{sev_icon} **{err.get('type', '?')}**: {err.get('detail', '')[:80]}\n"
            if p["error_patterns"].get("has_repeated"):
                errors_text += f"\n🚨 **Lỗi lặp lại!**"
            embed.add_field(
                name=f"🐛 Lỗi phát hiện ({len(p['errors'])})",
                value=errors_text[:1000],
                inline=False,
            )
        if p["recommendation"] and p["recommendation"].get("resources"):
            resources_text = ""
            for res in p["recommendation"]["resources"][:2]:
                resources_text += f"• [{res['title'][:60]}]({res['url']})\n"
            embed.add_field(name="📚 Tài liệu bổ trợ", value=resources_text[:500], inline=False)
        # ✅ ML ANOMALY ALERT
        if p.get("ml_anomaly") and p["ml_anomaly"].get("is_anomaly"):
            anomalies = p["ml_anomaly"].get("anomalies", [])
            if anomalies:
                anom_text = ""
                for a in anomalies[:2]:
                    icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(a.get("severity", "medium"), "⚪")
                    anom_text += f"{icon} **{a.get('type', '?')}**: {a.get('message', '')[:80]}\n"

                embed.add_field(
                    name=f"🚨 ML ALERT ({len(anomalies)})",
                    value=anom_text[:500],
                    inline=False,
                )

        # ✅ ML PREDICTION
        if p.get("ml_prediction") and p["ml_prediction"].get("predictions"):
            pred = p["ml_prediction"]["predictions"][0]
            trend_icon = {
                "improving": "📈",
                "declining": "📉",
                "stable": "➡️",
                "unknown (insufficient data)": "❓",
            }.get(p["ml_prediction"].get("trend", ""), "🔮")

            embed.add_field(
                name=f"{trend_icon} ML PREDICTION",
                value=(
                    f"**Tuần tới:** {pred['predicted_score']}/5\n"
                    f"**Model:** `{p['ml_prediction'].get('model', '?')}`\n"
                    f"**Trend:** {p['ml_prediction'].get('trend', '?')}"
                ),
                inline=False,
            )

        embed.add_field(
            name="🔗 Xem chi tiết",
            value=(
                f"`!solutions {member} {week}` – Giải pháp\n"
                f"`!exercises {member} {week}` – Bài tập\n"
                f"`!errors {member}` – Lịch sử lỗi"
            ),
            inline=False,
        )

        embed.set_footer(text=f"Deadline confirm: Thứ 7, 23:59")
        await admin_channel.send(embed=embed)

    if missing:
        mentions = " ".join(f"@{m}" for m in missing)
        missing_embed = discord.Embed(
            title="⚠️ CHƯA NỘP BÀI",
            description=mentions,
            color=discord.Color.orange(),
        )
        await admin_channel.send(embed=missing_embed)

    if sheets is not None:
        try:
            week_scores = get_week_scores(week)
            await asyncio.to_thread(sheets.sync_scores, week_scores)
            participation = get_week_participation(week)
            await asyncio.to_thread(sheets.sync_participation, week, participation)
        except Exception as e:
            print(f"[Sheets] Sync error: {e}")


# ============ COMMANDS ============

@bot.command(name="confirm")
async def confirm_cmd(ctx, member: str):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    week = get_current_week()
    member_clean = member.split("-NR.")[0].strip()
    if not member_clean:
        member_clean = member

    pending = get_pending_score(week, member_clean)
    if not pending:
        pending = get_pending_score(week, member)

    if not pending:
        await ctx.send(
            f"Khong co diem AI nao dang cho cho **{member}** tuan {week}.\n"
            f"(Da thu ca '{member_clean}' va '{member}')"
        )
        return

    update_score_source(week, pending["member"], "confirmed", changed_by=str(ctx.author.id))

    if sheets is not None:
        try:
            week_scores = get_week_scores(week)
            await asyncio.to_thread(sheets.sync_scores, week_scores)
        except Exception as e:
            print(f"[Sheets] Sync error after confirm: {e}")

    await ctx.send(
        f"Da xac nhan diem cho **{pending['member']}** tuan {week} "
        f"(Tong: {pending['total']}/5)"
    )


@bot.command(name="override")
async def override_cmd(ctx, member: str, accuracy: float, depth: float,
                        connection: float, presentation: float):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    week = get_current_week()
    member_clean = member.split("-NR.")[0].strip()
    if not member_clean:
        member_clean = member

    scores = {"accuracy": accuracy, "depth": depth, "connection": connection, "presentation": presentation}
    save_score(week, member_clean, scores, source="human_override",
               changed_by=str(ctx.author.id),
               note=f"Override boi {ctx.author.display_name}")
    total = scorer.calculate_total(scores)

    if sheets is not None:
        try:
            week_scores = get_week_scores(week)
            await asyncio.to_thread(sheets.sync_scores, week_scores)
        except Exception as e:
            print(f"[Sheets] Sync error after override: {e}")

    await ctx.send(f"Da sua diem **{member_clean}** tuan {week}: {total}/5")


@bot.command(name="trigger_scoring")
async def trigger_scoring_cmd(ctx, week: int = None):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    if week is None:
        week = get_current_week()

    if time_tracker.is_break_week(week):
        await ctx.send(f"Tuan {week} la BREAK WEEK - khong cham diem.")
        return

    info = time_tracker.get_current_info()
    await ctx.send(f"Dang chay AI scoring cho tuan {week} ({info['mode']})...")

    try:
        await asyncio.wait_for(run_ai_scoring(week), timeout=600)
        await ctx.send(f"Da cham AI xong tuan {week}.")
    except asyncio.TimeoutError:
        await ctx.send(f"⏱️ Timeout sau 10 phút.")
        print(f"[trigger_scoring] TIMEOUT 10 minutes")
    except Exception as e:
        await ctx.send(f"Loi: {e}")
        print(f"[trigger_scoring] {e}")


@bot.command(name="trigger_report")
async def trigger_report_cmd(ctx, week: int = None):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    if week is None:
        week = get_current_week()

    await ctx.send(f"Dang tao report tuan {week}...")
    try:
        await generate_final_report(week, ctx.channel)
    except Exception as e:
        await ctx.send(f"Loi: {e}")
        print(f"[trigger_report] {e}")


@bot.command(name="missing")
async def missing_cmd(ctx):
    week = get_current_week()
    cp_channel = bot.get_channel(CHECKPOINT_CHANNEL)
    if cp_channel is None:
        await ctx.send("❌ CHECKPOINT_CHANNEL chưa được cấu hình.")
        return

    _, missing = await collector.collect_week(cp_channel, week)

    if not missing:
        await ctx.send(f"Tuan {week}: Tat ca da nop bai!")
    else:
        mentions = " ".join(f"@{m}" for m in missing)
        await ctx.send(f"Tuan {week}: Chua nop: {mentions}")


@bot.command(name="week")
async def week_cmd(ctx):
    week = get_current_week()
    info = time_tracker.get_current_info()

    msg = f"# 📅 TUẦN {week}\n\n"
    msg += f"**Mode:** {info['mode']}\n"
    msg += f"**Thời gian:** {info['start_date']} → {info['end_date']}\n"

    if info['is_break']:
        msg += f"**Trạng thái:** 🏖️ BREAK WEEK\n"
    else:
        msg += f"**Còn lại:** {info['days_remaining']} ngày\n"

    if time_tracker.is_override_active():
        msg += f"\n⚠️ **Override active**\n"

    await ctx.send(msg)


@bot.command(name="mode")
async def mode_cmd(ctx):
    info = time_tracker.get_current_info()

    msg = f"# 📅 TUẦN {info['week']}\n\n"
    msg += f"**Mode:** {info['mode']}\n"
    msg += f"**Thời gian:** {info['start_date']} → {info['end_date']}\n"
    msg += f"**Còn lại:** {info['days_remaining']} ngày\n\n"

    if info['is_break']:
        msg += "🏖️ **BREAK WEEK** – Nghỉ ngơi, không nộp bài!\n"
    else:
        msg += "**Sản phẩm:** "
        if info['mode'] == "Academic":
            msg += "1 checkpoint"
        elif info['mode'] == "Research Literacy":
            msg += "1 Research Note"
        elif info['mode'] == "Project":
            msg += "Code + Report + Demo"
        else:
            msg += "?"

    await ctx.send(msg)


@bot.command(name="verify_time")
async def verify_time_cmd(ctx):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    cp_channel = bot.get_channel(CHECKPOINT_CHANNEL)
    if cp_channel is None:
        await ctx.send("❌ CHECKPOINT_CHANNEL chưa được cấu hình.")
        return

    week = get_current_week()
    scores = get_week_scores(week)

    submissions, _ = await collector.collect_week(cp_channel, week)

    result = time_tracker.verify(submissions, scores)

    msg = "# 🔍 ĐỐI CHIẾU TIME\n\n"
    msg += f"**Time gốc:** Tuần {result['ground_truth_week']} ({result['ground_truth_mode']})\n"
    msg += f"**AI đo lường:** Tuần {result['ai_measured_week']} (confidence: {result['ai_confidence']})\n\n"
    msg += f"**Kết quả:** {result['alert']}\n"

    if result['evidence']:
        msg += f"\n**Evidence:**\n"
        msg += f"- Tổng timestamps: {result['evidence'].get('total_timestamps', 0)}\n"
        msg += f"- Phân bố tuần: {result['evidence'].get('week_distribution', {})}\n"

    await ctx.send(msg)


@bot.command(name="set_week")
async def set_week_cmd(ctx, week: int = None):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    if week is None:
        await ctx.send("Cu phap: `!set_week <so>`")
        return

    if week < 1 or week > 72:
        await ctx.send("Tuan phai trong khoang 1-72.")
        return

    time_tracker.set_override_week(week)
    info = time_tracker.get_current_info()

    await ctx.send(
        f"✅ Da set tuan = **{week}**\n"
        f"Mode: {info['mode']}\n"
        f"Thoi gian: {info['start_date']} → {info['end_date']}"
    )


@bot.command(name="clear_override")
async def clear_override_cmd(ctx):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    time_tracker.clear_override_week()
    week = get_current_week()
    await ctx.send(f"✅ Da xoa override. Tuan hien tai: **{week}**")


@bot.command(name="time_debug")
async def time_debug_cmd(ctx):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    debug = time_tracker.debug_info()

    msg = "# 🔧 TIME DEBUG\n\n"
    msg += f"**Roadmap start:** {debug['roadmap_start_date']}\n"
    msg += f"**Week duration:** {debug['week_duration_days']} ngày\n"
    msg += f"**Break weeks:** {debug['break_weeks']}\n"
    msg += f"**Override week:** {debug['override_week']}\n"
    msg += f"**Override active:** {debug['override_active']}\n\n"

    info = debug['current_info']
    msg += f"**Current week:** {info['week']}\n"
    msg += f"**Mode:** {info['mode']}\n"
    msg += f"**Is break:** {info['is_break']}\n"
    msg += f"**Start:** {info['start_date']}\n"
    msg += f"**End:** {info['end_date']}\n"
    msg += f"**Days remaining:** {info['days_remaining']}\n"

    for part in reporter._split(msg):
        await ctx.send(part)


@bot.command(name="history")
async def history_cmd(ctx, week: int, member: str = None):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    if member:
        member_clean = member.split("-NR.")[0].strip()
        if member_clean:
            member = member_clean

    history = get_score_history(week, member)
    if not history:
        await ctx.send(f"Khong co lich su cho tuan {week}.")
        return

    msg = f"# LICH SU DIEM - TUAN {week}\n\n"
    for h in history[:20]:
        msg += f"**{h['member']}** | {h['total']}/5 | `{h['source']}` | {h['changed_at']}\n"
        if h.get("note"):
            msg += f"  _{h['note']}_\n"
        msg += "\n"

    for part in reporter._split(msg):
        await ctx.send(part)


@bot.command(name="insights")
async def insights_cmd(ctx, topic: str = None):
    if sheets is None:
        await ctx.send("Google Sheets chua ket noi. Khong the xem insights.")
        return

    insights = await asyncio.to_thread(sheets.load_insights, topic)

    if not insights:
        await ctx.send(f"Khong tim thay insights cho topic '{topic or 'ALL'}'")
        return

    msg = f"# 🧠 INSIGHTS – {topic or 'TAT CA'}\n\n"
    for i in insights[:10]:
        msg += f"**{i.get('Member', '')}** (Tuan {i.get('Tuan', '')}) – *{i.get('Topic', '')}*\n"
        msg += f"💡 {i.get('Insight chinh', '')}\n"
        msg += f"🔭 Goc nhin: {i.get('Goc nhin doc dao', '')}\n"
        msg += f"⚡ Ung dung: {i.get('Ung dung thuc te', '')}\n\n"

    for part in reporter._split(msg):
        await ctx.send(part)


@bot.command(name="codevault")
async def codevault_cmd(ctx, topic: str = None):
    if sheets is None:
        await ctx.send("Google Sheets chua ket noi. Khong the xem code vault.")
        return

    codes = await asyncio.to_thread(sheets.load_code_vault, topic)

    if not codes:
        await ctx.send(f"Khong tim thay code cho topic '{topic or 'ALL'}'")
        return

    msg = f"# 💻 CODE VAULT – {topic or 'TAT CA'}\n\n"
    for c in codes[:10]:
        msg += f"**{c.get('Member', '')}** (Tuan {c.get('Tuan', '')}) – *{c.get('Topic', '')}*\n"
        msg += f"```{c.get('Ngon ngu', '')}\n{c.get('Code snippet', '')}\n```\n\n"

    for part in reporter._split(msg):
        await ctx.send(part)


@bot.command(name="ping")
async def ping_cmd(ctx):
    """Kiểm tra AI provider"""
    from ai_provider import call_ai_json
    try:
        result = await asyncio.to_thread(
            call_ai_json, 'Tra ve JSON: {"ok": 1}', 100, 1, "ping"
        )

        # ✅ Thành công
        embed = discord.Embed(
            title="✅ AI PROVIDER OK",
            description=f"Response: `{str(result)[:80]}`",
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)

    except Exception as e:
        err = str(e)

        # Phân loại lỗi
        if "503" in err or "UNAVAILABLE" in err:
            title = "⏳ GEMINI QUÁ TẢI"
            desc = (
                "**Nguyên nhân:** Google server quá tải (giờ cao điểm)\n\n"
                "**Giải pháp:**\n"
                "• Thử lại sau **5-10 phút**\n"
                "• Hoặc đợi sáng mai (server rảnh)"
            )
            color = discord.Color.gold()

        elif "429" in err or "QUOTA" in err:
            title = "🚫 HẾT QUOTA"
            desc = (
                "**Nguyên nhân:** Đã dùng hết 250 requests/ngày\n\n"
                "**Giải pháp:**\n"
                "• Đợi **24h** để quota reset\n"
                "• Hoặc fix DeepSeek key để có backup"
            )
            color = discord.Color.red()

        elif "401" in err or "Authentication" in err or "invalid" in err:
            title = "🔑 API KEY SAI"
            desc = (
                "**Nguyên nhân:** DeepSeek key không hợp lệ\n\n"
                "**Giải pháp:**\n"
                "• Kiểm tra `DEEPSEEK_API_KEY` trong `.env`\n"
                "• Hoặc tạo key mới tại platform.deepseek.com"
            )
            color = discord.Color.red()

        elif "timeout" in err.lower():
            title = "⏱️ TIMEOUT"
            desc = (
                "**Nguyên nhân:** AI provider bị treo\n\n"
                "**Giải pháp:** Thử lại sau 1-2 phút"
            )
            color = discord.Color.orange()

        else:
            title = "❌ AI PROVIDER LỖI"
            desc = f"```\n{err[:300]}\n```"
            color = discord.Color.red()

        embed = discord.Embed(
            title=title,
            description=desc,
            color=color,
        )
        embed.set_footer(text="Gõ !ping để kiểm tra lại")
        await ctx.send(embed=embed)


@bot.command(name="check_channels")
async def check_channels_cmd(ctx):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    from config import CHECKPOINT_CHANNEL, ADMIN_REVIEW_CHANNEL, REPORT_CHANNEL

    msg = "# 🔍 CHANNEL CHECK\n\n"
    msg += f"**Config values:**\n"
    msg += f"- CHECKPOINT_CHANNEL: `{CHECKPOINT_CHANNEL}`\n"
    msg += f"- ADMIN_REVIEW_CHANNEL: `{ADMIN_REVIEW_CHANNEL}`\n"
    msg += f"- REPORT_CHANNEL: `{REPORT_CHANNEL}`\n\n"

    msg += f"**Bot lookup:**\n"
    cp = bot.get_channel(CHECKPOINT_CHANNEL)
    ar = bot.get_channel(ADMIN_REVIEW_CHANNEL)
    rp = bot.get_channel(REPORT_CHANNEL)

    msg += f"- checkpoint: {'✅ ' + cp.name if cp else '❌ None'}\n"
    msg += f"- admin_review: {'✅ ' + ar.name if ar else '❌ None'}\n"
    msg += f"- report: {'✅ ' + rp.name if rp else '❌ None'}\n"

    await ctx.send(msg)


@bot.command(name="whereami")
async def whereami_cmd(ctx):
    msg = "# 📍 CHANNEL INFO\n\n"
    msg += f"**Channel name:** #{ctx.channel.name}\n"
    msg += f"**Channel ID:** `{ctx.channel.id}`\n"
    msg += f"**Server:** {ctx.guild.name}\n"
    msg += f"**Server ID:** `{ctx.guild.id}`\n"
    msg += f"**Channel type:** {ctx.channel.type}\n"
    await ctx.send(msg)


# ============ LEARNING ENHANCEMENT ============

@bot.command(name="solutions")
async def solutions_cmd(ctx, member: str, week: int = None):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    if week is None:
        week = get_current_week()

    member_clean = member.split("-NR.")[0].strip()
    cp_channel = bot.get_channel(CHECKPOINT_CHANNEL)
    if cp_channel is None:
        await ctx.send("❌ CHECKPOINT_CHANNEL chưa được cấu hình.")
        return

    submissions, _ = await collector.collect_week(cp_channel, week)
    sub = next((s for s in submissions if s["member"] == member_clean), None)

    if not sub:
        await ctx.send(f"Khong tim thay bai nop cua {member_clean} tuan {week}")
        return

    scores = get_pending_score(week, member_clean)
    if not scores:
        await ctx.send(f"Chua co diem cho {member_clean} tuan {week}")
        return

    scores_dict = {k: scores.get(k, 0) for k in ["accuracy", "depth", "connection", "presentation"]}

    await ctx.send(f"Dang phan tich cach tiep can khac cho {member_clean}...")

    result = await asyncio.to_thread(
        solution_proposer.propose,
        member_clean, sub.get("topic", ""), sub["content"], scores_dict
    )

    msg = f"# 💡 ĐỀ XUẤT GIẢI PHÁP MỚI – {member_clean}\n\n"
    msg += f"**Cách hiện tại:** {result.get('current_approach', 'N/A')}\n\n"

    for i, sol in enumerate(result.get("alternative_solutions", []), 1):
        msg += f"## {i}. {sol.get('name', '?')} `[{sol.get('difficulty', '?')}]`\n"
        msg += f"{sol.get('description', '')}\n\n"
        msg += f"**Ưu điểm:**\n"
        for p in sol.get("pros", []):
            msg += f"- ✅ {p}\n"
        msg += f"\n**Nhược điểm:**\n"
        for c in sol.get("cons", []):
            msg += f"- ⚠️ {c}\n"
        msg += f"\n**Khi nào dùng:** {sol.get('when_to_use', '')}\n\n"

    if result.get("recommended"):
        msg += f"---\n🎯 **Khuyên dùng:** {result['recommended']}\n"

    for part in reporter._split(msg):
        await ctx.send(part)


@bot.command(name="exercises")
async def exercises_cmd(ctx, member: str, week: int = None):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    if week is None:
        week = get_current_week()

    member_clean = member.split("-NR.")[0].strip()
    scores = get_pending_score(week, member_clean)
    if not scores:
        await ctx.send(f"Chua co diem cho {member_clean} tuan {week}")
        return

    scores_dict = {k: scores.get(k, 0) for k in ["accuracy", "depth", "connection", "presentation"]}

    cp_channel = bot.get_channel(CHECKPOINT_CHANNEL)
    if cp_channel is None:
        await ctx.send("❌ CHECKPOINT_CHANNEL chưa được cấu hình.")
        return

    submissions, _ = await collector.collect_week(cp_channel, week)
    sub = next((s for s in submissions if s["member"] == member_clean), None)
    topic = sub.get("topic", "unknown") if sub else "unknown"

    await ctx.send(f"Dang sinh bai tap cho {member_clean}...")

    result = await asyncio.to_thread(
        exercise_generator.generate, member_clean, topic, scores_dict
    )

    msg = f"# 📝 BÀI TẬP CÁ NHÂN HÓA – {member_clean}\n\n"
    msg += f"**Focus:** {result.get('focus', 'N/A')}\n\n"

    for ex in result.get("exercises", []):
        msg += f"## Bài {ex.get('id', '?')} `[{ex.get('difficulty', '?')}]`\n"
        msg += f"**Đề:** {ex.get('question', '')}\n\n"
        msg += f"**Gợi ý:** ||{ex.get('hint', '')}||\n"
        msg += f"**Đáp án:** ||{ex.get('answer', '')}||\n"
        msg += f"**Thời gian:** {ex.get('time_estimate', '?')}\n\n"

    if result.get("resources"):
        msg += f"---\n📚 **Tài liệu:**\n"
        for r in result["resources"]:
            msg += f"- {r}\n"

    for part in reporter._split(msg):
        await ctx.send(part)


@bot.command(name="review_due")
async def review_due_cmd(ctx, member: str = None):
    if member:
        member = member.split("-NR.")[0].strip()

    due = spaced_repetition.get_due_reviews(member)

    if not due:
        await ctx.send("Khong co topic nao can on hom nay! 🎉")
        return

    msg = f"# 🔄 ÔN TẬP HÔM NAY\n\n"
    if member:
        msg += f"**Member:** {member}\n\n"

    for d in due:
        overdue = f" (quá {d['days_overdue']} ngày)" if d['days_overdue'] > 0 else ""
        msg += f"**{d['member']}** – Tuần {d['week']} – *{d['topic']}*\n"
        msg += f"  Stage: {d['stage']}/6{overdue}\n\n"

    await ctx.send(msg)


@bot.command(name="review_done")
async def review_done_cmd(ctx, member: str, week: int, topic: str):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    member_clean = member.split("-NR.")[0].strip()
    result = spaced_repetition.complete_review(week, member_clean, topic)

    if not result:
        await ctx.send(f"Khong tim thay lich on cho {member_clean} - tuan {week} - {topic}")
        return

    if result["status"] == "completed":
        await ctx.send(f"🎉 **{member_clean}** đã hoàn thành tất cả giai đoạn ôn tập cho **{topic}**!")
    else:
        await ctx.send(
            f"✅ Đã đánh dấu ôn tập **{topic}** (Stage {result['stage']}/6)\n"
            f"📅 Ôn tiếp sau **{result['interval_days']} ngày** ({result['next_review']})"
        )


@bot.command(name="review_schedule")
async def review_schedule_cmd(ctx, member: str = None):
    if member:
        member = member.split("-NR.")[0].strip()
        schedule = spaced_repetition.get_member_schedule(member)

        if not schedule:
            await ctx.send(f"Khong co lich on cho {member}")
            return

        msg = f"# 📅 LỊCH ÔN TẬP – {member}\n\n"
        for s in schedule:
            icon = "✅" if s["status"] == "completed" else "⏳"
            msg += f"{icon} **Tuần {s['week']}** – *{s['topic']}*\n"
            msg += f"   Stage: {s['stage']}/6 | Next: {s['next_review']}\n\n"
    else:
        stats = spaced_repetition.get_stats()
        msg = f"# 📊 THỐNG KÊ ÔN TẬP\n\n"
        msg += f"- Tổng: **{stats['total']}**\n"
        msg += f"- Chờ ôn: **{stats['pending']}**\n"
        msg += f"- Hoàn thành: **{stats['completed']}**\n"
        msg += f"- Cần ôn hôm nay: **{stats['due_now']}**\n"

    await ctx.send(msg)


@bot.command(name="learning_report")
async def learning_report_cmd(ctx, member: str, week: int = None):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    if week is None:
        week = get_current_week()

    member_clean = member.split("-NR.")[0].strip()
    scores = get_pending_score(week, member_clean)

    if not scores:
        await ctx.send(f"Chua co diem cho {member_clean} tuan {week}")
        return

    scores_dict = {k: scores.get(k, 0) for k in ["accuracy", "depth", "connection", "presentation"]}

    cp_channel = bot.get_channel(CHECKPOINT_CHANNEL)
    if cp_channel is None:
        await ctx.send("❌ CHECKPOINT_CHANNEL chưa được cấu hình.")
        return

    submissions, _ = await collector.collect_week(cp_channel, week)
    sub = next((s for s in submissions if s["member"] == member_clean), None)
    topic = sub.get("topic", "unknown") if sub else "unknown"

    await ctx.send(f"Đang tạo báo cáo đầy đủ cho {member_clean}...")

    solutions = await asyncio.to_thread(
        solution_proposer.propose,
        member_clean, topic, sub["content"] if sub else "", scores_dict
    )
    exercises = await asyncio.to_thread(
        exercise_generator.generate, member_clean, topic, scores_dict
    )
    schedule = spaced_repetition.schedule_review(week, member_clean, topic)

    msg = f"# 📚 BÁO CÁO HỌC TẬP – {member_clean} – TUẦN {week}\n\n"
    msg += f"**Topic:** {topic}\n"
    msg += f"**Điểm:** {scores_dict}\n\n"

    msg += f"## 💡 Giải pháp thay thế\n"
    for sol in solutions.get("alternative_solutions", [])[:2]:
        msg += f"- **{sol.get('name')}** – {sol.get('description', '')[:80]}...\n"
    msg += "\n"

    msg += f"## 📝 Bài tập\n"
    for ex in exercises.get("exercises", [])[:3]:
        msg += f"- **Bài {ex.get('id')}** `[{ex.get('difficulty')}]` – {ex.get('time_estimate')}\n"
    msg += "\n"

    msg += f"## 🔄 Lịch ôn tập\n"
    msg += f"- Ôn lần 1: **{schedule['next_review']}** (sau 1 ngày)\n"
    msg += f"- Ôn lần 2: +3 ngày\n"
    msg += f"- ... (1-3-7-14-30-60)\n"

    for part in reporter._split(msg):
        await ctx.send(part)


# ============ TOKEN / ROUTING ============

@bot.command(name="tokens")
async def tokens_cmd(ctx):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    from ai_provider import get_token_stats, cache_stats

    stats = get_token_stats()
    cstats = cache_stats()

    msg = f"# 📊 TOKEN USAGE – {stats['date']}\n\n"
    msg += f"## 🎯 Requests\n"
    msg += f"- Đã dùng: **{stats['requests_used']}**\n"
    msg += f"- Còn lại: **{stats['requests_remaining']}**\n"
    msg += f"- Ngân sách: **{stats['budget_pct']}%**\n\n"

    msg += f"## 💾 Tokens\n"
    msg += f"- Đã dùng: **{stats['tokens_used']:,}**\n"
    msg += f"- Còn lại: **{stats['tokens_remaining']:,}**\n\n"

    msg += f"## 🗂️ Cache\n"
    msg += f"- Files: **{cstats['files']}**\n"
    msg += f"- Size: **{cstats['size_mb']} MB**\n\n"

    if stats["requests_by_task"]:
        msg += f"## 📋 Chi tiết theo task\n"
        for task, count in sorted(
            stats["requests_by_task"].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            tokens = stats["tokens_by_task"].get(task, 0)
            msg += f"- **{task}**: {count} requests, {tokens:,} tokens\n"

    await ctx.send(msg)


@bot.command(name="token_reset")
async def token_reset_cmd(ctx):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    from ai_provider import reset_token_budget
    reset_token_budget()
    await ctx.send("✅ Đã reset token budget.")


@bot.command(name="routing")
async def routing_cmd(ctx):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    from ai_provider import get_token_stats, cache_stats

    stats = get_token_stats()
    cstats = cache_stats()

    msg = f"# 🎯 SMART TOKEN ROUTER – {stats['date']}\n\n"

    msg += f"## 📊 Priority Distribution\n"
    pstats = stats.get("priority_stats", {})
    total_priority = sum(pstats.values()) or 1

    priority_icons = {"CRITICAL": "🔴", "HIGH": "🟠", "NORMAL": "🟡", "LOW": "🟢"}

    for priority in ["CRITICAL", "HIGH", "NORMAL", "LOW"]:
        count = pstats.get(priority, 0)
        pct = round(count / total_priority * 100, 1)
        icon = priority_icons.get(priority, "⚪")
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        msg += f"- {icon} **{priority}**: {count} ({pct}%) `{bar}`\n"

    msg += "\n## ⚡ Turbo Modes\n"
    tstats = stats.get("turbo_stats", {})
    total_turbo = sum(tstats.values()) or 1
    turbo_icons = {"eco": "🍃", "normal": "⚙️", "turbo": "🚀", "hyper": "⚡"}

    for mode in ["eco", "normal", "turbo", "hyper"]:
        count = tstats.get(mode, 0)
        pct = round(count / total_turbo * 100, 1)
        icon = turbo_icons.get(mode, "⚪")
        msg += f"- {icon} **{mode}**: {count} ({pct}%)\n"

    msg += "\n## 💰 Token Budget\n"
    msg += f"- Requests: **{stats['requests_used']}** / 250 ({stats['budget_pct']}%)\n"
    msg += f"- Tokens: **{stats['tokens_used']:,}** / 500,000\n"
    msg += f"- Cache: **{cstats['files']}** files ({cstats['size_mb']} MB)\n\n"

    routing_log = stats.get("routing_log", [])
    if routing_log:
        msg += f"## 📋 Routing Log (last {len(routing_log)})\n"
        msg += "```\n"
        msg += f"{'Time':<10} {'Task':<12} {'Priority':<9} {'Base':>5} {'PM':>5} {'TM':>5} {'Final':>6}\n"
        msg += "─" * 60 + "\n"

        for log in routing_log:
            msg += (
                f"{log['time']:<10} {log['task']:<12} {log['priority']:<9} "
                f"{log['base']:>5} {log['priority_mult']:>4.2f}x "
                f"{log['turbo_mult']:>4.2f}x {log['final']:>6}\n"
            )
        msg += "```\n\n*PM = Priority Multiplier | TM = Turbo Multiplier*\n"
    else:
        msg += "*Chua co routing log hom nay.*\n"

    for part in reporter._split(msg):
        await ctx.send(part)


@bot.command(name="routing_reset")
async def routing_reset_cmd(ctx):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    from ai_provider import _token_optimizer

    _token_optimizer.state["routing_log"] = []
    _token_optimizer.state["priority_stats"] = {"CRITICAL": 0, "HIGH": 0, "NORMAL": 0, "LOW": 0}
    _token_optimizer.state["turbo_stats"] = {"eco": 0, "normal": 0, "turbo": 0, "hyper": 0}
    _token_optimizer._save_state()

    await ctx.send("✅ Đã reset routing log + stats.")


@bot.command(name="errors")
async def errors_cmd(ctx, member: str = None):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    if member:
        member_clean = member.split("-NR.")[0].strip()
        errors = error_tracker.get_member_errors(member_clean, weeks=8)
        patterns = error_tracker.get_error_patterns(member_clean)

        msg = f"# 🐛 LỊCH SỬ LỖI – {member_clean}\n\n"

        if not errors:
            msg += "Chưa có lỗi nào được ghi nhận. 🎉\n"
        else:
            msg += f"**Tổng lỗi:** {len(errors)}\n"
            msg += f"**Lỗi lặp lại:** {'CÓ ⚠️' if patterns['has_repeated'] else 'Không ✅'}\n\n"

            if patterns["has_repeated"]:
                msg += f"## 🚨 Lỗi lặp lại\n"
                for p in patterns["patterns"]:
                    msg += f"- **{p['type']}** – {p['count']} lần (tuần: {', '.join(map(str, p['weeks']))})\n"
                msg += "\n"

            msg += f"## 📋 Chi tiết (10 gần nhất)\n"
            for err in errors[:10]:
                sev = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(err["severity"], "⚪")
                msg += f"{sev} **Tuần {err['week']}** – *{err['type']}*\n"
                msg += f"  {err['detail'][:150]}\n\n"
    else:
        stats = error_tracker.get_stats()
        msg = f"# 📊 THỐNG KÊ LỖI\n\n"
        msg += f"- Tổng lỗi: **{stats['total_errors']}**\n"
        msg += f"- Members có lỗi: **{stats['members_tracked']}**\n\n"

        for m in stats["members"]:
            patterns = error_tracker.get_error_patterns(m)
            flag = "⚠️" if patterns["has_repeated"] else "✅"
            msg += f"- {flag} **{m}** – {patterns['total_errors']} lỗi\n"

    for part in reporter._split(msg):
        await ctx.send(part)


@bot.command(name="error_reset")
async def error_reset_cmd(ctx, member: str = None):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    if member:
        member_clean = member.split("-NR.")[0].strip()
        error_tracker.reset(member_clean)
        await ctx.send(f"✅ Đã reset lỗi của **{member_clean}**.")
    else:
        error_tracker.reset()
        await ctx.send("✅ Đã reset tất cả lỗi.")


@bot.command(name="reset_source")
async def reset_source_cmd(ctx, week: int, member: str):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    import sqlite3
    member_clean = member.split("-NR.")[0].strip()

    conn = sqlite3.connect("scores.db")
    before = conn.execute(
        "SELECT source FROM scores WHERE week = ? AND member = ?",
        (week, member_clean)
    ).fetchone()

    if not before:
        conn.close()
        await ctx.send(f"Khong tim thay score cua {member_clean} tuan {week}")
        return

    conn.execute(
        "UPDATE scores SET source = 'ai_suggested' WHERE week = ? AND member = ?",
        (week, member_clean)
    )
    conn.commit()
    conn.close()

    await ctx.send(
        f"✅ Đã reset **{member_clean}** tuan {week}\n"
        f"`{before[0]}` → `ai_suggested`\n"
        f"Chạy `!trigger_scoring {week}` để chấm lại."
    )


# ============ ACCESS CONTROL ============

@bot.command(name="my_role")
async def my_role_cmd(ctx):
    role = access_control.get_role(ctx.author)
    icon = access_control.get_role_icon(role)
    role_name = access_control.get_role_name(role)
    perms = access_control.get_permissions_list(ctx.author)

    msg = f"# {icon} YOUR ROLE\n\n"
    msg += f"**Role:** {role_name}\n"
    msg += f"**Member:** {ctx.author.display_name}\n\n"

    msg += f"## 📋 Permissions\n"
    if "*" in perms["permissions"]:
        msg += "**ALL COMMANDS** 👑\n"
    else:
        for p in perms["permissions"]:
            msg += f"- `!{p}`\n"

    await ctx.send(msg)


@bot.command(name="check_perm")
async def check_perm_cmd(ctx, member: str, command: str):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    has_perm = access_control.has_permission(member, command)
    role = access_control.get_role(member)
    icon = access_control.get_role_icon(role)

    if has_perm:
        await ctx.send(f"✅ **{member}** ({icon} {role}) có quyền `!{command}`")
    else:
        await ctx.send(f"❌ **{member}** ({icon} {role}) KHÔNG có quyền `!{command}`")


@bot.command(name="set_leader")
async def set_leader_cmd(ctx, member: str):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    access_control.set_weekly_leader(member)
    await ctx.send(f"✅ Đã set **{member}** làm Leader tuần.")


@bot.command(name="permissions")
async def permissions_cmd(ctx):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    from access_control import PERMISSIONS

    msg = "# 🔐 ACCESS CONTROL – PERMISSIONS\n\n"

    for role, perms in PERMISSIONS.items():
        icon = access_control.get_role_icon(role)
        role_name = access_control.get_role_name(role)

        msg += f"## {icon} {role_name}\n"
        if "*" in perms:
            msg += "- **ALL COMMANDS**\n"
        else:
            for p in perms:
                msg += f"- `!{p}`\n"
        msg += "\n"

    if access_control.get_weekly_leader():
        msg += f"---\n**Leader tuần:** {access_control.get_weekly_leader()}\n"

    for part in reporter._split(msg):
        await ctx.send(part)


# ============ SOCRATIC TUTOR ============

@bot.command(name="socratic")
async def socratic_cmd(ctx, topic: str):
    if not access_control.has_permission(ctx.author, "socratic"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    user_id = ctx.author.id
    member = ctx.author.display_name

    await ctx.send(f"🎓 Đang khởi tạo Socratic Tutor cho topic **{topic}**...")

    try:
        result = await asyncio.to_thread(
            socratic_tutor.start_session, user_id, member, topic
        )
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {e}")
        print(f"[socratic] {e}")
        return

    embed = discord.Embed(
        title=f"🎓 SOCRATIC TUTOR – {topic.upper()}",
        description=f"**Câu {result['turn']}/{result['max_turns']}**",
        color=discord.Color.purple(),
    )

    embed.add_field(name="❓ Câu hỏi", value=result["question"], inline=False)
    embed.add_field(name="💡 Cách trả lời", value="Gõ `!answer <câu trả lời>`", inline=False)
    embed.add_field(name="🔧 Trợ giúp", value="`!hint` | `!skip` | `!end_socratic`", inline=False)
    embed.set_footer(text="Bot không đưa đáp án – bạn tự khám phá!")

    await ctx.send(embed=embed)


@bot.command(name="answer")
async def answer_cmd(ctx, *, answer: str):
    if not access_control.has_permission(ctx.author, "socratic"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    user_id = ctx.author.id
    result = await asyncio.to_thread(
        socratic_tutor.answer_question, user_id, answer
    )

    if "error" in result:
        await ctx.send(f"❌ {result['error']}")
        return

    eval_embed = discord.Embed(
        title="📝 Đánh giá",
        description=result["evaluation"],
        color=discord.Color.blue(),
    )
    eval_embed.add_field(name="Điểm", value=f"{result['score']}/5", inline=True)
    await ctx.send(embed=eval_embed)

    if result.get("is_completed"):
        report = result["final_report"]
        await _send_socratic_final_report(ctx, report)
        return

    next_embed = discord.Embed(
        title=f"❓ Câu hỏi {result['turn']}/{result['max_turns']}",
        description=result["next_question"],
        color=discord.Color.purple(),
    )
    next_embed.set_footer(text="Gõ !answer <câu trả lời>")
    await ctx.send(embed=next_embed)


@bot.command(name="hint")
async def hint_cmd(ctx):
    if not access_control.has_permission(ctx.author, "socratic"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    hint = await asyncio.to_thread(socratic_tutor.get_hint, ctx.author.id)

    if not hint:
        await ctx.send("❌ Chưa có session. Gõ `!socratic <topic>` để bắt đầu.")
        return

    await ctx.send(f"💡 **Gợi ý:** {hint}")


@bot.command(name="skip")
async def skip_cmd(ctx):
    if not access_control.has_permission(ctx.author, "socratic"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    result = await asyncio.to_thread(socratic_tutor.skip_question, ctx.author.id)

    if "error" in result:
        await ctx.send(f"❌ {result['error']}")
        return

    if result.get("is_completed"):
        report = result["final_report"]
        await _send_socratic_final_report(ctx, report)
        return

    next_embed = discord.Embed(
        title=f"⏭️ Đã bỏ qua – Câu {result['turn']}/{result['max_turns']}",
        description=result["next_question"],
        color=discord.Color.purple(),
    )
    await ctx.send(embed=next_embed)


@bot.command(name="end_socratic")
async def end_socratic_cmd(ctx):
    if not access_control.has_permission(ctx.author, "socratic"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    report = await asyncio.to_thread(socratic_tutor.end_session, ctx.author.id)

    if not report:
        await ctx.send("❌ Chưa có session.")
        return

    await _send_socratic_final_report(ctx, report)


@bot.command(name="socratic_status")
async def socratic_status_cmd(ctx):
    status = socratic_tutor.get_status(ctx.author.id)

    if not status:
        await ctx.send("❌ Chưa có session. Gõ `!socratic <topic>` để bắt đầu.")
        return

    msg = f"# 🎓 SOCRATIC STATUS\n\n"
    msg += f"**Topic:** {status['topic']}\n"
    msg += f"**Câu:** {status['turn']}/{status['max_turns']}\n"
    msg += f"**Trạng thái:** {status['status']}\n"
    msg += f"**Bắt đầu:** {status['started_at']}\n"

    await ctx.send(msg)


async def _send_socratic_final_report(ctx, report):
    embed = discord.Embed(
        title=f"🎉 HOÀN THÀNH SOCRATIC – {report['topic'].upper()}",
        description=report.get("summary", ""),
        color=discord.Color.gold(),
    )

    embed.add_field(
        name="📊 Thống kê",
        value=(
            f"• Tổng câu: **{report['total_questions']}**\n"
            f"• Đã trả lời: **{report['answered']}**\n"
            f"• Bỏ qua: **{report['skipped']}**\n"
            f"• Điểm TB: **{report['avg_score']}/5**\n"
            f"• Thời gian: **{report['duration_minutes']} phút**"
        ),
        inline=False,
    )

    if report.get("strengths"):
        strengths = "\n".join(f"• {s}" for s in report["strengths"][:3])
        embed.add_field(name="💪 Điểm mạnh", value=strengths[:500], inline=False)

    if report.get("weaknesses"):
        weaknesses = "\n".join(f"• {w}" for w in report["weaknesses"][:3])
        embed.add_field(name="⚠️ Cần cải thiện", value=weaknesses[:500], inline=False)

    if report.get("recommendations"):
        recs = "\n".join(f"• {r}" for r in report["recommendations"][:3])
        embed.add_field(name="📚 Gợi ý", value=recs[:500], inline=False)

    embed.set_footer(text=f"Gõ !socratic <topic> để bắt đầu session mới")
    await ctx.send(embed=embed)

    if sheets is not None:
        try:
            week = get_current_week()
            insights = {
                "insights": [f"Socratic session: {report['topic']} – {report['avg_score']}/5"],
                "unique_perspective": report.get("summary", "")[:150],
                "real_world_application": "",
                "code_snippet": "",
                "code_language": "none",
            }
            await asyncio.to_thread(
                sheets.sync_insights, week, report["member"],
                report["topic"], insights, report["avg_score"]
            )
            print(f"[Socratic] Saved insights for {report['member']}")
        except Exception as e:
            print(f"[Socratic] Sheets error: {e}")


# ============ PRACTICE QUIZ ============

@bot.command(name="quiz")
async def quiz_cmd(ctx, topic: str, num: int = 5):
    if not access_control.has_permission(ctx.author, "quiz"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    user_id = ctx.author.id
    member = ctx.author.display_name

    await ctx.send(f"📝 Đang sinh quiz cho topic **{topic}** ({num} câu)...")

    try:
        result = await asyncio.to_thread(
            practice_quiz.start_quiz, user_id, member, topic, num
        )
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {e}")
        print(f"[quiz] {e}")
        return

    if "error" in result:
        await ctx.send(f"❌ {result['error']}")
        return

    await _send_quiz_question(ctx, result, is_new=True)


@bot.command(name="quiz_answer")
async def quiz_answer_cmd(ctx, answer: str):
    if not access_control.has_permission(ctx.author, "quiz"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    result = await asyncio.to_thread(
        practice_quiz.answer_question, ctx.author.id, answer
    )

    if "error" in result:
        await ctx.send(f"❌ {result['error']}")
        return

    if result["is_correct"]:
        eval_embed = discord.Embed(
            title="✅ CHÍNH XÁC!",
            description=result.get("explanation", ""),
            color=discord.Color.green(),
        )
    else:
        eval_embed = discord.Embed(
            title="❌ SAI RỒI!",
            description=f"**Đáp án đúng:** `{result['correct_answer']}`\n\n{result.get('explanation', '')}",
            color=discord.Color.red(),
        )
    await ctx.send(embed=eval_embed)

    if result.get("is_completed"):
        await _send_quiz_result(ctx, result["result"])
        return

    await _send_quiz_question(ctx, result["next_question"], is_new=False)


@bot.command(name="quiz_hint")
async def quiz_hint_cmd(ctx):
    if not access_control.has_permission(ctx.author, "quiz"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    hint = await asyncio.to_thread(practice_quiz.get_hint, ctx.author.id)

    if not hint:
        await ctx.send("❌ Chưa có quiz. Gõ `!quiz <topic>` để bắt đầu.")
        return

    await ctx.send(f"💡 **Gợi ý:** {hint}")


@bot.command(name="quiz_skip")
async def quiz_skip_cmd(ctx):
    if not access_control.has_permission(ctx.author, "quiz"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    result = await asyncio.to_thread(practice_quiz.skip_question, ctx.author.id)

    if "error" in result:
        await ctx.send(f"❌ {result['error']}")
        return

    if result.get("is_completed"):
        await _send_quiz_result(ctx, result["result"])
        return

    await ctx.send("⏭️ Đã bỏ qua câu hỏi.")
    await _send_quiz_question(ctx, result["next_question"], is_new=False)


@bot.command(name="quiz_end")
async def quiz_end_cmd(ctx):
    if not access_control.has_permission(ctx.author, "quiz"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    result = await asyncio.to_thread(practice_quiz.end_quiz, ctx.author.id)

    if not result:
        await ctx.send("❌ Chưa có quiz.")
        return

    await _send_quiz_result(ctx, result)


@bot.command(name="quiz_status")
async def quiz_status_cmd(ctx):
    status = practice_quiz.get_status(ctx.author.id)

    if not status:
        await ctx.send("❌ Chưa có quiz. Gõ `!quiz <topic>` để bắt đầu.")
        return

    msg = f"# 📝 QUIZ STATUS\n\n"
    msg += f"**Topic:** {status['topic']}\n"
    msg += f"**Câu:** {status['current']}/{status['total']}\n"
    msg += f"**Đúng:** {status['correct']}\n"
    msg += f"**Trạng thái:** {status['status']}\n"

    await ctx.send(msg)


async def _send_quiz_question(ctx, q, is_new=False):
    difficulty_icon = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}.get(
        q.get("difficulty", "Medium"), "⚪"
    )

    embed = discord.Embed(
        title=f"📝 QUIZ – CÂU {q['index']}/{q['total']}",
        description=f"{difficulty_icon} **{q['question']}**\n\n{q['options']}",
        color=discord.Color.blue(),
    )

    embed.add_field(name="💡 Cách trả lời", value="Gõ `!quiz_answer <A/B/C/D>`", inline=False)
    embed.add_field(name="🔧 Trợ giúp", value="`!quiz_hint` | `!quiz_skip` | `!quiz_end`", inline=False)
    embed.set_footer(text=f"Topic: {q['topic']}")

    await ctx.send(embed=embed)


async def _send_quiz_result(ctx, result):
    embed = discord.Embed(
        title=f"{result['icon']} KẾT QUẢ QUIZ – {result['topic'].upper()}",
        description=f"**{result['level']}**",
        color=discord.Color.gold() if result['score'] >= 3.5 else discord.Color.red(),
    )

    embed.add_field(
        name="📊 Thống kê",
        value=(
            f"• Tổng câu: **{result['total']}**\n"
            f"• Đúng: **{result['correct']}** ✅\n"
            f"• Sai: **{result['wrong']}** ❌\n"
            f"• Bỏ qua: **{result['skipped']}**\n"
            f"• Điểm: **{result['score']}/5**\n"
            f"• Thời gian: **{result['duration_minutes']} phút**"
        ),
        inline=False,
    )

    if result.get("summary"):
        embed.add_field(name="📝 Nhận xét", value=result["summary"][:500], inline=False)

    if result.get("weak_questions"):
        weak_text = ""
        for wq in result["weak_questions"][:3]:
            weak_text += f"❌ {wq['question'][:80]}\n"
            weak_text += f"   Đúng: `{wq['correct_answer']}` – Bạn: `{wq['user_answer']}`\n\n"
        embed.add_field(name="🎯 Câu cần ôn lại", value=weak_text[:800], inline=False)

    if result.get("recommendations"):
        recs = "\n".join(f"• {r}" for r in result["recommendations"][:3])
        embed.add_field(name="📚 Gợi ý", value=recs[:500], inline=False)

    embed.set_footer(text="Gõ !quiz <topic> để làm quiz mới")
    await ctx.send(embed=embed)

    if sheets is not None:
        try:
            week = get_current_week()
            insights = {
                "insights": [f"Quiz {result['topic']}: {result['correct']}/{result['total']} đúng ({result['score']}/5)"],
                "unique_perspective": result.get("summary", "")[:150],
                "real_world_application": "",
                "code_snippet": "",
                "code_language": "none",
            }
            await asyncio.to_thread(
                sheets.sync_insights, week, result["member"],
                f"quiz_{result['topic']}", insights, result["score"]
            )
            print(f"[Quiz] Saved insights for {result['member']}")
        except Exception as e:
            print(f"[Quiz] Sheets error: {e}")


# ============ PROGRESS PREDICTOR ============

@bot.command(name="predict")
async def predict_cmd(ctx, member: str = None, weeks: int = 4):
    if not access_control.has_permission(ctx.author, "predict"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    if member is None:
        member = ctx.author.display_name

    member_clean = member.split("-NR.")[0].strip()

    await ctx.send(f"🔮 Đang phân tích tiến bộ của **{member_clean}**...")

    try:
        result = await asyncio.to_thread(
            progress_predictor.predict, member_clean, weeks
        )
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {e}")
        print(f"[predict] {e}")
        return

    if "error" in result:
        await ctx.send(f"❌ {result['error']}")
        return

    await _send_prediction(ctx, result)


@bot.command(name="predict_all")
async def predict_all_cmd(ctx, weeks: int = 4):
    if not access_control.has_permission(ctx.author, "predict"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    await ctx.send(f"🔮 Đang phân tích toàn cohort...")

    try:
        results = await asyncio.to_thread(
            progress_predictor.predict_all, weeks
        )
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {e}")
        return

    if not results:
        await ctx.send("❌ Không có đủ dữ liệu để dự đoán.")
        return

    overview = progress_predictor.get_cohort_overview()
    header_embed = discord.Embed(
        title=f"🔮 DỰ ĐOÁN COHORT – {weeks} TUẦN TỚI",
        description=(
            f"**Members có data:** {overview['with_data']}/{overview['total_members']}\n"
            f"**Điểm TB:** {overview['avg_score']}/5\n"
            f"📈 Improving: {overview['improving']} | "
            f"➡️ Plateau: {overview['plateau']} | "
            f"📉 Declining: {overview['declining']}"
        ),
        color=discord.Color.purple(),
    )
    await ctx.send(embed=header_embed)

    for r in results:
        trend_icon = r["trend_icon"]
        last_pred = r["predictions"][-1]["predicted_score"]

        embed = discord.Embed(
            title=f"{trend_icon} {r['member']}",
            description=(
                f"**Hiện tại:** {r['last_score']}/5 (TB: {r['current_avg']}/5)\n"
                f"**Xu hướng:** {r['trend_desc']} (slope: {r['slope']:+.3f}/tuần)\n"
                f"**Dự đoán W+{weeks}:** {last_pred}/5"
            ),
            color=_get_trend_color(r["trend"]),
        )

        high_warnings = [w for w in r["warnings"] if w["severity"] == "high"]
        if high_warnings:
            embed.add_field(name="🚨 Cảnh báo", value=high_warnings[0]["message"][:200], inline=False)

        await ctx.send(embed=embed)


@bot.command(name="cohort_overview")
async def cohort_overview_cmd(ctx):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    overview = progress_predictor.get_cohort_overview()

    msg = f"# 📊 COHORT OVERVIEW\n\n"
    msg += f"**Tổng members:** {overview['total_members']}\n"
    msg += f"**Có data:** {overview['with_data']}\n"
    msg += f"**Điểm TB:** {overview['avg_score']}/5\n\n"
    msg += f"**Phân loại xu hướng:**\n"
    msg += f"- 📈 Đang cải thiện: **{overview['improving']}**\n"
    msg += f"- ➡️ Chững lại: **{overview['plateau']}**\n"
    msg += f"- 📉 Đang giảm: **{overview['declining']}**\n"

    await ctx.send(msg)


async def _send_prediction(ctx, result):
    embed = discord.Embed(
        title=f"🔮 DỰ ĐOÁN TIẾN BỘ – {result['member'].upper()}",
        description=result["summary"].get("summary", ""),
        color=_get_trend_color(result["trend"]),
    )

    embed.add_field(
        name="📊 Hiện tại",
        value=(
            f"• Điểm gần nhất: **{result['last_score']}/5**\n"
            f"• Điểm TB 8 tuần: **{result['current_avg']}/5**\n"
            f"• Xu hướng: {result['trend_icon']} **{result['trend_desc']}**\n"
            f"• Slope: **{result['slope']:+.3f}/tuần**\n"
            f"• Độ dao động: **{result['volatility']}**"
        ),
        inline=False,
    )

    history_text = " → ".join(f"**W{h['week']}**: {h['total']}" for h in result["history"])
    embed.add_field(name="📈 Lịch sử", value=history_text[:500], inline=False)

    pred_text = ""
    for p in result["predictions"]:
        conf_bar = "█" * int(p["confidence"] * 10) + "░" * (10 - int(p["confidence"] * 10))
        pred_text += f"**W{p['week']}:** {p['predicted_score']}/5 `{conf_bar}` {int(p['confidence']*100)}%\n"

    embed.add_field(
        name=f"🔮 Dự đoán {len(result['predictions'])} tuần tới",
        value=pred_text[:500],
        inline=False,
    )

    if result["warnings"]:
        warn_text = ""
        for w in result["warnings"][:3]:
            warn_text += f"{w['message']}\n\n"
        embed.add_field(name="⚠️ Cảnh báo", value=warn_text[:800], inline=False)

    recs = result["summary"].get("recommendations", [])
    if recs:
        rec_text = "\n".join(f"• {r}" for r in recs[:3])
        embed.add_field(name="📚 Gợi ý cải thiện", value=rec_text[:500], inline=False)

    embed.set_footer(text="Dự đoán dựa trên linear regression – có sai số!")
    await ctx.send(embed=embed)


def _get_trend_color(trend):
    colors = {
        "improving": discord.Color.green(),
        "slowly_improving": discord.Color.teal(),
        "plateau": discord.Color.gold(),
        "declining": discord.Color.red(),
    }
    return colors.get(trend, discord.Color.blue())


# ============ CHAT BOT ============

@bot.command(name="chat")
async def chat_cmd(ctx, *, message: str = None):
    if not access_control.has_permission(ctx.author, "chat"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    if message is None:
        await ctx.send(
            "💬 **Cách dùng:** `!chat <tin nhắn của bạn>`\n\n"
            "Ví dụ:\n"
            "• `!chat Em không hiểu phần induction`\n"
            "• `!chat Gợi ý cách học hiệu quả`\n"
            "• `!chat Tôi muốn cải thiện phần depth`"
        )
        return

    user_id = ctx.author.id
    member = ctx.author.display_name
    role = access_control.get_role(ctx.author)

    async with ctx.typing():
        try:
            result = await asyncio.to_thread(
                chat_bot.chat, user_id, member, message, role
            )
        except Exception as e:
            await ctx.send(f"❌ Lỗi: {e}")
            print(f"[chat] {e}")
            return

    if "error" in result:
        await ctx.send(f"❌ {result['error']}")
        return

    role_icon = access_control.get_role_icon(role)
    embed = discord.Embed(
        title=f"💬 CHAT với {member}",
        description=result["reply"][:4000],
        color=discord.Color.blue(),
    )
    embed.set_footer(text=f"{role_icon} {role} • Tin nhắn #{result['session_message_count']}")
    await ctx.send(embed=embed)

    insights = result.get("insights", [])
    if insights:
        insight_text = ""
        for ins in insights:
            type_label = chat_bot.INSIGHT_TYPES.get(ins["type"], "📝")
            insight_text += f"{type_label} {ins['content']}\n"

        insight_embed = discord.Embed(
            title="🧠 Insights được ghi nhận",
            description=insight_text[:2000],
            color=discord.Color.purple(),
        )
        insight_embed.set_footer(text="Đã lưu vào Knowledge Vault để hỗ trợ nhóm!")
        await ctx.send(embed=insight_embed)

        if sheets is not None:
            try:
                week = get_current_week()
                for ins in insights:
                    await asyncio.to_thread(
                        sheets.sync_chat_insight,
                        week, member, role, ins["topic"],
                        ins["content"], ins["type"]
                    )
                print(f"[Chat] Saved {len(insights)} insights for {member}")
            except Exception as e:
                print(f"[Chat] Sheets error: {e}")


@bot.command(name="chat_history")
async def chat_history_cmd(ctx):
    if not access_control.has_permission(ctx.author, "chat"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    history = chat_bot.get_history(ctx.author.id, limit=10)

    if not history:
        await ctx.send("💬 Chưa có lịch sử chat. Gõ `!chat <message>` để bắt đầu.")
        return

    msg = f"# 💬 LỊCH SỬ CHAT\n\n"
    for m in history:
        if m["role"] == "user":
            msg += f"**👤 Bạn:** {m['content'][:200]}\n\n"
        else:
            msg += f"**🤖 Bot:** {m['content'][:200]}\n\n"

    for part in reporter._split(msg):
        await ctx.send(part)


@bot.command(name="chat_status")
async def chat_status_cmd(ctx):
    info = chat_bot.get_session_info(ctx.author.id)

    if not info:
        await ctx.send("💬 Chưa có session. Gõ `!chat <message>` để bắt đầu.")
        return

    msg = f"# 💬 CHAT STATUS\n\n"
    msg += f"**Member:** {info['member']}\n"
    msg += f"**Role:** {info['role']}\n"
    msg += f"**Số tin nhắn:** {info['message_count']}\n"
    msg += f"**Bắt đầu:** {info['started_at']}\n"

    await ctx.send(msg)


@bot.command(name="chat_clear")
async def chat_clear_cmd(ctx):
    if not access_control.has_permission(ctx.author, "chat"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    cleared = chat_bot.clear_session(ctx.author.id)

    if cleared:
        await ctx.send("✅ Đã xóa session. Gõ `!chat <message>` để bắt đầu mới.")
    else:
        await ctx.send("💬 Không có session để xóa.")


@bot.command(name="chat_insights")
async def chat_insights_cmd(ctx, member: str = None):
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    if sheets is None:
        await ctx.send("❌ Google Sheets chưa kết nối.")
        return

    if member:
        member_clean = member.split("-NR.")[0].strip()
        insights = await asyncio.to_thread(
            sheets.load_chat_insights, member_clean, 20
        )
        title = f"CHAT INSIGHTS – {member_clean}"
    else:
        insights = await asyncio.to_thread(sheets.load_chat_insights, None, 20)
        title = "CHAT INSIGHTS – ALL"

    if not insights:
        await ctx.send(f"❌ Không có chat insights cho {title}.")
        return

    msg = f"# 💬 {title}\n\n"
    for i in insights:
        type_label = chat_bot.INSIGHT_TYPES.get(i.get("Type", ""), "📝")
        msg += f"{type_label} **{i.get('Member', '')}** ({i.get('Role', '')})\n"
        msg += f"Topic: *{i.get('Topic', '')}*\n"
        msg += f"{i.get('Insight', '')[:200]}\n"
        msg += f"_{i.get('Timestamp', '')}_\n\n"

    for part in reporter._split(msg):
        await ctx.send(part)


# ============ WEEKLY PLANNER COMMANDS ============

@bot.command(name="plan")
async def plan_cmd(ctx, week: int = None):
    """Xem kế hoạch tuần (Admin/Leader)"""
    if not access_control.has_permission(ctx.author, "plan"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    if week is None:
        week = get_current_week()

    info = time_tracker.get_current_info()
    mode = info["mode"]

    await ctx.send(f"📋 Đang lập kế hoạch tuần {week} ({mode})...")

    try:
        plan = await asyncio.to_thread(
            weekly_planner.generate_plan, week, mode
        )
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {e}")
        print(f"[plan] {e}")
        return

    if not plan:
        await ctx.send("❌ Không thể lập kế hoạch.")
        return

    plan["week"] = week
    plan["mode"] = mode

    # Format
    msg = weekly_planner.format_plan_for_discord(plan)

    for part in reporter._split(msg):
        await ctx.send(part)

    # Sync to Sheets
    if sheets is not None:
        try:
            await asyncio.to_thread(
                sheets.sync_plan, week, mode, plan
            )
            print(f"[Plan] Synced to Sheets")
        except Exception as e:
            print(f"[Plan] Sheets error: {e}")


@bot.command(name="plan_create")
async def plan_create_cmd(ctx, week: int = None):
    """Tạo và post kế hoạch lên channel hiện tại"""
    if not access_control.has_permission(ctx.author, "plan"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    if week is None:
        week = get_current_week()

    info = time_tracker.get_current_info()
    mode = info["mode"]

    await ctx.send(f"📋 Đang tạo kế hoạch tuần {week}...")

    try:
        plan = await asyncio.to_thread(
            weekly_planner.generate_plan, week, mode
        )
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {e}")
        return

    if not plan:
        await ctx.send("❌ Không thể tạo kế hoạch.")
        return

    plan["week"] = week
    plan["mode"] = mode

    # Format as embed
    embed = discord.Embed(
        title=f"📋 KẾ HOẠCH TUẦN {week}",
        description=f"**Mode:** {mode}",
        color=discord.Color.blue(),
    )

    if plan.get("overview"):
        embed.add_field(
            name="📊 Tổng quan",
            value=plan["overview"][:1000],
            inline=False,
        )

    if plan.get("group_tasks"):
        tasks = "\n".join(f"• {t}" for t in plan["group_tasks"][:5])
        embed.add_field(
            name="🎯 Task nhóm",
            value=tasks[:1000],
            inline=False,
        )

    if plan.get("member_tasks"):
        member_text = ""
        for member, tasks in list(plan["member_tasks"].items())[:5]:
            member_text += f"**{member}:**\n"
            for task in tasks[:3]:
                member_text += f"  • {task}\n"
        embed.add_field(
            name="👥 Task cá nhân",
            value=member_text[:1000],
            inline=False,
        )

    if plan.get("warnings"):
        warns = "\n".join(f"⚠️ {w}" for w in plan["warnings"][:3])
        embed.add_field(
            name="⚠️ Cảnh báo",
            value=warns[:500],
            inline=False,
        )

    if plan.get("focus_topics"):
        topics = ", ".join(f"`{t}`" for t in plan["focus_topics"][:5])
        embed.add_field(
            name="📚 Topic cần tập trung",
            value=topics[:500],
            inline=False,
        )

    embed.set_footer(text=f"Tạo bởi {ctx.author.display_name}")

    await ctx.send(embed=embed)

    # Sync Sheets
    if sheets is not None:
        try:
            await asyncio.to_thread(
                sheets.sync_plan, week, mode, plan
            )
        except Exception as e:
            print(f"[Plan] Sheets error: {e}")


@bot.command(name="notify")
async def notify_cmd(ctx, *, message: str = None):
    """Thông báo nhóm (Admin/Leader)"""
    if not access_control.has_permission(ctx.author, "notify"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    if message is None:
        await ctx.send("Cú pháp: `!notify <nội dung thông báo>`")
        return

    # Gửi thông báo vào channel hiện tại
    embed = discord.Embed(
        title="📢 THÔNG BÁO",
        description=message,
        color=discord.Color.gold(),
        timestamp=datetime.now(),
    )
    embed.set_footer(text=f"Từ {ctx.author.display_name}")

    await ctx.send(embed=embed)

    # Xóa lệnh gốc (nếu có quyền)
    try:
        await ctx.message.delete()
    except Exception:
        pass


@bot.command(name="remind")
async def remind_cmd(ctx, member: str, *, task: str):
    """Nhắc nhở member (Admin/Leader)"""
    if not access_control.has_permission(ctx.author, "notify"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    member_clean = member.split("-NR.")[0].strip()

    embed = discord.Embed(
        title="🔔 NHẮC NHỞ",
        description=f"**{member_clean}**\n\n{task}",
        color=discord.Color.orange(),
        timestamp=datetime.now(),
    )
    embed.set_footer(text=f"Từ {ctx.author.display_name}")

    await ctx.send(embed=embed)


@bot.command(name="plan_history")
async def plan_history_cmd(ctx):
    """Xem lịch sử kế hoạch (Admin)"""
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    if sheets is None:
        await ctx.send("❌ Google Sheets chưa kết nối.")
        return

    plans = await asyncio.to_thread(sheets.load_plans, 10)

    if not plans:
        await ctx.send("❌ Chưa có kế hoạch nào.")
        return

    msg = "# 📋 LỊCH SỬ KẾ HOẠCH\n\n"
    for p in plans[-5:]:
        msg += f"## Tuần {p.get('Tuan', '?')} – {p.get('Mode', '?')}\n"
        msg += f"{p.get('Overview', '')[:200]}\n"
        msg += f"_{p.get('Timestamp', '')}_\n\n"

    for part in reporter._split(msg):
        await ctx.send(part)

# ============ SWITCH BOARD COMMANDS ============

@bot.command(name="sync_calendar")
async def sync_calendar_cmd(ctx, member: str, week: int = None):
    """
    Sync 1 member → Google Calendar
    
    Cách dùng:
        !sync_calendar DatPT          (tuần hiện tại)
        !sync_calendar DatPT 3        (tuần 3)
    """
    if not is_admin(ctx):
        await ctx.send("❌ Chỉ Admin.")
        return

    if week is None:
        week = get_current_week()

    member_clean = member.split("-NR.")[0].strip()

    await ctx.send(f"📤 Đang sync **{member_clean}** W{week} → Google Calendar...")

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{SWITCH_BOARD_URL}/switch/sync-score-to-calendar",
                params={"week": week, "member": member_clean},
                timeout=15.0,
            )

            if r.status_code == 404:
                await ctx.send(f"❌ Không tìm thấy **{member_clean}** tuần {week} trong DB.")
                return

            if r.status_code == 503:
                await ctx.send(
                    "❌ Switch Board chưa chạy!\n"
                    "Chạy lệnh này ở terminal khác:\n"
                    "```\ncd \"D:\\Bot deepseek\\switch\"\npython panel.py\n```"
                )
                return

            r.raise_for_status()
            data = r.json()

        # Parse result
        score = data.get("score", {})
        total = score.get("total", "?")

        routed = data.get("routed", [])
        html_link = None
        if routed and routed[0].get("result"):
            html_link = routed[0]["result"].get("htmlLink")

        # Build embed
        embed = discord.Embed(
            title="✅ SYNCED TO GOOGLE CALENDAR",
            description=(
                f"**Member:** {member_clean}\n"
                f"**Tuần:** {week}\n"
                f"**Điểm:** {total}/5"
            ),
            color=discord.Color.green(),
        )

        if html_link:
            embed.add_field(
                name="🔗 Event Link",
                value=f"[Mở Google Calendar]({html_link})",
                inline=False,
            )

        embed.set_footer(text=f"Sync bởi {ctx.author.display_name}")
        await ctx.send(embed=embed)

    except httpx.ConnectError:
        await ctx.send(
            "❌ **Không kết nối được Switch Board!**\n\n"
            "**Chạy lệnh này ở terminal khác:**\n"
            "```\ncd \"D:\\Bot deepseek\\switch\"\npython panel.py\n```"
        )
    except httpx.TimeoutException:
        await ctx.send("⏱️ Timeout – Switch Board phản hồi quá chậm.")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {e}")
        print(f"[sync_calendar] {e}")


@bot.command(name="sync_all_calendar")
async def sync_all_calendar_cmd(ctx, week: int = None):
    """
    Sync toàn bộ members của tuần → Google Calendar
    
    Cách dùng:
        !sync_all_calendar          (tuần hiện tại)
        !sync_all_calendar 3        (tuần 3)
    """
    if not is_admin(ctx):
        await ctx.send("❌ Chỉ Admin.")
        return

    if week is None:
        week = get_current_week()

    await ctx.send(f"📤 Đang sync TOÀN BỘ members W{week} → Google Calendar...")

    try:
        async with httpx.AsyncClient() as client:
            # 1. Lấy danh sách scores tuần này từ Switch
            r = await client.get(
                f"{SWITCH_BOARD_URL}/cogni/scores",
                params={"week": week},
                timeout=10.0,
            )

            if r.status_code == 503:
                await ctx.send("❌ Switch Board chưa chạy!")
                return

            r.raise_for_status()
            data = r.json()
            scores = data.get("scores", [])

            if not scores:
                await ctx.send(f"❌ Tuần {week} chưa có data.")
                return

            # 2. Sync từng member
            success = 0
            failed = 0
            events = []

            for score in scores:
                member = score.get("member")
                try:
                    r2 = await client.post(
                        f"{SWITCH_BOARD_URL}/switch/sync-score-to-calendar",
                        params={"week": week, "member": member},
                        timeout=15.0,
                    )
                    if r2.status_code == 200:
                        result = r2.json()
                        link = None
                        routed = result.get("routed", [])
                        if routed and routed[0].get("result"):
                            link = routed[0]["result"].get("htmlLink")
                        events.append({"member": member, "link": link})
                        success += 1
                    else:
                        failed += 1
                except Exception as e:
                    print(f"[sync_all] {member}: {e}")
                    failed += 1

        # Build summary
        msg = f"# 📤 SYNC W{week} → GOOGLE CALENDAR\n\n"
        msg += f"**Thành công:** {success}\n"
        msg += f"**Thất bại:** {failed}\n\n"

        if events:
            msg += "## 🎯 Events đã tạo\n"
            for e in events:
                if e["link"]:
                    msg += f"- **{e['member']}** – [Mở]({e['link']})\n"
                else:
                    msg += f"- **{e['member']}**\n"

        for part in reporter._split(msg):
            await ctx.send(part)

    except httpx.ConnectError:
        await ctx.send("❌ Không kết nối được Switch Board! Chạy `python panel.py` trước.")
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {e}")
        print(f"[sync_all_calendar] {e}")


@bot.command(name="switch_status")
async def switch_status_cmd(ctx):
    """Xem trạng thái Switch Board"""
    if not is_admin(ctx):
        await ctx.send("❌ Chỉ Admin.")
        return

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{SWITCH_BOARD_URL}/panel/status",
                timeout=5.0,
            )
            r.raise_for_status()
            data = r.json()

        msg = "# 🔌 SWITCH BOARD STATUS\n\n"
        msg += f"**Tổng:** {data['total']} sockets\n"
        msg += f"**ON:** {data['by_status']['on']}\n"
        msg += f"**OFF:** {data['by_status']['off']}\n\n"

        msg += "## Sockets\n"
        for s in data["sockets"]:
            icon = {"on": "🟢", "off": "⚪", "error": "🔴", "warning": "🟠"}.get(s["status"], "❓")
            msg += f"{icon} **{s['name']}** v{s['version']}\n"
            msg += f"   Stats: {s['stats']['calls']} calls / {s['stats']['failed']} failed\n\n"

        await ctx.send(msg)

    except httpx.ConnectError:
        await ctx.send(
            "❌ **Switch Board chưa chạy!**\n\n"
            "**Chạy ở terminal khác:**\n"
            "```\ncd \"D:\\Bot deepseek\\switch\"\npython panel.py\n```"
        )
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {e}")

# ============ ADVANCED MODE COMMANDS ============

@bot.command(name="my_mode")
async def my_mode_cmd(ctx, member: str = None):
    """Xem tier và recommendations"""
    if not access_control.has_permission(ctx.author, "advanced_mode"):
        await ctx.send("❌ Bạn không có quyền dùng lệnh này.")
        return

    if member is None:
        member = ctx.author.display_name

    member_clean = member.split("-NR.")[0].strip()
    week = get_current_week()

    await ctx.send(f"🎯 Đang phân tích tier của **{member_clean}**...")

    try:
        info = await asyncio.to_thread(
            advanced_mode.get_recommendations, member_clean, week
        )
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {e}")
        print(f"[my_mode] {e}")
        return

    # Format embed
    tier_colors = {
        "Foundation": discord.Color.orange(),
        "Advanced": discord.Color.blue(),
        "Mastery": discord.Color.green(),
    }

    embed = discord.Embed(
        title=f"{info['tier_icon']} TIER: {info['tier'].upper()}",
        description=f"**{info['member']}**\n_{info['tier_description']}_",
        color=tier_colors.get(info["tier"], discord.Color.blue()),
    )

    embed.add_field(
        name="📊 Điểm TB 4 tuần",
        value=f"**{info['avg_score']}/5**",
        inline=True,
    )
    embed.add_field(
        name="📅 Roadmap Mode",
        value=f"**{info['roadmap_mode']}**",
        inline=True,
    )

    if info.get("focus"):
        focus_text = "\n".join(f"• {f}" for f in info["focus"][:5])
        embed.add_field(
            name="🎯 Focus",
            value=focus_text[:1000],
            inline=False,
        )

    if info.get("activities"):
        act_text = "\n".join(f"• {a}" for a in info["activities"][:5])
        embed.add_field(
            name="📝 Activities",
            value=act_text[:1000],
            inline=False,
        )

    if info.get("resources"):
        res_text = "\n".join(f"• {r}" for r in info["resources"][:3])
        embed.add_field(
            name="📚 Resources",
            value=res_text[:500],
            inline=False,
        )

    # Next tier progress
    next_tier = info.get("next_tier", {})
    if next_tier and next_tier.get("next_tier"):
        progress = int(next_tier["progress_pct"] / 5)
        bar = "█" * progress + "░" * (20 - progress)

        embed.add_field(
            name=f"📈 Tiến độ lên {next_tier['next_tier']}",
            value=(
                f"`{bar}` **{next_tier['progress_pct']}%**\n"
                f"Cần thêm **+{next_tier['gap']} điểm** để lên tier"
            ),
            inline=False,
        )
    elif next_tier and next_tier.get("message"):
        embed.add_field(
            name="🏆 Max Tier",
            value=next_tier["message"],
            inline=False,
        )

    embed.set_footer(text="Bot tự động phân tích tier theo điểm số của bạn")

    await ctx.send(embed=embed)


@bot.command(name="tiers")
async def tiers_cmd(ctx):
    """Xem phân bố tier của cohort (Admin)"""
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    try:
        tiers = advanced_mode.get_all_tiers()
        dist = advanced_mode.get_tier_distribution()
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {e}")
        return

    msg = f"# 🎯 TIER DISTRIBUTION\n\n"
    msg += f"**Tổng members:** {dist['total']}\n\n"

    msg += f"## 🌱 Foundation ({dist['foundation']})\n"
    for item in dist["distribution"]["Foundation"]:
        msg += f"- {item['member']}: {item['avg_score']}/5\n"
    msg += "\n"

    msg += f"## 🌿 Advanced ({dist['advanced']})\n"
    for item in dist["distribution"]["Advanced"]:
        msg += f"- {item['member']}: {item['avg_score']}/5\n"
    msg += "\n"

    msg += f"## 🌳 Mastery ({dist['mastery']})\n"
    for item in dist["distribution"]["Mastery"]:
        msg += f"- {item['member']}: {item['avg_score']}/5\n"

    for part in reporter._split(msg):
        await ctx.send(part)


@bot.command(name="tier_check")
async def tier_check_cmd(ctx, member: str):
    """Check tier của member (Admin)"""
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    member_clean = member.split("-NR.")[0].strip()

    try:
        info = advanced_mode.get_tier(member_clean)
    except Exception as e:
        await ctx.send(f"❌ Lỗi: {e}")
        return

    await ctx.send(
        f"{info['icon']} **{member_clean}** – Tier: **{info['tier']}** "
        f"(Điểm TB: {info['avg_score']}/5, {info['score_count']} tuần)"
    )


@bot.command(name="tier_reset")
async def tier_reset_cmd(ctx):
    """Reset cache tier (Admin)"""
    if not is_admin(ctx):
        await ctx.send("Chi Admin moi dung duoc lenh nay.")
        return

    import os
    import shutil
    cache_dir = os.path.join(CACHE_DIR, "advanced_mode")
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            os.makedirs(cache_dir, exist_ok=True)
            await ctx.send("✅ Đã reset cache Advanced Mode.")
        except Exception as e:
            await ctx.send(f"❌ Lỗi: {e}")
    else:
        await ctx.send("ℹ️ Cache chưa có gì để reset.")


# ============ SYNC COMMANDS ============

@bot.command(name="sync_commands")
async def sync_commands_cmd(ctx):
    """Sync slash commands thủ công (Admin)"""
    if not is_admin(ctx):
        await ctx.send("❌ Chỉ Admin.")
        return

    await ctx.send("🔄 Đang sync slash commands...")
    try:
        if ctx.guild:
            guild = discord.Object(id=ctx.guild.id)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            await ctx.send(
                f"✅ Đã sync **{len(synced)}** slash commands!\n"
                f"💡 Gõ `/` sau 30 giây."
            )
        else:
            synced = await bot.tree.sync()
            await ctx.send(f"✅ Đã sync **{len(synced)}** slash commands globally!")
    except Exception as e:
        await ctx.send(f"❌ Lỗi sync: {e}")
        print(f"[sync_commands] {e}")


# ============ RUN ============

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)