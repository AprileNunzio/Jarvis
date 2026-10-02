import random
import time
import uuid

import numpy as np

from features.study.constants import DEPTH_TOKENS, LEITNER_DAYS, LEVELS, LEVEL_HINT, PASS_MASTERY
from state import store


class StudyLessons:
    async def plan(self, topic: dict) -> None:
        lvl = topic["level"]
        previous = [x["title"] for n in range(1, lvl) for x in topic["levels"].get(str(n), {}).get("lessons", [])]
        count = max(3, min(12, int(self.settings["lessons_per_level"])))
        prompt = (f"Materia: {topic['name']}\nLivello: {LEVELS[lvl]} (per {LEVEL_HINT[lvl]})\n"
                  + (f"Preferenze dell'utente: {topic['focus']}\n" if topic.get("focus") else "")
                  + (f"Argomenti di cui l'utente parla spesso: {', '.join(topic['hints'][:10])}\n" if topic.get("hints") else "")
                  + (f"Lezioni già studiate (non ripeterle): {'; '.join(previous[-30:])}\n" if previous else "")
                  + f"\nCrea il programma di {count} lezioni in ordine progressivo, dal più semplice al più complesso. "
                    'Formato JSON: {"lezioni": [{"titolo": "titolo breve e specifico", "obiettivo": "cosa si impara"}]}')
        result = await self.llm_json("Sei un docente universitario esperto che progetta percorsi di studio in italiano. "
                                     "Rispondi solo in JSON.", prompt, 500)
        lessons = []
        for item in (result.get("lezioni") or [])[:count]:
            title = str(item.get("titolo", "")).strip()
            if title and title.lower() not in {x.lower() for x in previous}:
                lessons.append({"id": uuid.uuid4().hex[:10], "title": title[:100],
                                "goal": str(item.get("obiettivo", ""))[:200], "status": "todo", "questions": []})
        if not lessons:
            raise ValueError("programma vuoto")
        topic["levels"][str(lvl)] = {"lessons": lessons, "planned_at": time.time()}
        self.journal(f"{topic['name']}: programma del livello {LEVELS[lvl]} ({len(lessons)} lezioni)")
        self.save()

    async def lesson(self, topic: dict) -> None:
        lvl = topic["level"]
        level = topic["levels"][str(lvl)]
        lesson = next(x for x in level["lessons"] if x["status"] == "todo")
        self.publish("studying", f"Lezione: {lesson['title']}", topic)
        srcs = await self.sources(topic, lesson, lvl)
        remembered = ""
        if lesson.get("retry"):
            hits = await self.recall_cells(f"{lesson['title']} {topic['name']}", 4, topic=topic["id"])
            remembered = "\n".join(f"- {h['text']}" for h in hits)
        source_text = "\n\n".join(f"[Fonte: {s['title']} ({s['lang']})]\n{s['text']}" for s in srcs)
        prompt = (f"Materia: {topic['name']} — livello {LEVELS[lvl]} ({LEVEL_HINT[lvl]})\n"
                  f"Lezione: {lesson['title']}\nObiettivo: {lesson.get('goal', '')}\n"
                  + (f"Preferenze dell'utente: {topic['focus']}\n" if topic.get("focus") else "")
                  + (f"\nCiò che ricordi già:\n{remembered}\n" if remembered else "")
                  + (f"\nFONTI (usa solo informazioni coerenti con queste fonti):\n{source_text}\n" if source_text
                     else "\nNon hai fonti esterne: scrivi solo informazioni di cui sei certo.\n")
                  + "\nStudia la lezione e prepara i tuoi appunti in italiano. Non fermarti alla teoria: includi "
                    "sempre la PRATICA. Dove la materia lo consente usa formule e calcoli con numeri reali; "
                    "per le materie non numeriche usa procedure operative o esempi applicati, passo per passo. "
                    "Formato JSON:\n"
                    '{"sintesi": "spiegazione chiara in 4-6 frasi", '
                    '"fatti": ["concetto o fatto preciso e autonomo (con formule, valori, esempi)", "..."], '
                    '"esercizi": [{"testo": "problema o procedura pratica da svolgere", '
                    '"soluzione": "soluzione svolta passo per passo, con formule o passaggi"}], '
                    '"domande": [{"d": "domanda di verifica", "r": "risposta corretta e breve"}]}\n'
                    "Scrivi da 5 a 8 fatti, da 2 a 4 esercizi con soluzione e 3 domande.")
        notes = await self.llm_json("Sei uno studente modello: prendi appunti precisi, verificabili e senza "
                                    "invenzioni, e ti alleni con esercizi pratici. Rispondi solo in JSON.", prompt,
                                    DEPTH_TOKENS.get(self.settings["depth"], 700))
        summary = str(notes.get("sintesi", "")).strip()
        facts = [str(f).strip() for f in (notes.get("fatti") or []) if len(str(f).strip()) > 15][:10]
        exercises = [{"q": str(e.get("testo", "")).strip(), "a": str(e.get("soluzione", "")).strip()}
                     for e in (notes.get("esercizi") or []) if isinstance(e, dict) and e.get("testo") and e.get("soluzione")][:4]
        questions = [{"q": str(q.get("d", "")).strip(), "a": str(q.get("r", "")).strip()}
                     for q in (notes.get("domande") or []) if isinstance(q, dict) and q.get("d") and q.get("r")][:5]
        if not summary and not facts:
            raise ValueError("appunti vuoti")

        texts = (([f"{lesson['title']}: {summary}"] if summary else []) + facts
                 + [f"Esercizio: {e['q']} Soluzione: {e['a']}" for e in exercises]
                 + [f"{q['q']} {q['a']}" for q in questions])
        kinds = (["summary"] if summary else []) + ["fact"] * len(facts) + ["exercise"] * len(exercises) + ["qa"] * len(questions)
        vectors = await self.embed(texts)
        source_url = srcs[0]["url"] if srcs else ""
        new_cells = 0
        for text, kind, vec in zip(texts, kinds, vectors):
            _, fresh = self.memory.add(f"{topic['id']}:{uuid.uuid4().hex[:12]}", np.asarray(vec, dtype=np.float32),
                                       text[:700], topic=topic["id"], topic_name=topic["name"], level=lvl,
                                       lesson=lesson["id"], kind=kind, source=source_url)
            new_cells += fresh
        now = time.time()
        lesson.update(status="done", studied_at=now, summary=summary, facts=facts, exercises=exercises, cells=new_cells,
                      sources=[{"title": s["title"], "url": s["url"]} for s in srcs], retry=False,
                      questions=[{**q, "box": 0, "due": now + LEITNER_DAYS[0] * 86400, "last_score": None,
                                  "history": []} for q in questions] or lesson.get("questions", []))
        topic["last_studied"] = now
        self.data["stats"]["lessons"] += 1
        self.journal(f"{topic['name']} · {lesson['title']}: {len(facts)} fatti, {len(exercises)} esercizi, {new_cells} nuove celle")
        self.save()
        if self.on_neuron:
            await self.on_neuron(topic, lesson, self.overview(topic))

    async def _answer(self, topic: dict, q: dict) -> float:
        hits = await self.recall_cells(q["q"], 4, topic=topic["id"])
        context = "\n".join(f"- {h['text']}" for h in hits) or "(nessun ricordo)"
        result = await self.llm_json("Rispondi a una domanda di verifica usando i tuoi appunti. "
                                     "Rispondi solo in JSON.",
                                     f"Appunti:\n{context}\n\nDomanda: {q['q']}\n"
                                     'Formato: {"risposta": "risposta breve e precisa"}', 160)
        answer = str(result.get("risposta", "")).strip()
        if not answer:
            return 0.0
        va, vr = await self.embed([answer, q["a"]])
        va, vr = np.asarray(va), np.asarray(vr)
        cos = float(va @ vr / (np.linalg.norm(va) * np.linalg.norm(vr) + 1e-9))
        return round(max(0.0, min(1.0, (cos - 0.55) / 0.35)), 3)

    def _grade(self, q: dict, score: float) -> None:
        q["last_score"] = score
        q["history"] = (q.get("history", []) + [round(score, 2)])[-8:]
        q["box"] = min(len(LEITNER_DAYS) - 1, q.get("box", 0) + 1) if score >= 0.6 else 0
        q["due"] = time.time() + LEITNER_DAYS[q["box"]] * 86400

    async def review(self, topic: dict) -> None:
        due = [(lv, q) for lv in topic["levels"].values() for q in self._questions(lv) if q.get("due", 0) <= time.time()]
        random.shuffle(due)
        for _, q in due[:5]:
            self._grade(q, await self._answer(topic, q))
            self.data["stats"]["reviews"] += 1
        topic["last_studied"] = time.time()
        m = self.mastery(topic, topic["level"])
        self.journal(f"{topic['name']}: ripasso di {min(5, len(due))} domande"
                     + (f", padronanza {m * 100:.0f}%" if m is not None else ""))
        self.save()

    async def exam(self, topic: dict) -> None:
        lvl = topic["level"]
        level = topic["levels"][str(lvl)]
        pool = [(lesson, q) for lesson in level["lessons"] for q in lesson.get("questions", [])]
        sample = random.sample(pool, min(8, len(pool)))
        per_lesson: dict = {}
        for lesson, q in sample:
            score = await self._answer(topic, q)
            self._grade(q, score)
            per_lesson.setdefault(lesson["id"], []).append(score)
        scores = [s for v in per_lesson.values() for s in v]
        result = sum(scores) / len(scores) if scores else 0.0
        level.setdefault("exams", []).append({"at": time.time(), "score": round(result, 3)})
        self.data["stats"]["exams"] += 1
        topic["last_studied"] = time.time()
        if result >= PASS_MASTERY or not pool:
            level["passed_at"] = time.time()
            self.journal(f"🎓 {topic['name']}: superato il livello {LEVELS[lvl]} ({result * 100:.0f}%)")
            store.event("INFO", f"Studio: {topic['name']} — livello {LEVELS[lvl]} superato ({result * 100:.0f}%)", "study")
            if lvl >= topic["target_level"]:
                topic["level"] = lvl + 1 if lvl < 5 else 5
                topic["status"] = "done"
            else:
                topic["level"] = lvl + 1
        else:
            weak = sorted(per_lesson.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))[:max(1, len(per_lesson) // 2)]
            for lesson in level["lessons"]:
                if lesson["id"] in dict(weak):
                    lesson.update(status="todo", retry=True)
            self.journal(f"{topic['name']}: esame {LEVELS[lvl]} al {result * 100:.0f}%, ristudio {len(weak)} lezioni")
        self.save()
        if self.on_neuron:
            await self.on_neuron(topic, None, self.overview(topic))
