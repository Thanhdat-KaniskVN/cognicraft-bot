class KnowledgeBar:
    BAR_LENGTH = 15
    FULL = "█"
    EMPTY = "░"

    def __init__(self, roadmap):
        self.roadmap = roadmap

    def render(self, coverage):
        lines = []
        lines.append("📊 **KNOWLEDGE BAR**")
        lines.append("")

        total_covered = 0
        total_topics = 0

        for phase in self.roadmap["phases"]:
            # Kiểm tra phase có topic nào được cover không
            phase_data = []
            phase_total = 0
            phase_count = 0

            for topic in phase["topics"]:
                tid = topic["id"]
                cov = coverage.get(tid, {})
                pct = cov.get("covered", 0)
                score = cov.get("score", 0)

                phase_data.append({
                    "name": topic["name"],
                    "pct": pct,
                    "score": score,
                })

                phase_total += pct
                phase_count += 1
                total_covered += pct
                total_topics += 1

            phase_avg = phase_total / phase_count if phase_count else 0

            # Chỉ hiển thị phase có ít nhất 1 topic > 0%
            has_data = any(d["pct"] > 0 for d in phase_data)

            if has_data:
                # Header phase có data
                lines.append(
                    f"**🎯 Phase {phase['id']}: {phase['name']}** — "
                    f"`{phase_avg:.0f}%`"
                )

                for d in phase_data:
                    if d["pct"] > 0:
                        emoji = self._status_emoji(d["pct"])
                        bar = self._draw_bar(d["pct"])
                        lines.append(
                            f"{emoji} `{bar}` **{d['pct']:>3}%** "
                            f"· {d['name']} · *{d['score']}/5*"
                        )

                lines.append("")
            else:
                # Phase trống – hiển thị 1 dòng gộp
                lines.append(
                    f"💤 **Phase {phase['id']}: {phase['name']}** "
                    f"— *chưa bắt đầu* ({phase_count} topics)"
                )
                lines.append("")

        # Tổng kết
        avg = total_covered / total_topics if total_topics else 0
        overall_emoji = self._status_emoji(avg)

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(
            f"{overall_emoji} **TỔNG: {avg:.1f}%** "
            f"({self._count_active(coverage)}/{total_topics} topics đã chạm)"
        )

        return "\n".join(lines)

    def _draw_bar(self, pct):
        """Vẽ bar với block đầy/rỗng rõ ràng"""
        filled = int(self.BAR_LENGTH * pct / 100)
        return self.FULL * filled + self.EMPTY * (self.BAR_LENGTH - filled)

    def _status_emoji(self, pct):
        """Chọn emoji theo % coverage"""
        if pct >= 80:
            return "🟢"
        elif pct >= 50:
            return "🟡"
        elif pct > 0:
            return "🟠"
        else:
            return "⚪"

    def _count_active(self, coverage):
        """Đếm số topic có coverage > 0"""
        return sum(1 for c in coverage.values() if c.get("covered", 0) > 0)