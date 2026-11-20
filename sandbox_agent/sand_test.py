"""Run the independent Docker agent: python -m sandbox_agent.sand_test."""
import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from deepagents import create_deep_agent
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from .docker_backend import DockerSandbox
from .task_context import TaskContextMiddleware, refine_task, update_task_record

EXPERIMENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EXPERIMENT_DIR.parent


def run_task(model, backend, user_prompt, record, record_path):
    agent = create_deep_agent(
        model=model,
        system_prompt=(EXPERIMENT_DIR / "prompts/coding.md").read_text(),
        backend=backend,
        tools=[update_task_record],
        middleware=[TaskContextMiddleware()],
    )
    for mode, chunk in agent.stream(
        {"messages": [{"role": "user", "content": user_prompt}], "task_record": record},
        stream_mode=["messages", "updates", "values"],
    ):
        if mode == "values":
            if "task_record" in chunk:
                save_record(record_path, chunk["task_record"])
        elif mode == "messages":
            message, metadata = chunk
            for block in message.content_blocks:
                if block["type"] == "text":
                    print(block["text"], end="", flush=True)
        elif mode == "updates":
            for update in chunk.values():
                if not isinstance(update, dict):
                    continue
                for message in update.get("messages", []):
                    for call in getattr(message, "tool_calls", []):
                        print(f"\n[Tool call: {call['name']}] {json.dumps(call['args'], ensure_ascii=False)}", flush=True)
                    if message.type == "tool":
                        print(f"\n[Tool result: {message.name or message.tool_call_id}]\n{message.content}", flush=True)
    print(flush=True)


def save_record(path, record):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="?", help="Task to perform; asks for input if omitted")
    args = parser.parse_args()
    user_prompt = args.prompt if args.prompt is not None else input("Task: ")
    if not user_prompt.strip():
        parser.error("Task prompt cannot be empty")
    load_dotenv(PROJECT_DIR / ".env")
    model = ChatOpenAI(
        base_url=os.getenv("CAMPUSAI_API_URL"),
        model=os.getenv("CAMPUSAI_MODEL"),
        api_key=os.getenv("CAMPUSAI_API_KEY"),
    )
    print("Refining the task...", flush=True)
    record = refine_task(model, user_prompt)
    print(json.dumps(record, ensure_ascii=False, indent=2), flush=True)
    runs = EXPERIMENT_DIR / "runs"
    runs.mkdir(exist_ok=True)
    record_path = runs / f"{uuid4().hex}.json"
    save_record(record_path, record)
    print(f"Task record: {record_path}", flush=True)
    # Refinement must succeed before we allocate a Docker container.
    with DockerSandbox(EXPERIMENT_DIR / "sandbox_workspace") as backend:
        run_task(model, backend, user_prompt, record, record_path)


if __name__ == "__main__":
    main()
