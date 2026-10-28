"""Create an evaluation-only source tree; never modify the full project."""
import ast
import hashlib
import json
import sys
from pathlib import Path

class StripDocs(ast.NodeTransformer):
    def visit_Module(self, node):
        self.generic_visit(node)
        node.body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
        return node
    def visit_ClassDef(self, node):
        self.generic_visit(node)
        node.body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
        return node
    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        node.body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
        if not node.body:
            node.body = [ast.Pass()]
        return node

def prepare(source, destination):
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if destination == source or source in destination.parents:
        raise ValueError("Output must be separate from the complete source tree")
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise ValueError("Use an empty output directory")
    def read(relative):
        return ast.parse((source / relative).read_text(encoding="utf-8-sig"))
    def write(relative, tree):
        tree = StripDocs().visit(tree)
        ast.fix_missing_locations(tree)
        text = ast.unparse(tree) + "\n"
        compile(text, relative, "exec")
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    def module(imports, nodes):
        return ast.Module(body=ast.parse(imports).body + nodes, type_ignores=[])
    def classes(relative, keep):
        result = []
        for n in read(relative).body:
            if isinstance(n, ast.ClassDef) and n.name in keep:
                methods = keep[n.name]
                if methods is not None:
                    n.body = [m for m in n.body if isinstance(m, ast.FunctionDef) and m.name in methods]
                result.append(n)
        assert len(result) == len(keep), relative
        return result
    def selected(relative, names):
        result = [n for n in read(relative).body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
        assert len(result) == len(names), relative
        return result
    def method(cls, name):
        return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)

    for relative in ["__init__.py", "components/__init__.py", "learners/__init__.py", "utils/__init__.py"]:
        write(relative, module("", []))
    write("agents/__init__.py", ast.parse('from .rnn_agent import RNNAgent\nREGISTRY = {"rnn": RNNAgent}'))
    write("controllers/__init__.py", ast.parse('from .basic_controller import BasicMAC\nREGISTRY = {"basic_mac": BasicMAC}'))
    write("runners/__init__.py", ast.parse('from .episode_runner import EpisodeRunner\nREGISTRY = {"episode_runner": EpisodeRunner}'))

    agent_nodes = classes("agents/rnn_agent.py", {"RNNAgent": {"__init__", "forward", "init_hidden"}, "FeatureLayer": None, "Head": None})
    init = method(agent_nodes[0], "__init__")
    init.body = [n for n in init.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) and n.value.func.attr == "_init_heads_mutually_orthogonal")]
    write("agents/rnn_agent.py", module("import torch\nimport torch.nn as nn\nimport torch.nn.functional as F\nfrom collections import OrderedDict", agent_nodes))
    write("agents/adapter.py", module("import torch\nimport torch.nn as nn\nimport math", classes("agents/adapter.py", {"Adapter": None})))

    episode = classes("components/episode_buffer.py", {"EpisodeBatch": {"__init__", "_setup_data", "update", "_check_safe_view", "__getitem__", "_parse_slices"}})[0]
    method(episode, "__getitem__").body = ast.parse(
        'if isinstance(item, str):\n'
        '    if item in self.data.episode_data:\n'
        '        return self.data.episode_data[item]\n'
        '    if item in self.data.transition_data:\n'
        '        return self.data.transition_data[item]\n'
        '    raise ValueError(item)\n'
        'raise TypeError("Evaluation batches support field lookup only")\n'
    ).body
    write("components/episode_buffer.py", module("import torch as th\nimport numpy as np\nfrom types import SimpleNamespace as SN", [episode]))
    write("components/transforms.py", module("import torch as th", classes("components/transforms.py", {"Transform": None, "OneHot": None})))
    write("components/action_selectors.py", module("import torch as th\nfrom torch.distributions import Categorical\nfrom .epsilon_schedules import DecayThenFlatSchedule", classes("components/action_selectors.py", {"EpsilonGreedyActionSelector": None})))
    write("components/epsilon_schedules.py", module("import numpy as np", classes("components/epsilon_schedules.py", {"DecayThenFlatSchedule": None})))

    mac = classes("controllers/basic_controller.py", {"BasicMAC": {"__init__", "_build_agents", "select_actions", "forward", "init_hidden", "_build_inputs", "_get_input_shape"}})[0]
    init = method(mac, "__init__")
    init.body = [n for n in init.body if "self.global_relation_capture" not in ast.unparse(n)]
    write("controllers/basic_controller.py", module("import torch\nfrom src.agents import REGISTRY as agent_REGISTRY\nfrom src.components.action_selectors import EpsilonGreedyActionSelector\nfrom utils.sc2_decomposer import SC2Decomposer", [mac]))

    env_fn = selected("envs/__init__.py", {"env_fn"})[0]
    write("envs/__init__.py", module("from functools import partial\nfrom smac.env import StarCraft2Env", [env_fn] + ast.parse('REGISTRY = {"sc2": partial(env_fn, env=StarCraft2Env)}').body))
    dec = classes("utils/sc2_decomposer.py", {"SC2Decomposer": {"__init__", "get_obs_size", "get_state_size", "decompose_obs", "decompose_action_info"}})
    write("utils/sc2_decomposer.py", module("from smac.env.starcraft2.maps import get_map_params\nimport torch as th\nimport numpy as np", dec))

    adapter = classes("learners/adapter_learner.py", {"AdapterLearner": {"__init__", "load_models", "bulid_pre_input"}})[0]
    original_init = method(adapter, "__init__")
    assignments = {ast.unparse(n.targets[0]): n for n in original_init.body if isinstance(n, ast.Assign)}
    calls = {ast.unparse(n.value.func): n for n in original_init.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)}
    original_init.body = [assignments[name] if name in assignments else calls[name] for name in [
        "self.args", "self.mac", "self.env_name", "self.adapter", "self.adapter.to",
        "self.task2decomposer", "self.surrogate_decomposer", "self.pre_input_model", "self.pre_input_model.to"
    ]]
    load = method(adapter, "load_models")
    load.body = [n for n in load.body if "self.target_adapter" not in ast.unparse(n)]
    write("learners/adapter_learner.py", module("import torch\nimport torch.nn as nn\nfrom src.agents.adapter import Adapter", [adapter]))

    runner = classes("runners/episode_runner.py", {"EpisodeRunner": {"__init__", "setup", "close_env", "reset", "run", "get_agent_role", "get_env_info"}})[0]
    class RemoveTrainingHooks(ast.NodeTransformer):
        def visit_Assign(self, n):
            if any(ast.unparse(t) in {"new_params", "adapter_learner.new_head_params"} for t in n.targets):
                return None
            return self.generic_visit(n)
        def visit_Expr(self, n):
            text = ast.unparse(n)
            if text.startswith("adapter_learner.optim.") or text.startswith("adapter_learner.params."):
                return None
            return self.generic_visit(n)
    runner = RemoveTrainingHooks().visit(runner)
    method(runner, "run").decorator_list = [ast.parse("torch.no_grad()").body[0].value]
    write("runners/episode_runner.py", module("import torch\nfrom functools import partial\nfrom collections import Counter\nfrom components.episode_buffer import EpisodeBatch\nfrom envs import REGISTRY as env_REGISTRY", [runner]))

    evaluate = read("evaluate3.py")
    test_model = next(n for n in evaluate.body if isinstance(n, ast.FunctionDef) and n.name == "test_model")
    class EvaluationOnly(ast.NodeTransformer):
        def visit_Name(self, n):
            if n.id == "ReplayBuffer":
                n.id = "EpisodeBatch"
            return n
        def visit_Assign(self, n):
            if any(isinstance(t, ast.Name) and t.id in {"learner", "task_learner", "local_agent_relations"} for t in n.targets):
                return None
            return self.generic_visit(n)
        def visit_Expr(self, n):
            if ast.unparse(n).startswith("learner."):
                return None
            return self.generic_visit(n)
    test_model = EvaluationOnly().visit(test_model)
    test_model.decorator_list = [ast.parse("torch.no_grad()").body[0].value]
    for n in test_model.body:
        if isinstance(n, ast.For) and any(isinstance(t, ast.Name) and t.id == "task_id" for t in ast.walk(n.target)) and any(isinstance(s, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "success_num" for t in s.targets) for s in n.body):
            n.body.insert(0, ast.parse('print(f"Evaluating {task_id + 1}/{len(env_name)}: {task_name}", flush=True)').body[0])
    for index, n in enumerate(test_model.body):
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and ast.unparse(n.value.func) == "np.save":
            test_model.body.insert(index, ast.parse('os.makedirs(os.path.join(args["ckpt_folder"], "success_rate"), exist_ok=True)').body[0])
            break
    preamble = ast.parse(
        'import os\nimport sys\nimport copy\nimport numpy as np\nimport torch\n'
        'os.environ.setdefault("PWD", os.getcwd())\n'
        '_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
        'if _project_root not in sys.path:\n    sys.path.insert(0, _project_root)\n'
        'from runners import REGISTRY as r_REGISTRY\n'
        'from controllers import REGISTRY as mac_REGISTRY\n'
        'from components.transforms import OneHot\n'
        'from components.episode_buffer import EpisodeBatch\n'
        'from learners.adapter_learner import AdapterLearner\n'
        'torch.set_num_threads(max(1, int(os.environ.get("LACMC_TORCH_THREADS", "2"))))\n'
    ).body
    write("evaluate3.py", ast.Module(body=preamble + [test_model] + ast.parse('if __name__ == "__main__":\n    test_model()').body, type_ignores=[]))

    records = []
    for path in sorted(destination.rglob("*")):
        if path.is_file():
            records.append({"path": path.relative_to(destination).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size})
    return records

if __name__ == "__main__":
    records = prepare(sys.argv[1], sys.argv[2])
    print(json.dumps(records, indent=2))
