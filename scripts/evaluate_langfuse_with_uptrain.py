from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langfuse import get_client
from uptrain import EvalLLM, Evals
from uptrain.framework.base import Settings


def _get_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = [_to_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in ("answer", "response", "question", "message", "content", "text"):
            if key in value and value[key]:
                return _to_text(value[key])
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _extract_message_text(messages: Any, role: str) -> str:
    if not isinstance(messages, list):
        return ""

    parts: list[str] = []
    for item in messages:
        if _get_value(item, "role") != role:
            continue
        text = _to_text(_get_value(item, "content"))
        if text:
            parts.append(text)
    return "\n".join(parts)


def _extract_reasoning_from_output(output_items: Any) -> str:
    if not isinstance(output_items, list):
        return ""

    parts: list[str] = []
    for item in output_items:
        reasoning = _to_text(_get_value(item, "reasoning_content"))
        if reasoning:
            parts.append(reasoning)
    return "\n".join(parts)


def _build_reasoning_prompt(payload: TraceEvaluationInput) -> str:
    return (
        "请判断下面这段推理说明，是否充分解释了最终答案是如何得出的。\n"
        f"用户问题: {payload.question}\n"
        f"最终答案: {payload.response}"
    )


@dataclass
class TraceEvaluationInput:
    trace_id: str
    trace_name: str
    session_id: str | None
    question: str
    response: str
    context: str
    reasoning: str
    latency_seconds: float | None
    total_cost_usd: float | None
    total_tokens: int | None
    html_path: str | None


def _extract_trace_input(trace: Any) -> TraceEvaluationInput:
    question = _to_text(_get_value(trace, "input"))
    response = _to_text(_get_value(trace, "output"))
    context = ""
    reasoning = ""
    total_tokens: int | None = None

    observations = _get_value(trace, "observations", []) or []
    for observation in observations:
        if _get_value(observation, "type") != "GENERATION":
            continue

        if not context:
            generation_input = _get_value(observation, "input")
            user_text = _extract_message_text(generation_input, "user")
            system_text = _extract_message_text(generation_input, "system")
            if user_text:
                question = user_text
            # This project is not a RAG pipeline; keep context empty unless there
            # is explicit non-system material. Avoid dumping the whole system prompt.
            if system_text and "context" in system_text.lower():
                context = system_text

        if not reasoning:
            reasoning = _extract_reasoning_from_output(_get_value(observation, "output"))

        if total_tokens is None:
            candidate_tokens = _get_value(observation, "total_tokens")
            if candidate_tokens is None:
                usage = _get_value(observation, "usage")
                candidate_tokens = _get_value(usage, "total")
            if candidate_tokens is not None:
                total_tokens = int(candidate_tokens)

    return TraceEvaluationInput(
        trace_id=_get_value(trace, "id", ""),
        trace_name=_get_value(trace, "name", ""),
        session_id=_get_value(trace, "session_id") or _get_value(trace, "sessionId"),
        question=question,
        response=response,
        context=context,
        reasoning=reasoning,
        latency_seconds=_get_value(trace, "latency"),
        total_cost_usd=_get_value(trace, "total_cost") or _get_value(trace, "totalCost"),
        total_tokens=total_tokens,
        html_path=_get_value(trace, "html_path") or _get_value(trace, "htmlPath"),
    )


def _build_uptrain() -> EvalLLM:
    api_base = os.getenv("UPTRAIN_API_BASE") or os.getenv("OPENAI_BASE_URL")
    model = os.getenv("UPTRAIN_EVAL_MODEL") or os.getenv("UPTRAIN_MODEL") or "deepseek-v4-flash"
    provider = os.getenv("UPTRAIN_LLM_PROVIDER", "openai")

    settings = Settings(
        model=model,
        api_base=api_base,
        custom_llm_provider=provider,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )
    return EvalLLM(settings=settings)


def _pick_checks(has_context: bool) -> list[Any]:
    checks = [Evals.RESPONSE_RELEVANCE, Evals.RESPONSE_COMPLETENESS]
    if has_context:
        checks.append(Evals.FACTUAL_ACCURACY)
    return checks


def _extract_score_payloads(result_row: dict[str, Any], prefix: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for key, value in result_row.items():
        if not key.startswith("score_") or value is None:
            continue

        metric_name = key.removeprefix("score_")
        explanation = result_row.get(f"explanation_{metric_name}")
        payloads.append(
            {
                "name": f"{prefix}_{metric_name}",
                "value": float(value),
                "comment": _to_text(explanation),
            }
        )
    return payloads


def _evaluate_with_uptrain(eval_llm: EvalLLM, payload: TraceEvaluationInput) -> dict[str, Any]:
    report: dict[str, Any] = {"trace": asdict(payload), "scores": []}

    answer_row = {
        "question": payload.question,
        "response": payload.response,
    }
    if payload.context:
        answer_row["context"] = payload.context

    answer_result = eval_llm.evaluate(
        data=[answer_row],
        checks=_pick_checks(bool(payload.context)),
    )[0]
    report["scores"].extend(_extract_score_payloads(answer_result, "uptrain_response"))

    if payload.reasoning:
        reasoning_row = {
            "question": _build_reasoning_prompt(payload),
            "response": payload.reasoning,
        }
        if payload.context:
            reasoning_row["context"] = payload.context

        reasoning_result = eval_llm.evaluate(
            data=[reasoning_row],
            checks=_pick_checks(bool(payload.context)),
        )[0]
        report["scores"].extend(_extract_score_payloads(reasoning_result, "uptrain_reasoning"))

    if payload.latency_seconds is not None:
        report["scores"].append(
            {
                "name": "trace_latency_seconds",
                "value": float(payload.latency_seconds),
                "comment": "Latency captured from Langfuse trace metrics.",
            }
        )
    if payload.total_cost_usd is not None:
        report["scores"].append(
            {
                "name": "trace_total_cost_usd",
                "value": float(payload.total_cost_usd),
                "comment": "Total cost captured from Langfuse trace metrics.",
            }
        )
    if payload.total_tokens is not None:
        report["scores"].append(
            {
                "name": "trace_total_tokens",
                "value": float(payload.total_tokens),
                "comment": "Total token usage captured from Langfuse generation metrics.",
            }
        )

    return report


def _write_scores(langfuse_client: Any, trace_id: str, score_payloads: list[dict[str, Any]]) -> None:
    for score in score_payloads:
        langfuse_client.create_score(
            name=score["name"],
            value=score["value"],
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=score["comment"][:4000],
        )
    langfuse_client.flush()


def _fetch_trace_ids(langfuse_client: Any, args: argparse.Namespace) -> list[str]:
    if args.trace_id:
        return args.trace_id

    traces = langfuse_client.api.trace.list(
        session_id=args.session_id,
        limit=args.limit,
        order_by="timestamp.desc",
        fields="all",
    )
    return [trace.id for trace in traces.data]


def _save_report(reports: list[dict[str, Any]]) -> Path:
    output_dir = Path("workspace") / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"uptrain_langfuse_eval_{timestamp}.json"
    path.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Langfuse traces with UpTrain.")
    parser.add_argument("--trace-id", action="append", help="Specific Langfuse trace id to evaluate. Can be repeated.")
    parser.add_argument("--session-id", help="Evaluate recent traces under this Langfuse session id.")
    parser.add_argument("--limit", type=int, default=5, help="How many recent traces to evaluate when trace ids are not provided.")
    parser.add_argument("--write-scores", action="store_true", help="Write evaluation scores back into Langfuse.")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    langfuse_client = get_client()
    if not langfuse_client.auth_check():
        raise SystemExit("Langfuse auth failed. Please verify LANGFUSE keys and host.")

    args = parse_args()
    trace_ids = _fetch_trace_ids(langfuse_client, args)
    if not trace_ids:
        raise SystemExit("No traces found to evaluate.")

    eval_llm = _build_uptrain()
    reports: list[dict[str, Any]] = []

    for trace_id in trace_ids:
        trace = langfuse_client.api.trace.get(trace_id=trace_id, fields="all")
        payload = _extract_trace_input(trace)
        report = _evaluate_with_uptrain(eval_llm, payload)
        if args.write_scores:
            _write_scores(langfuse_client, payload.trace_id, report["scores"])
        reports.append(report)

    report_path = _save_report(reports)
    print(json.dumps({"report_path": str(report_path), "trace_count": len(reports)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
