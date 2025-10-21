---
applyTo: '*.py'
---

# 🧠 GitHub Copilot Coding Instructions

## 1. Package Management — Use `uv`

All dependencies must be managed through [`uv`](https://docs.astral.sh/uv/), not `pip` or `poetry`.

### ✅ Installing a Package

```bash
uv add <package-name>
```

Example:

```bash
uv add pydantic
```

### ✅ Running a Python File

```bash
uv run python <file_name>.py
```

Example:

```bash
uv run python main.py
```

---

## 2. Coding Rules

When writing code, **follow these strict rules**:

* 🔹 **Use Python 3.11+** syntax and best practices.
* 🔹 **Use [Pydantic v2](https://docs.pydantic.dev/latest/)** for all data validation and models.
* 🔹 **Simplicity over everything** — write clean, readable, and minimal code.
* 🔹 **No unnecessary abstractions** — avoid over-engineering, inheritance, or extra files unless requested.
* 🔹 **Follow only what is said** — do **not** assume extra requirements or add unrequested helpers, comments, or examples.
* 🔹 **Ask for clarification** if instructions are incomplete or ambiguous before proceeding.
* 🔹 **Do not generate summaries, explanations, or print outputs** unless explicitly asked.

---

## 3. Pydantic Usage Example

Always use **Pydantic v2** models for data validation:

```python
from pydantic import BaseModel, Field

class User(BaseModel):
    id: int
    name: str = Field(..., min_length=1)
    email: str

# Example usage
user = User(id=1, name="Marian", email="test@example.com")
print(user.model_dump())
```

---

## 4. Do Not:

* ❌ Use `pip install`, `venv`, or `poetry`.
* ❌ Add comments explaining what the code does (unless asked).
* ❌ Add tests, docs, or configs unless requested.
* ❌ Summarize or restate what was done after completion.

---

## 5. Summary

Copilot should:

> “Write only the requested Python code, keep it simple, use `uv` for packages, and rely on `pydantic v2` for validation — nothing more, nothing less.”

!!! DO NOT CREATE SUMMARY OR EXPLANATION AFTER THE CODE.