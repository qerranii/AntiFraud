from types import SimpleNamespace


def evaluate_dsl(expression: str, context: dict) -> bool:
    try:
        if "user" in context and isinstance(context["user"], dict):
            context["user"] = SimpleNamespace(**context["user"])

        clean_expression = expression.strip()

        result = eval(clean_expression, {"__builtins__": {}}, context)

        return bool(result)
    except Exception as e:
        print(f"DSL Eval Error: {e} | Expression: {expression}")
        return False