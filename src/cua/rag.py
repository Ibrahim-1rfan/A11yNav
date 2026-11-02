"""Local retrieval over the curated platform guides in knowledge/<platform>/*.md.

Keyword ranking (BM25) always works offline. When an embedding model is configured, semantic
ranking is fused in with reciprocal rank fusion. Guide text is reference data only.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

APPS = {"edge": ("edge", "microsoft edge"), "chrome": ("chrome", "google chrome"), "firefox": ("firefox", "mozilla")}
SOURCE_HOSTS = {"edge": "microsoft.com", "chrome": "google.com", "firefox": "mozilla.org"}
STOPWORDS = set("""a an and are as at be by can could do does for from get go how i if in into is it its me my of on
or please should so that the then there this to turn use using want way what when where which while who why will with
would you your help browser page pages website websites web site sites one""".split())


@dataclass(frozen=True)
class Chunk:
    id: str
    platform: str
    app: str
    title: str
    text: str
    keywords: tuple[str, ...]
    sources: tuple[str, ...]
    task: str = ""

    @property
    def source(self):
        host = SOURCE_HOSTS.get(self.app, "")
        return next((s for s in self.sources if (urlsplit(s).hostname or "").endswith(host)), self.sources[0] if self.sources else "")

    @property
    def steps(self):
        return tuple(re.sub(r"^\s*\d+[.)]\s*", "", line).strip() for line in self.text.splitlines() if line.strip())


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float
    matched: bool


def knowledge_root() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / "knowledge"


def _front_matter(text):
    meta, body = {}, text
    if text.startswith("---"):
        head, _, body = text[3:].partition("\n---")
        key = None
        for line in head.splitlines():
            if line.strip().startswith("- ") and key:
                meta.setdefault(key, []).append(line.strip()[2:].strip())
            elif ":" in line:
                key, value = (part.strip() for part in line.split(":", 1))
                meta[key] = value if value else []
    return meta, body


def load_corpus(root: Path | None = None) -> list[Chunk]:
    root = root or knowledge_root()
    chunks = []
    for path in sorted(root.glob("*/*.md")):
        meta, body = _front_matter(path.read_text(encoding="utf-8"))
        keywords = tuple(k.strip() for k in str(meta.get("keywords", "")).split(",") if k.strip())
        sources = tuple(meta.get("sources") or ())
        for section in re.split(r"(?m)^## ", body)[1:]:
            heading, _, text = section.partition("\n")
            app = heading.strip().lower()
            if text.strip():
                chunks.append(Chunk(f"{path.parent.name}/{path.stem}#{app}", path.parent.name, app,
                                    meta.get("title", path.stem), text.strip(), keywords, sources, str(meta.get("task", ""))))
    return chunks


def tokens(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words if w not in STOPWORDS]


def detect_app(question):
    text = question.lower()
    return next((app for app, names in APPS.items() if any(re.search(rf"\b{n}\b", text) for n in names)), None)


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs = [tokens(d) for d in docs]
        self.k1, self.b = k1, b
        self.avg = sum(map(len, self.docs)) / max(1, len(self.docs))
        self.df = {}
        for doc in self.docs:
            for term in set(doc):
                self.df[term] = self.df.get(term, 0) + 1

    def scores(self, query):
        terms, n = set(tokens(query)), len(self.docs)
        out = []
        for doc in self.docs:
            score = 0.0
            for term in terms:
                tf = doc.count(term)
                if tf:
                    idf = math.log(1 + (n - self.df[term] + .5) / (self.df[term] + .5))
                    score += idf * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * len(doc) / self.avg))
            out.append(score)
        return out


def cosine(a, b):
    na, nb = math.sqrt(sum(x*x for x in a)), math.sqrt(sum(y*y for y in b))
    return sum(x*y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def fuse(rankings, k=60):
    """Reciprocal rank fusion of several ranked index lists."""
    fused = {}
    for ranking in rankings:
        for rank, index in enumerate(ranking):
            fused[index] = fused.get(index, 0.0) + 1 / (k + rank + 1)
    return sorted(fused, key=lambda i: -fused[i])


class Index:
    def __init__(self, chunks, embed=None, cache_dir: Path | None = None, embed_threshold=0.6, embed_model=""):
        self.chunks = list(chunks)
        # Title and keywords are repeated so they weigh more than body wording.
        self.bm25 = BM25([f"{c.title} {c.title} {' '.join(c.keywords)} {' '.join(c.keywords)} {c.app} {c.text}" for c in self.chunks])
        self.embed, self.cache_dir, self.embed_threshold, self.embed_model = embed, cache_dir, embed_threshold, embed_model
        self.vectors = None

    def _chunk_vectors(self, stop):
        if self.vectors is None:
            texts = [f"{c.title}. {c.app}. {c.text}" for c in self.chunks]
            digest = hashlib.sha256(json.dumps([self.embed_model, texts]).encode()).hexdigest()[:24]
            path = self.cache_dir / f"{digest}.json" if self.cache_dir else None
            try:
                self.vectors = json.loads(path.read_text(encoding="utf-8")) if path and path.exists() else None
            except (OSError, ValueError):
                self.vectors = None
            if not isinstance(self.vectors, list) or len(self.vectors) != len(texts):
                self.vectors = self.embed(texts, stop)
                if path:
                    try:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(json.dumps(self.vectors), encoding="utf-8")
                    except OSError:
                        pass
        return self.vectors

    def retrieve(self, question, app=None, k=3, stop=None):
        app = app or detect_app(question)
        allowed = [i for i, c in enumerate(self.chunks) if not app or c.app == app]
        keyword = self.bm25.scores(question)
        matched = {i for i in allowed if keyword[i] > 0}
        rankings = [sorted(allowed, key=lambda i: -keyword[i])]
        if self.embed:
            from .models import Cancelled
            try:
                vectors = self._chunk_vectors(stop)
                query = self.embed([question], stop)[0]
                semantic = {i: cosine(query, vectors[i]) for i in allowed}
                rankings.append(sorted(allowed, key=lambda i: -semantic[i]))
                matched |= {i for i in allowed if semantic[i] >= self.embed_threshold}
            except Cancelled:
                raise
            except Exception:
                pass  # Embeddings are an enhancement; keyword retrieval still answers.
        order = fuse(rankings) if len(rankings) > 1 else rankings[0]
        return [Hit(self.chunks[i], keyword[i], i in matched) for i in order if i in matched][:k]
