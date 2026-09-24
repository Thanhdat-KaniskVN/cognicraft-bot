# reporter.py
from config import DISCORD_MSG_LIMIT


class Reporter:
    def generate(self, week, submissions, missing,
                 week_scores, agg, coverage, kb, participation=None):
        report = f"# BAO CAO TUAN {week}\n\n"

        # === PARTICIPATION ===
        report += "## THAM GIA\n"
        total = len(participation) if participation else 5
        report += f"- Da nop: **{len(submissions)}/{total}**\n"
        if missing:
            report += f"- Chua nop: {', '.join(missing)}\n"
        report += "\n"

        # === DIEM 4 TIEU CHI ===
        if week_scores:
            report += "## DIEM 4 TIEU CHI\n"
            report += "| Thanh vien | Chinh xac | Do sau | Lien ket | Trinh bay | Tong |\n"
            report += "|------------|-----------|--------|----------|-----------|------|\n"
            for s in week_scores:
                report += (
                    f"| {s['member']} | {s['accuracy']} | {s['depth']} | "
                    f"{s['connection']} | {s['presentation']} | "
                    f"**{s['total']}** |\n"
                )

            report += f"\n**Trung binh nhom:** {agg['average']}/5\n"
            report += f"- Chinh xac: {agg['by_criteria']['accuracy']}/5\n"
            report += f"- Do sau: {agg['by_criteria']['depth']}/5\n"
            report += f"- Lien ket: {agg['by_criteria']['connection']}/5\n"
            report += f"- Trinh bay: {agg['by_criteria']['presentation']}/5\n\n"

            # === SELF-SCORE COMPARISON ===
            rows = []
            for s in week_scores:
                self_score = s.get("self_score")
                real_score = s.get("total", 0)

                if self_score is None:
                    continue

                diff = self_score - real_score

                if abs(diff) < 0.3:
                    flag = "(OK)"
                elif diff >= 1.0:
                    flag = "(!) OVERCONF"
                elif diff <= -1.0:
                    flag = "(?) UNDERCONF"
                elif diff > 0:
                    flag = "(~) +"
                else:
                    flag = "(~) -"

                rows.append([
                    s["member"],
                    f"{self_score:.1f}/5",
                    f"{real_score:.1f}/5",
                    f"{flag} {diff:+.2f}",
                ])

            # ✅ FIX: Ghi rows vào report
            if rows:
                report += "## SELF-SCORE vs REVIEWER\n"
                report += "| Thanh vien | Tu danh gia | Diem that | Chenh lech |\n"
                report += "|------------|-------------|-----------|------------|\n"
                for r in rows:
                    report += f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |\n"
                report += "\n"

        # === KNOWLEDGE BAR ===
        report += "## KNOWLEDGE BAR\n"
        report += kb + "\n\n"

        # === NHAN XET ===
        if coverage.get("summary"):
            report += f"## NHAN XET\n{coverage['summary']}\n"

        return self._split(report)

    def _split(self, text):
        if len(text) <= DISCORD_MSG_LIMIT:
            return [text]

        parts = []
        current = ""
        for line in text.split("\n"):
            if len(current) + len(line) + 1 > DISCORD_MSG_LIMIT:
                parts.append(current)
                current = line
            else:
                current += "\n" + line if current else line
        if current:
            parts.append(current)
        return parts