"""Health Risk Prediction API.

A standalone REST service (separate process from the web app) that screens
blood test values against standard adult reference ranges and returns a
possible condition / risk level.

    POST /predict   {"age": 35, "glucose": 110, "haemoglobin": 13.5, "cholesterol": 210}
    GET  /health    service status

This is a rule-based screening tool, not a diagnostic device.
"""
import os

import requests
from flask import Flask, jsonify, request

api = Flask(__name__)

# Optional external AI model. Set ANTHROPIC_API_KEY in your environment (never in
# the code or on GitHub) to get AI-written remarks. Without it, or if the call
# fails, the rule-based result below is used.
AI_KEY = os.environ.get("ANTHROPIC_API_KEY")
AI_MODEL = os.environ.get("AI_MODEL", "claude-haiku-5-5")
AI_URL = "https://api.anthropic.com/v1/messages"

# Points added to the overall risk score for each abnormal finding.
SEVERITY = {"mild": 1, "moderate": 2, "high": 3}


def assess_glucose(v):
    """Fasting plasma glucose, mg/dL."""
    if v < 54:
        return "high", "Severely low glucose", "Hypoglycaemia (urgent review advised)"
    if v < 70:
        return "moderate", "Low glucose", "Hypoglycaemia (low glucose)"
    if v < 100:
        return None
    if v < 126:
        return "mild", "Elevated glucose", "Prediabetes (impaired fasting glucose)"
    if v < 200:
        return "moderate", "High glucose", "Type 2 diabetes range (confirm with HbA1c)"
    return "high", "Very high glucose", "Probable diabetes mellitus (needs prompt testing)"


def assess_haemoglobin(v):
    """Haemoglobin, g/dL (adult reference 12.0 - 17.5)."""
    if v < 8:
        return "high", "Severely low haemoglobin", "Severe anaemia"
    if v < 10:
        return "moderate", "Low haemoglobin", "Moderate anaemia"
    if v < 12:
        return "mild", "Slightly low haemoglobin", "Mild anaemia"
    if v <= 17.5:
        return None
    if v <= 18.5:
        return "mild", "Slightly high haemoglobin", "Possible dehydration"
    return "moderate", "High haemoglobin", "Possible polycythaemia or dehydration"


def assess_cholesterol(v):
    """Total cholesterol, mg/dL."""
    if v < 200:
        return None
    if v < 240:
        return "mild", "Borderline high cholesterol", "Borderline hypercholesterolaemia"
    if v < 300:
        return "moderate", "High cholesterol", "Hypercholesterolaemia (raised cardiovascular risk)"
    return "high", "Very high cholesterol", "Severe hypercholesterolaemia (high cardiovascular risk)"


def predict(age, glucose, haemoglobin, cholesterol):
    checks = [
        assess_glucose(glucose),
        assess_haemoglobin(haemoglobin),
        assess_cholesterol(cholesterol),
    ]
    findings = [c for c in checks if c]
    score = sum(SEVERITY[c[0]] for c in findings)

    # Age increases the weight of metabolic and cardiovascular findings.
    if age >= 45 and any(c is checks[0] or c is checks[2] for c in findings):
        score += 1

    if not findings:
        level = "Low"
    elif score <= 2:
        level = "Moderate" if score == 2 else "Low"
    elif score <= 4:
        level = "Moderate"
    else:
        level = "High"
    if any(c[0] == "high" for c in findings):
        level = "High"

    conditions = [c[2] for c in findings]
    if not findings:
        remarks = "Low risk. All values are within normal adult ranges."
    else:
        remarks = (
            f"{level} risk. " + "; ".join(c[1] for c in findings) + ". "
            + "Possible: " + "; ".join(conditions) + ". "
            + "Screening result only; confirm with a clinician."
        )
    return {
        "risk_level": level,
        "risk_score": score,
        "findings": [c[1] for c in findings],
        "possible_conditions": conditions,
        "remarks": remarks,
    }


def ai_remarks(age, glucose, haemoglobin, cholesterol, rule_result):
    """Ask an external AI model for a short remark. Returns None on any failure."""
    key = os.environ.get("ANTHROPIC_API_KEY", AI_KEY)
    if not key:
        return None
    prompt = (
        "You are a health screening assistant. A patient aged "
        f"{age} has fasting glucose {glucose} mg/dL, haemoglobin {haemoglobin} g/dL "
        f"and total cholesterol {cholesterol} mg/dL. A rule-based check found: "
        f"{'; '.join(rule_result['findings']) or 'no abnormal values'}. "
        "Reply in at most two short sentences: state the risk level (Low, Moderate "
        "or High) and the possible condition(s), and say to confirm with a clinician. "
        "Do not give a diagnosis."
    )
    try:
        resp = requests.post(
            AI_URL,
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": AI_MODEL, "max_tokens": 200,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"].strip() or None
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return None


@api.get("/health")
def health():
    return jsonify(status="ok", ai_enabled=bool(os.environ.get("ANTHROPIC_API_KEY", AI_KEY)))


@api.post("/predict")
def predict_route():
    body = request.get_json(silent=True) or {}
    try:
        values = {k: float(body[k]) for k in ("age", "glucose", "haemoglobin", "cholesterol")}
    except (KeyError, TypeError, ValueError):
        return jsonify(error="age, glucose, haemoglobin and cholesterol are required numbers"), 400
    if not 0 <= values["age"] <= 120:
        return jsonify(error="age must be between 0 and 120"), 400
    result = predict(**values)
    ai_text = ai_remarks(values["age"], values["glucose"], values["haemoglobin"],
                         values["cholesterol"], result)
    result["source"] = "ai" if ai_text else "rules"
    if ai_text:
        result["remarks"] = ai_text
    return jsonify(result)


if __name__ == "__main__":
    api.run(host="127.0.0.1", port=5001)
