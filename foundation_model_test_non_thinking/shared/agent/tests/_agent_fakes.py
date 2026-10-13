"""Offline whole-module loader shared by agent characterization tests."""
import importlib.util
from pathlib import Path
import sys
import types

CUSTOM = Path(__file__).resolve().parents[1] / "gpustack_custom"


def load_runner(monkeypatch, base):
    """Load the complete production module, substituting only external bench dependencies."""
    def install(name, **attrs):
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, mod)

    class Registry:
        def get_available_tools(self):
            return []

    class Adapter:
        def __init__(self, *args, **kwargs):
            (base / 'adapter_created').touch()
            self.unparsed_tool_call_candidates = 0
            self.timeout = 1
            self.max_tokens = 16
            self.openai_sdk_version = 'fixture'
            self.sdk_max_retries = 0

    class Runner:
        def __init__(self, *args, **kwargs):
            self.timeout = kwargs['timeout']
            self.max_retries = kwargs['max_retries']

        def run_task(self, task):
            (base / 'evaluated').touch()
            return {'success': True, 'execution_time': 0, 'steps_taken': 0, 'tool_invocations': []}

    install('dotenv', load_dotenv=lambda: None)  # Never open a real .env.
    install('bench.tools.tool_registry', ToolRegistry=Registry)
    install('bench.adapters.openai_compat_adapter', OpenAICompatAdapter=Adapter)
    install('bench.runner', BenchmarkRunner=Runner)
    install('bench.tools.base_api', BaseTool=object)
    install('bench.models', MODEL_IDS=[])
    install('bench.tools.tool_catalog', resolve_tool_classes=lambda _: [], TOOL_CATALOG={})
    install('bench.config', set_cache_mode=lambda _: None)
    install('configs.secrets', **{key: '' for key in (
        'AZURE_API_KEY', 'AZURE_API_BASE', 'AZURE_API_VERSION', 'ANTHROPIC_API_KEY',
        'GEMINI_API_KEY', 'OPENROUTER_API_KEY', 'OPENROUTER_APP_URL', 'OPENROUTER_APP_TITLE')})
    monkeypatch.syspath_prepend(str(CUSTOM))
    spec = importlib.util.spec_from_file_location('results_runner_fixture', CUSTOM / 'run_gpustack_benchmark_with_logging.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.load_benchmark_datasets = lambda _: {'L1': [{'task_id': 'fixture', 'instruction': 'fixture', 'level': 'L1'}]}
    return module

