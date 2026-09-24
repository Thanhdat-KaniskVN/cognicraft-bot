# slash_commands.py
"""
Slash Commands - Discord native commands với auto-complete
- Modern UI với / prefix
- Auto-complete cho tất cả commands
- Params với choices, description
"""
import discord
from discord import app_commands


def setup_slash_commands(bot, modules):
    """
    Setup tất cả slash commands.

    Args:
        bot: Discord bot instance
        modules: Dict chứa các modules
            {
                "access_control": ...,
                "time_tracker": ...,
                "collector": ...,
                "ai_scorer": ...,
                "sheets": ...,
                "reporter": ...,
                "socratic_tutor": ...,
                "practice_quiz": ...,
                "progress_predictor": ...,
                "chat_bot": ...,
                "weekly_planner": ...,
                "advanced_mode": ...,
                "error_tracker": ...,
                "solution_proposer": ...,
                "exercise_generator": ...,
                "spaced_repetition": ...,
                "scorer": ...,
                "distiller": ...,
                "resource_recommender": ...,
                "get_current_week": None,
                "is_admin": None,
                "run_ai_scoring": None,
                "generate_final_report": None,
                "save_score": None,
                "get_week_scores": None,
                "get_pending_score": None,
                "update_score_source": None,
                "get_week_participation": None,
                "get_score_history": None,
            }
    """

    # Extract modules
    access_control = modules["access_control"]
    time_tracker = modules["time_tracker"]
    collector = modules["collector"]
    sheets = modules["sheets"]
    reporter = modules["reporter"]
    socratic_tutor = modules["socratic_tutor"]
    practice_quiz = modules["practice_quiz"]
    progress_predictor = modules["progress_predictor"]
    chat_bot = modules["chat_bot"]
    weekly_planner = modules["weekly_planner"]
    advanced_mode = modules["advanced_mode"]
    error_tracker = modules["error_tracker"]
    solution_proposer = modules["solution_proposer"]
    exercise_generator = modules["exercise_generator"]
    spaced_repetition = modules["spaced_repetition"]
    scorer = modules["scorer"]

    get_current_week = modules["get_current_week"]
    is_admin = modules["is_admin"]
    run_ai_scoring = modules["run_ai_scoring"]
    generate_final_report = modules["generate_final_report"]
    save_score = modules["save_score"]
    get_week_scores = modules["get_week_scores"]
    get_pending_score = modules["get_pending_score"]
    update_score_source = modules["update_score_source"]
    get_week_participation = modules["get_week_participation"]
    get_score_history = modules["get_score_history"]

    import asyncio

    # ============================================================
    # HELPER: PERMISSION CHECK
    # ============================================================

    async def check_perm(interaction: discord.Interaction, command: str) -> bool:
        """Check permission, gửi error nếu không có quyền"""
        has_perm = access_control.has_permission(interaction.user, command)
        if not has_perm:
            await interaction.response.send_message(
                "❌ Bạn không có quyền dùng lệnh này.",
                ephemeral=True,
            )
        return has_perm

    async def check_admin(interaction: discord.Interaction) -> bool:
        """Check admin"""
        user_is_admin = any(
            r.name.lower() == "admin" for r in interaction.user.roles
        )
        if not user_is_admin:
            await interaction.response.send_message(
                "❌ Chỉ Admin mới dùng được lệnh này.",
                ephemeral=True,
            )
        return user_is_admin

    # ============================================================
    # INFO COMMANDS
    # ============================================================

    @bot.tree.command(name="week", description="Xem tuần hiện tại và Mode")
    async def slash_week(interaction: discord.Interaction):
        week = get_current_week()
        info = time_tracker.get_current_info()

        msg = f"# 📅 TUẦN {week}\n\n"
        msg += f"**Mode:** {info['mode']}\n"
        msg += f"**Thời gian:** {info['start_date']} → {info['end_date']}\n"
        if info['is_break']:
            msg += f"**Trạng thái:** 🏖️ BREAK WEEK\n"
        else:
            msg += f"**Còn lại:** {info['days_remaining']} ngày\n"

        await interaction.response.send_message(msg)

    @bot.tree.command(name="mode", description="Xem Mode của tuần hiện tại")
    async def slash_mode(interaction: discord.Interaction):
        info = time_tracker.get_current_info()

        msg = f"# 📅 TUẦN {info['week']}\n\n"
        msg += f"**Mode:** {info['mode']}\n"
        msg += f"**Sản phẩm:** "

        if info['mode'] == "Academic":
            msg += "1 checkpoint"
        elif info['mode'] == "Research Literacy":
            msg += "1 Research Note"
        elif info['mode'] == "Project":
            msg += "Code + Report + Demo"
        else:
            msg += "?"

        await interaction.response.send_message(msg)

    @bot.tree.command(name="missing", description="Xem ai chưa nộp bài")
    async def slash_missing(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        week = get_current_week()
        cp_channel = bot.get_channel(modules["CHECKPOINT_CHANNEL"])
        _, missing = await collector.collect_week(cp_channel, week)

        if not missing:
            await interaction.followup.send(f"✅ Tuần {week}: Tất cả đã nộp bài!")
        else:
            mentions = " ".join(f"@{m}" for m in missing)
            await interaction.followup.send(f"⚠️ Tuần {week}: Chưa nộp: {mentions}")

    @bot.tree.command(name="ping", description="Kiểm tra AI provider")
    async def slash_ping(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        from ai_provider import call_ai_json
        try:
            result = await asyncio.to_thread(
                call_ai_json, 'Return JSON: {"ok": 1}', 100, 1, "ping"
            )
            embed = discord.Embed(
                title="✅ AI PROVIDER OK",
                description=f"Response: `{str(result)[:80]}`",
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            err = str(e)

            if "503" in err:
                title = "⏳ GEMINI QUÁ TẢI"
                desc = "Google server quá tải (giờ cao điểm).\nThử lại sau **5-10 phút**."
                color = discord.Color.gold()
            elif "429" in err or "QUOTA" in err:
                title = "🚫 HẾT QUOTA"
                desc = "Đã dùng hết 250 requests/ngày.\nĐợi **24h** reset."
                color = discord.Color.red()
            elif "401" in err or "invalid" in err:
                title = "🔑 API KEY SAI"
                desc = "Kiểm tra `.env` → `DEEPSEEK_API_KEY`."
                color = discord.Color.red()
            else:
                title = "❌ AI PROVIDER LỖI"
                desc = f"```\n{err[:200]}\n```"
                color = discord.Color.red()

            embed = discord.Embed(title=title, description=desc, color=color)
            await interaction.followup.send(embed=embed)

    @bot.tree.command(name="my-role", description="Xem role và quyền của bạn")
    async def slash_my_role(interaction: discord.Interaction):
        role = access_control.get_role(interaction.user)
        icon = access_control.get_role_icon(role)
        role_name = access_control.get_role_name(role)
        perms = access_control.get_permissions_list(interaction.user)

        msg = f"# {icon} YOUR ROLE\n\n"
        msg += f"**Role:** {role_name}\n"
        msg += f"**Member:** {interaction.user.display_name}\n\n"

        if "*" in perms["permissions"]:
            msg += "**ALL COMMANDS** 👑\n"
        else:
            msg += f"**Commands:** {len(perms['permissions'])}\n"
            for p in perms["permissions"][:10]:
                msg += f"- `/{p}`\n"

        await interaction.response.send_message(msg, ephemeral=True)

    # ============================================================
    # ADMIN COMMANDS
    # ============================================================

    @bot.tree.command(name="confirm", description="[Admin] Xác nhận điểm AI")
    @app_commands.describe(member="Tên member (VD: DatPT)")
    async def slash_confirm(interaction: discord.Interaction, member: str):
        if not await check_admin(interaction):
            return

        week = get_current_week()
        member_clean = member.split("-NR.")[0].strip()

        pending = get_pending_score(week, member_clean)
        if not pending:
            pending = get_pending_score(week, member)

        if not pending:
            await interaction.response.send_message(
                f"❌ Không có điểm AI nào đang chờ cho **{member}** tuần {week}."
            )
            return

        update_score_source(
            week, pending["member"], "confirmed",
            changed_by=str(interaction.user.id)
        )

        if sheets is not None:
            try:
                week_scores = get_week_scores(week)
                await asyncio.to_thread(sheets.sync_scores, week_scores)
            except Exception as e:
                print(f"[Slash confirm] Sheets error: {e}")

        await interaction.response.send_message(
            f"✅ Đã xác nhận điểm cho **{pending['member']}** "
            f"tuần {week} (Tổng: {pending['total']}/5)"
        )

    @bot.tree.command(name="override", description="[Admin] Sửa điểm")
    @app_commands.describe(
        member="Tên member",
        accuracy="Điểm chính xác (0-5)",
        depth="Điểm độ sâu (0-5)",
        connection="Điểm kết nối (0-5)",
        presentation="Điểm trình bày (0-5)",
    )
    async def slash_override(
        interaction: discord.Interaction,
        member: str,
        accuracy: float,
        depth: float,
        connection: float,
        presentation: float,
    ):
        if not await check_admin(interaction):
            return

        week = get_current_week()
        member_clean = member.split("-NR.")[0].strip()

        scores = {
            "accuracy": accuracy,
            "depth": depth,
            "connection": connection,
            "presentation": presentation,
        }
        save_score(
            week, member_clean, scores,
            source="human_override",
            changed_by=str(interaction.user.id),
            note=f"Override bởi {interaction.user.display_name}",
        )
        total = scorer.calculate_total(scores)

        if sheets is not None:
            try:
                week_scores = get_week_scores(week)
                await asyncio.to_thread(sheets.sync_scores, week_scores)
            except Exception as e:
                print(f"[Slash override] Sheets error: {e}")

        await interaction.response.send_message(
            f"✅ Đã sửa điểm **{member_clean}** tuần {week}: **{total}/5**"
        )

    @bot.tree.command(name="trigger-scoring", description="[Admin] Chạy AI chấm điểm")
    @app_commands.describe(week="Tuần cần chấm (bỏ trống = tuần hiện tại)")
    async def slash_trigger_scoring(interaction: discord.Interaction, week: int = None):
        if not await check_admin(interaction):
            return

        if week is None:
            week = get_current_week()

        if time_tracker.is_break_week(week):
            await interaction.response.send_message(
                f"⚠️ Tuần {week} là BREAK WEEK - không chấm điểm."
            )
            return

        await interaction.response.send_message(
            f"⏳ Đang chạy AI scoring cho tuần {week}..."
        )

        try:
            await asyncio.wait_for(run_ai_scoring(week), timeout=600)
            await interaction.followup.send(f"✅ Đã chấm AI xong tuần {week}.")
        except asyncio.TimeoutError:
            await interaction.followup.send(f"⏱️ Timeout sau 10 phút.")
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi: {e}")

    @bot.tree.command(name="trigger-report", description="[Admin] Tạo báo cáo tuần")
    @app_commands.describe(week="Tuần cần report (bỏ trống = tuần hiện tại)")
    async def slash_trigger_report(interaction: discord.Interaction, week: int = None):
        if not await check_admin(interaction):
            return

        if week is None:
            week = get_current_week()

        await interaction.response.send_message(f"⏳ Đang tạo report tuần {week}...")

        try:
            await generate_final_report(week, interaction.channel)
            await interaction.followup.send(f"✅ Đã tạo report tuần {week}.")
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi: {e}")

    @bot.tree.command(name="history", description="[Admin] Xem lịch sử điểm")
    @app_commands.describe(
        week="Tuần cần xem",
        member="Tên member (bỏ trống = tất cả)",
    )
    async def slash_history(
        interaction: discord.Interaction,
        week: int,
        member: str = None,
    ):
        if not await check_admin(interaction):
            return

        if member:
            member = member.split("-NR.")[0].strip()

        history = get_score_history(week, member)
        if not history:
            await interaction.response.send_message(
                f"❌ Không có lịch sử cho tuần {week}."
            )
            return

        msg = f"# 📊 LỊCH SỬ ĐIỂM - TUẦN {week}\n\n"
        for h in history[:20]:
            msg += (
                f"**{h['member']}** | {h['total']}/5 | "
                f"`{h['source']}` | {h['changed_at']}\n"
            )

        for part in reporter._split(msg):
            await interaction.response.send_message(part)

    @bot.tree.command(name="errors", description="[Admin] Xem lịch sử lỗi")
    @app_commands.describe(member="Tên member (bỏ trống = tất cả)")
    async def slash_errors(interaction: discord.Interaction, member: str = None):
        if not await check_admin(interaction):
            return

        if member:
            member_clean = member.split("-NR.")[0].strip()
            errors = error_tracker.get_member_errors(member_clean, weeks=8)
            patterns = error_tracker.get_error_patterns(member_clean)

            msg = f"# 🐛 LỊCH SỬ LỖI – {member_clean}\n\n"
            if not errors:
                msg += "Chưa có lỗi nào. 🎉\n"
            else:
                msg += f"**Tổng lỗi:** {len(errors)}\n"
                msg += f"**Lỗi lặp lại:** {'CÓ ⚠️' if patterns['has_repeated'] else 'Không ✅'}\n\n"

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
            await interaction.response.send_message(part)

    @bot.tree.command(name="tokens", description="[Admin] Xem token usage")
    async def slash_tokens(interaction: discord.Interaction):
        if not await check_admin(interaction):
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
        msg += f"- Đã dùng: **{stats['tokens_used']:,}**\n\n"

        msg += f"## 🗂️ Cache\n"
        msg += f"- Files: **{cstats['files']}**\n"

        await interaction.response.send_message(msg, ephemeral=True)

    @bot.tree.command(name="set-leader", description="[Admin] Set Leader tuần")
    @app_commands.describe(member="Tên member làm Leader")
    async def slash_set_leader(interaction: discord.Interaction, member: str):
        if not await check_admin(interaction):
            return

        access_control.set_weekly_leader(member)
        await interaction.response.send_message(
            f"✅ Đã set **{member}** làm Leader tuần."
        )

    @bot.tree.command(name="set-week", description="[Admin] Override tuần hiện tại")
    @app_commands.describe(week="Số tuần (1-72)")
    async def slash_set_week(interaction: discord.Interaction, week: int):
        if not await check_admin(interaction):
            return

        if week < 1 or week > 72:
            await interaction.response.send_message(
                "❌ Tuần phải trong khoảng 1-72.", ephemeral=True
            )
            return

        time_tracker.set_override_week(week)
        info = time_tracker.get_current_info()

        await interaction.response.send_message(
            f"✅ Đã set tuần = **{week}**\n"
            f"Mode: {info['mode']}"
        )

    # ============================================================
    # LEARNING COMMANDS
    # ============================================================

    @bot.tree.command(name="chat", description="Chat với bot")
    @app_commands.describe(message="Tin nhắn của bạn")
    async def slash_chat(interaction: discord.Interaction, message: str):
        if not await check_perm(interaction, "chat"):
            return

        await interaction.response.defer(thinking=True)

        user_id = interaction.user.id
        member = interaction.user.display_name
        role = access_control.get_role(interaction.user)

        try:
            result = await asyncio.to_thread(
                chat_bot.chat, user_id, member, message, role
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi: {e}")
            return

        if "error" in result:
            await interaction.followup.send(f"❌ {result['error']}")
            return

        role_icon = access_control.get_role_icon(role)
        embed = discord.Embed(
            title=f"💬 CHAT với {member}",
            description=result["reply"][:4000],
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"{role_icon} {role} • Tin nhắn #{result['session_message_count']}")

        await interaction.followup.send(embed=embed)

        insights = result.get("insights", [])
        if insights:
            insight_text = ""
            for ins in insights:
                type_label = chat_bot.INSIGHT_TYPES.get(ins["type"], "📝")
                insight_text += f"{type_label} {ins['content']}\n"

            insight_embed = discord.Embed(
                title="🧠 Insights",
                description=insight_text[:2000],
                color=discord.Color.purple(),
            )
            await interaction.followup.send(embed=insight_embed)

            if sheets is not None:
                try:
                    week = get_current_week()
                    for ins in insights:
                        await asyncio.to_thread(
                            sheets.sync_chat_insight,
                            week, member, role, ins["topic"],
                            ins["content"], ins["type"]
                        )
                except Exception as e:
                    print(f"[Slash chat] Sheets error: {e}")

    @bot.tree.command(name="socratic", description="Học bằng câu hỏi Socratic")
    @app_commands.describe(topic="Chủ đề muốn học")
    async def slash_socratic(interaction: discord.Interaction, topic: str):
        if not await check_perm(interaction, "socratic"):
            return

        await interaction.response.defer(thinking=True)

        user_id = interaction.user.id
        member = interaction.user.display_name

        try:
            result = await asyncio.to_thread(
                socratic_tutor.start_session, user_id, member, topic
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi: {e}")
            return

        embed = discord.Embed(
            title=f"🎓 SOCRATIC TUTOR – {topic.upper()}",
            description=f"**Câu {result['turn']}/{result['max_turns']}**",
            color=discord.Color.purple(),
        )
        embed.add_field(name="❓ Câu hỏi", value=result["question"], inline=False)
        embed.add_field(
            name="💡 Cách trả lời",
            value="Gõ `/answer <câu trả lời>`",
            inline=False,
        )

        await interaction.followup.send(embed=embed)

    @bot.tree.command(name="answer", description="Trả lời câu hỏi Socratic")
    @app_commands.describe(answer="Câu trả lời của bạn")
    async def slash_answer(interaction: discord.Interaction, answer: str):
        if not await check_perm(interaction, "socratic"):
            return

        await interaction.response.defer(thinking=True)

        result = await asyncio.to_thread(
            socratic_tutor.answer_question, interaction.user.id, answer
        )

        if "error" in result:
            await interaction.followup.send(f"❌ {result['error']}")
            return

        eval_embed = discord.Embed(
            title="📝 Đánh giá",
            description=result["evaluation"],
            color=discord.Color.blue(),
        )
        eval_embed.add_field(name="Điểm", value=f"{result['score']}/5", inline=True)
        await interaction.followup.send(embed=eval_embed)

        if result.get("is_completed"):
            # Final report sẽ gửi ở đây
            await interaction.followup.send("🎉 Session hoàn thành! Gõ `/socratic <topic>` để bắt đầu session mới.")
            return

        next_embed = discord.Embed(
            title=f"❓ Câu hỏi {result['turn']}/{result['max_turns']}",
            description=result["next_question"],
            color=discord.Color.purple(),
        )
        await interaction.followup.send(embed=next_embed)

    @bot.tree.command(name="quiz", description="Làm quiz trắc nghiệm")
    @app_commands.describe(topic="Chủ đề", num="Số câu (3-10)")
    @app_commands.choices(num=[
        app_commands.Choice(name="3 câu", value=3),
        app_commands.Choice(name="5 câu", value=5),
        app_commands.Choice(name="10 câu", value=10),
    ])
    async def slash_quiz(interaction: discord.Interaction, topic: str, num: app_commands.Choice[int] = None):
        if not await check_perm(interaction, "quiz"):
            return

        await interaction.response.defer(thinking=True)

        num_val = num.value if num else 5
        user_id = interaction.user.id
        member = interaction.user.display_name

        try:
            result = await asyncio.to_thread(
                practice_quiz.start_quiz, user_id, member, topic, num_val
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi: {e}")
            return

        if "error" in result:
            await interaction.followup.send(f"❌ {result['error']}")
            return

        difficulty_icon = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}.get(
            result.get("difficulty", "Medium"), "⚪"
        )

        embed = discord.Embed(
            title=f"📝 QUIZ – CÂU {result['index']}/{result['total']}",
            description=f"{difficulty_icon} **{result['question']}**\n\n{result['options']}",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="💡 Cách trả lời",
            value="Gõ `/quiz-answer <A/B/C/D>`",
            inline=False,
        )

        await interaction.followup.send(embed=embed)

    @bot.tree.command(name="quiz-answer", description="Trả lời câu hỏi quiz")
    @app_commands.describe(answer="Đáp án (A, B, C, hoặc D)")
    @app_commands.choices(answer=[
        app_commands.Choice(name="A", value="A"),
        app_commands.Choice(name="B", value="B"),
        app_commands.Choice(name="C", value="C"),
        app_commands.Choice(name="D", value="D"),
    ])
    async def slash_quiz_answer(interaction: discord.Interaction, answer: app_commands.Choice[str]):
        if not await check_perm(interaction, "quiz"):
            return

        await interaction.response.defer(thinking=True)

        result = await asyncio.to_thread(
            practice_quiz.answer_question, interaction.user.id, answer.value
        )

        if "error" in result:
            await interaction.followup.send(f"❌ {result['error']}")
            return

        if result["is_correct"]:
            embed = discord.Embed(
                title="✅ CHÍNH XÁC!",
                description=result.get("explanation", ""),
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="❌ SAI RỒI!",
                description=f"**Đáp án đúng:** `{result['correct_answer']}`\n\n{result.get('explanation', '')}",
                color=discord.Color.red(),
            )
        await interaction.followup.send(embed=embed)

        if result.get("is_completed"):
            await interaction.followup.send("🎉 Quiz hoàn thành! Gõ `/quiz <topic>` để làm quiz mới.")
            return

        next_q = result["next_question"]
        difficulty_icon = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}.get(
            next_q.get("difficulty", "Medium"), "⚪"
        )
        next_embed = discord.Embed(
            title=f"📝 QUIZ – CÂU {next_q['index']}/{next_q['total']}",
            description=f"{difficulty_icon} **{next_q['question']}**\n\n{next_q['options']}",
            color=discord.Color.blue(),
        )
        await interaction.followup.send(embed=next_embed)

    @bot.tree.command(name="predict", description="Dự đoán tiến bộ")
    @app_commands.describe(
        member="Tên member (bỏ trống = chính bạn)",
        weeks="Số tuần dự đoán (2-8)",
    )
    async def slash_predict(
        interaction: discord.Interaction,
        member: str = None,
        weeks: int = 4,
    ):
        if not await check_perm(interaction, "predict"):
            return

        await interaction.response.defer(thinking=True)

        if member is None:
            member = interaction.user.display_name

        member_clean = member.split("-NR.")[0].strip()

        try:
            result = await asyncio.to_thread(
                progress_predictor.predict, member_clean, weeks
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi: {e}")
            return

        if "error" in result:
            await interaction.followup.send(f"❌ {result['error']}")
            return

        embed = discord.Embed(
            title=f"🔮 DỰ ĐOÁN – {result['member'].upper()}",
            description=result["summary"].get("summary", ""),
            color=discord.Color.purple(),
        )

        embed.add_field(
            name="📊 Hiện tại",
            value=(
                f"• Điểm gần nhất: **{result['last_score']}/5**\n"
                f"• Xu hướng: {result['trend_icon']} **{result['trend_desc']}**\n"
                f"• Slope: **{result['slope']:+.3f}/tuần**"
            ),
            inline=False,
        )

        await interaction.followup.send(embed=embed)

    @bot.tree.command(name="my-mode", description="Xem tier và lộ trình của bạn")
    @app_commands.describe(member="Tên member (bỏ trống = chính bạn)")
    async def slash_my_mode(interaction: discord.Interaction, member: str = None):
        if not await check_perm(interaction, "advanced_mode"):
            return

        await interaction.response.defer(thinking=True)

        if member is None:
            member = interaction.user.display_name

        member_clean = member.split("-NR.")[0].strip()
        week = get_current_week()

        try:
            info = await asyncio.to_thread(
                advanced_mode.get_recommendations, member_clean, week
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi: {e}")
            return

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
            name="📊 Điểm TB",
            value=f"**{info['avg_score']}/5**",
            inline=True,
        )
        embed.add_field(
            name="📅 Roadmap",
            value=f"**{info['roadmap_mode']}**",
            inline=True,
        )

        if info.get("focus"):
            focus_text = "\n".join(f"• {f}" for f in info["focus"][:3])
            embed.add_field(name="🎯 Focus", value=focus_text[:500], inline=False)

        next_tier = info.get("next_tier", {})
        if next_tier and next_tier.get("next_tier"):
            progress = int(next_tier["progress_pct"] / 5)
            bar = "█" * progress + "░" * (20 - progress)
            embed.add_field(
                name=f"📈 Lên {next_tier['next_tier']}",
                value=f"`{bar}` **{next_tier['progress_pct']}%**\n+{next_tier['gap']} điểm",
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    # ============================================================
    # PLANNING COMMANDS
    # ============================================================

    @bot.tree.command(name="plan", description="[Leader] Xem kế hoạch tuần")
    @app_commands.describe(week="Tuần (bỏ trống = tuần hiện tại)")
    async def slash_plan(interaction: discord.Interaction, week: int = None):
        if not await check_perm(interaction, "plan"):
            return

        await interaction.response.defer(thinking=True)

        if week is None:
            week = get_current_week()

        info = time_tracker.get_current_info()
        mode = info["mode"]

        try:
            plan = await asyncio.to_thread(
                weekly_planner.generate_plan, week, mode
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi: {e}")
            return

        plan["week"] = week
        plan["mode"] = mode

        msg = weekly_planner.format_plan_for_discord(plan)
        for part in reporter._split(msg):
            await interaction.followup.send(part)

        if sheets is not None:
            try:
                await asyncio.to_thread(sheets.sync_plan, week, mode, plan)
            except Exception as e:
                print(f"[Slash plan] Sheets error: {e}")

    @bot.tree.command(name="notify", description="[Leader] Thông báo nhóm")
    @app_commands.describe(message="Nội dung thông báo")
    async def slash_notify(interaction: discord.Interaction, message: str):
        if not await check_perm(interaction, "notify"):
            return

        embed = discord.Embed(
            title="📢 THÔNG BÁO",
            description=message,
            color=discord.Color.gold(),
        )
        embed.set_footer(text=f"Từ {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="remind", description="[Leader] Nhắc nhở member")
    @app_commands.describe(
        member="Tên member",
        task="Việc cần nhắc",
    )
    async def slash_remind(interaction: discord.Interaction, member: str, task: str):
        if not await check_perm(interaction, "notify"):
            return

        member_clean = member.split("-NR.")[0].strip()

        embed = discord.Embed(
            title="🔔 NHẮC NHỞ",
            description=f"**{member_clean}**\n\n{task}",
            color=discord.Color.orange(),
        )
        embed.set_footer(text=f"Từ {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

    # ============================================================
    # HELP
    # ============================================================

    @bot.tree.command(name="help", description="Xem danh sách slash commands")
    async def slash_help(interaction: discord.Interaction):
        embed = discord.Embed(
            title="📚 COGNICRAFT BOT – SLASH COMMANDS",
            description="Gõ `/` để xem tất cả commands với auto-complete",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="📊 Info",
            value="`/week` `/mode` `/missing` `/ping` `/my-role`",
            inline=False,
        )
        embed.add_field(
            name="📚 Learning",
            value="`/socratic` `/answer` `/quiz` `/quiz-answer` `/chat` `/predict` `/my-mode`",
            inline=False,
        )
        embed.add_field(
            name="📋 Planning",
            value="`/plan` `/notify` `/remind`",
            inline=False,
        )
        embed.add_field(
            name="👑 Admin",
            value="`/confirm` `/override` `/trigger-scoring` `/trigger-report` `/history` `/errors` `/tokens` `/set-leader` `/set-week`",
            inline=False,
        )

        embed.set_footer(text="Gõ / để bắt đầu")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ============================================================
    # SYNC ON READY
    # ============================================================

        # ============================================================
    # SYNC FUNCTION (gọi từ bot.py on_ready)
    # ============================================================

    async def sync_slash_commands():
        """Sync slash commands (gọi từ bot.on_ready)"""
        import os
        guild_id = os.getenv("GUILD_ID")

        try:
            if guild_id:
                guild = discord.Object(id=int(guild_id))
                bot.tree.clear_commands(guild=guild)
                await bot.tree.sync(guild=guild)

                # Add tất cả commands vào guild
                bot.tree.copy_global_to(guild=guild)
                synced = await bot.tree.sync(guild=guild)
                print(f"[Slash] ✅ Synced {len(synced)} commands to guild {guild_id}")
            else:
                synced = await bot.tree.sync()
                print(f"[Slash] ✅ Synced {len(synced)} commands globally")
        except Exception as e:
            print(f"[Slash] ❌ Sync error: {e}")

    return sync_slash_commands