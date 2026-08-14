"""One-off analysis: measured word-to-token ratio per language on the real
corpus, using the same tokenizer the pipeline embeds with. Backs the numbers
in docs/TOKENIZATION.md -- run again and paste fresh output if the corpus or
embedding model changes.
"""
from __future__ import annotations

import glob
import json
import statistics

from transformers import AutoTokenizer

from src.rag.lang import detect_language

TOKENIZER_NAME = "intfloat/multilingual-e5-small"


def main() -> None:
    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_NAME)
    by_lang: dict[str, list[tuple[int, int]]] = {"ar": [], "en": [], "mixed": []}

    for path in sorted(glob.glob("data/sample/*.md")):
        text = open(path, encoding="utf-8").read()
        lang = detect_language(text)
        words = len(text.split())
        tokens = len(tokenizer.encode(text, add_special_tokens=False))
        by_lang[lang].append((words, tokens))

    print(f"{'lang':<8}{'docs':<6}{'total_words':<14}{'total_tokens':<14}{'tokens/word':<14}")
    summary = {}
    for lang, pairs in by_lang.items():
        if not pairs:
            continue
        total_words = sum(w for w, _ in pairs)
        total_tokens = sum(t for _, t in pairs)
        ratio = total_tokens / total_words
        per_doc_ratios = [t / w for w, t in pairs if w]
        summary[lang] = {
            "docs": len(pairs),
            "total_words": total_words,
            "total_tokens": total_tokens,
            "tokens_per_word": round(ratio, 3),
            "median_tokens_per_word": round(statistics.median(per_doc_ratios), 3),
        }
        print(f"{lang:<8}{len(pairs):<6}{total_words:<14}{total_tokens:<14}{ratio:<14.3f}")

    if summary.get("ar") and summary.get("en"):
        density = summary["ar"]["tokens_per_word"] / summary["en"]["tokens_per_word"]
        summary["ar_vs_en_density_ratio"] = round(density, 2)
        print(f"\nArabic tokenizes {density:.2f}x denser than English (tokens/word)")

    with open("docs/tokenization_measurements.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
