"""
Phase 11 — Evaluation question set.

25 questions, each with a known "correct" drug and section (matched by
keyword, not exact title — see eval_metrics.py for why). Covers a mix
of drugs and question categories (dosage, contraindications, warnings,
pregnancy, side effects, drug interactions, overdose) so the results
aren't skewed by one category being easy or hard.

Expected section keywords are based on standard FDA SPL section names,
which are consistent across most drug labels even when the exact
title wording differs (e.g. numbered vs. unnumbered, "Directions" vs.
"Dosage and Administration").
"""

from eval_metrics import EvalQuestion

EVAL_QUESTIONS = [
    # --- Dosage / directions ---
    EvalQuestion("what is the max daily dose of ibuprofen?", "Ibuprofen", ["direction", "dosage"]),
    EvalQuestion("how much metformin should I take?", "Metformin", ["dosage", "direction"]),
    EvalQuestion("what is the recommended dose of amoxicillin?", "Amoxicillin", ["dosage", "direction"]),
    EvalQuestion("how often should I take sertraline?", "Sertraline", ["dosage", "direction"]),
    EvalQuestion("what is the starting dose of lisinopril?", "Lisinopril", ["dosage", "direction"]),
    EvalQuestion("how much acetaminophen is safe to take?", "Acetaminophen", ["dosage", "direction"]),

    # --- Contraindications ---
    EvalQuestion("who should not take metformin?", "Metformin", ["contraindication"]),
    EvalQuestion("who should not use ibuprofen?", "Ibuprofen", ["contraindication", "warning", "ask a doctor"]),
    EvalQuestion("is warfarin safe for everyone?", "Warfarin", ["contraindication"]),

    # --- Warnings ---
    EvalQuestion("what are the warnings for ibuprofen?", "Ibuprofen", ["warning"]),
    EvalQuestion("can metformin cause lactic acidosis?", "Metformin", ["lactic acidosis", "warning"]),
    EvalQuestion("what is the stomach bleeding risk with naproxen?", "Naproxen", ["stomach bleeding", "warning"]),

    # --- Pregnancy ---
    EvalQuestion("is ibuprofen safe during pregnancy?", "Ibuprofen", ["pregnan"]),
    EvalQuestion("can I take sertraline while pregnant?", "Sertraline", ["pregnan"]),
    EvalQuestion("is lisinopril safe during pregnancy?", "Lisinopril", ["pregnan"]),

    # --- Side effects / adverse reactions ---
    EvalQuestion("what are the side effects of metformin?", "Metformin", ["adverse", "side effect"]),
    EvalQuestion("what are common side effects of sertraline?", "Sertraline", ["adverse", "side effect"]),
    EvalQuestion("what side effects does amoxicillin cause?", "Amoxicillin", ["adverse", "side effect"]),
    EvalQuestion("what are the side effects of lisinopril?", "Lisinopril", ["adverse", "side effect"]),

    # --- Drug interactions ---
    EvalQuestion("does metformin interact with other drugs?", "Metformin", ["interaction"]),
    EvalQuestion("what drugs interact with warfarin?", "Warfarin", ["interaction"]),

    # --- Overdose ---
    EvalQuestion("what happens if I take too much metformin?", "Metformin", ["overdose"]),
    EvalQuestion("what should I do if I take too much acetaminophen?", "Acetaminophen", ["overdose"]),

    # --- Missed dose / administration ---
    EvalQuestion("what should I do if I miss a dose of ciprofloxacin?", "Ciprofloxacin", ["missed dose", "dosage"]),

    # --- Storage ---
    EvalQuestion("how should ibuprofen be stored?", "Ibuprofen", ["storage", "how supplied"]),
]
