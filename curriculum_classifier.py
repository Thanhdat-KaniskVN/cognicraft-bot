# curriculum_classifier.py
"""Curriculum Classifier - classify content -> week chinh xac."""
import json
import os
from typing import Optional
from datetime import datetime


class CurriculumClassifier:
    CONFIDENCE_THRESHOLD = 0.5
    WEIGHT_KEYWORD_MATCH = 1.0

    def __init__(self, roadmap_path: str = "roadmap.json"):
        self.roadmap_path = roadmap_path
        self.roadmap = self._load_roadmap()
        self._build_keyword_index()

    def _load_roadmap(self) -> dict:
        if not os.path.exists(self.roadmap_path):
            raise FileNotFoundError(f"Khong tim thay roadmap: {self.roadmap_path}")
        with open(self.roadmap_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[Classifier] Loaded roadmap v{data.get('version', '?')} "
              f"({data.get('total_weeks', '?')} weeks, "
              f"{len(data.get('phases', []))} phases)")
        return data

    def _build_keyword_index(self):
        self.keyword_index = {}
        self.topic_index = {}
        self.week_index = {}
        for phase in self.roadmap.get("phases", []):
            for topic in phase.get("topics", []):
                tid = topic.get("id", "")
                self.topic_index[tid] = {**topic, "phase_id": phase.get("id", 0), "phase_name": phase.get("name", "")}
                for week in topic.get("expected_weeks", []):
                    self.week_index.setdefault(week, []).append({"topic": topic, "phase": phase})
                for kw in topic.get("keywords", []):
                    k = kw.lower().strip()
                    self.keyword_index.setdefault(k, []).append({"topic": topic, "phase": phase, "weight": self.WEIGHT_KEYWORD_MATCH})

    def _extract_keywords(self, content: str) -> list:
        if not content:
            return []
        text = content.lower()
        return list({kw for kw in self.keyword_index if kw in text})

    def classify(self, content: str, thread_week: int = None) -> dict:
        if not content:
            return self._fallback(thread_week, "empty_content")
        kws = self._extract_keywords(content)
        if not kws:
            return self._fallback(thread_week, "no_keywords")
        tscores = {}
        for kw in kws:
            for e in self.keyword_index.get(kw, []):
                tid = e["topic"]["id"]
                tscores.setdefault(tid, {"score": 0, "keywords": [], "topic": e["topic"], "phase": e["phase"]})
                tscores[tid]["score"] += e["weight"]
                tscores[tid]["keywords"].append(kw)
        if not tscores:
            return self._fallback(thread_week, "no_topic_match")
        best_id = max(tscores, key=lambda k: tscores[k]["score"])
        best = tscores[best_id]
        total = sum(t["score"] for t in tscores.values())
        conf = best["score"] / total if total else 0
        ews = best["topic"].get("expected_weeks", [])
        if not ews:
            return self._fallback(thread_week, "no_expected_weeks")
        if len(ews) == 1:
            week = ews[0]
        else:
            week = thread_week if (thread_week and thread_week in ews) else ews[0]
        if conf >= self.CONFIDENCE_THRESHOLD:
            method = "ai_classify"
        elif thread_week:
            method = "thread_fallback"
            week = thread_week
        else:
            method = "low_confidence"
        return {
            "week": week,
            "confidence": round(conf, 3),
            "topic_id": best_id,
            "topic_name": best["topic"].get("name", ""),
            "phase_id": best["phase"].get("id", 0),
            "phase_name": best["phase"].get("name", ""),
            "method": method,
            "keywords_found": kws[:20],
            "thread_week": thread_week,
            "classified_at": datetime.now().isoformat(),
        }

    def _fallback(self, thread_week, reason):
        return {"week": thread_week or 0, "confidence": 0.0, "topic_id": None,
                "topic_name": None, "phase_id": None, "phase_name": None,
                "method": "fallback", "fallback_reason": reason,
                "keywords_found": [], "thread_week": thread_week,
                "classified_at": datetime.now().isoformat()}

    def get_topic_for_week(self, week):
        es = self.week_index.get(week, [])
        if not es:
            return None
        return {"week": week, "topic": es[0]["topic"], "phase": es[0]["phase"]}

    def debug_info(self):
        return {"roadmap_version": self.roadmap.get("version", "?"),
                "total_weeks": self.roadmap.get("total_weeks", "?"),
                "total_phases": len(self.roadmap.get("phases", [])),
                "total_topics": len(self.topic_index),
                "total_keywords": len(self.keyword_index),
                "weeks_with_topics": len(self.week_index),
                "confidence_threshold": self.CONFIDENCE_THRESHOLD}


if __name__ == "__main__":
    print("=" * 60)
    print("CURRICULUM CLASSIFIER TEST")
    print("=" * 60)
    c = CurriculumClassifier("roadmap.json")
    for k, v in c.debug_info().items():
        print(f"  {k}: {v}")
    print()
    tests = [
        ("Python co ban", "Em hoc ve bien, vong lap for va while trong Python.", 5),
        ("Calculus", "Em hoc ve gioi han, dao ham, chain rule, implicit differentiation.", 11),
        ("Induction", "Bai nay em chung minh bang quy nap. Base case n=1 dung.", 2),
        ("Khong ro", "Hom nay em hoc duoc nhieu thu hay ho.", 5),
    ]
    for name, content, tw in tests:
        r = c.classify(content, thread_week=tw)
        print(f"[{name}] Thread W{tw} -> W{r['week']} | conf={r['confidence']} | {r['method']} | {r['topic_name']}")