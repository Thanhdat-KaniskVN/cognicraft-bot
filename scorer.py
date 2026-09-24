from config import SCORE_WEIGHTS


class Scorer:
    def calculate_total(self, scores):
        return round(sum(
            scores.get(c, 0) * w
            for c, w in SCORE_WEIGHTS.items()
        ), 2)

    def aggregate_week(self, week_scores):
        if not week_scores:
            return {
                'average': 0,
                'by_criteria': {c: 0 for c in SCORE_WEIGHTS},
                'count': 0,
            }

        criteria_sums = {c: 0 for c in SCORE_WEIGHTS}
        total_sum = 0

        for row in week_scores:
            for c in SCORE_WEIGHTS:
                criteria_sums[c] += row.get(c, 0)
            total_sum += row.get('total', 0)

        n = len(week_scores)
        return {
            'average': round(total_sum / n, 2),
            'by_criteria': {
                c: round(criteria_sums[c] / n, 2)
                for c in SCORE_WEIGHTS
            },
            'count': n,
        }
