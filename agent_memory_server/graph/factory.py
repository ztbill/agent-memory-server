import logging

from agent_memory_server.config import settings
from agent_memory_server.graph.base import MemoryGraph


logger = logging.getLogger(__name__)

_memory_graph: MemoryGraph | None = None


def _import_and_call_factory(factory_path: str):
    import importlib

    module_path, function_name = factory_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    factory_function = getattr(module, function_name)
    return factory_function()


def create_redisgraph_memory() -> MemoryGraph:
    from agent_memory_server.graph.impls.redisgraph import RedisGraphMemory

    return RedisGraphMemory(settings.redis_url)


def create_networkx_memory() -> MemoryGraph:
    from agent_memory_server.graph.impls.networkx import NetworkXGraphMemory

    return NetworkXGraphMemory()


def create_falkordb_memory() -> MemoryGraph:
    from agent_memory_server.graph.impls.falkordb import FalkorDBMemory

    return FalkorDBMemory(host=settings.falkordb_host, port=settings.falkordb_port)


def create_memory_graph() -> MemoryGraph:
    factory_path = settings.memory_graph_factory
    logger.info(f"Creating memory graph using factory: {factory_path}")
    return _import_and_call_factory(factory_path)


async def get_memory_graph() -> MemoryGraph:
    global _memory_graph
    if _memory_graph is None:
        _memory_graph = create_memory_graph()
    return _memory_graph
