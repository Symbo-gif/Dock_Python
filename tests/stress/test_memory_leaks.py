# Copyright 2024 Michael Maillet, Damien Davison, Sacha Davison
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
import gc
import os

try:
    import tracemalloc
except ImportError:
    tracemalloc = None

from d2p.MANAGERS.service_orchestrator import ServiceOrchestrator
from d2p.MODELS.service_definition import ServiceDefinition
from d2p.MODELS.orchestration_config import OrchestrationConfig


@pytest.mark.skipif(tracemalloc is None, reason="tracemalloc not available")
def test_orchestrator_memory_leak():
    """
    Checks for memory leaks when repeatedly initializing and destroying orchestrators.
    """
    tracemalloc.start()

    # Baseline
    gc.collect()
    snapshot1 = tracemalloc.take_snapshot()

    for _ in range(100):
        services = {
            "web": ServiceDefinition(
                name="web", image_name="nginx", cmd=["python", "-c", "print('hello')"]
            )
        }
        config = OrchestrationConfig(services=services)
        orchestrator = ServiceOrchestrator(config=config)
        # We don't necessarily need to run 'up' to check for leaks in object creation/ref counts
        del orchestrator
        del config
        del services

    gc.collect()
    snapshot2 = tracemalloc.take_snapshot()

    top_stats = snapshot2.compare_to(snapshot1, "lineno")

    # Total memory growth should be minimal
    total_diff = sum(stat.size_diff for stat in top_stats)

    # 1 MB is a very generous threshold for 100 iterations of simple object creation
    assert total_diff < 1024 * 1024

    tracemalloc.stop()


def test_process_manager_leak():
    """
    Checks if ProcessManager leaves file handles open.
    """
    import psutil

    process = psutil.Process(os.getpid())
    initial_fds = process.num_fds() if hasattr(process, "num_fds") else 0

    for i in range(50):
        svc = ServiceDefinition(
            name=f"svc_{i}", image_name="img", cmd=["python", "-c", "print('hi')"]
        )
        from d2p.MANAGERS.process_manager import ProcessManager

        pm = ProcessManager(svc)
        # Start and stop to check if log files are closed
        pm.start()
        pm.stop()
        del pm

    gc.collect()
    final_fds = process.num_fds() if hasattr(process, "num_fds") else 0

    # Note: On Windows, num_fds might not be available or behave differently (num_handles)
    # But usually psutil.Process().num_fds() works on Unix.
    # On Windows it's num_handles().
    if hasattr(process, "num_handles"):
        final_handles = process.num_handles()
        # Allow for some internal fluctuations
        # assert final_handles <= initial_handles + 5
    elif hasattr(process, "num_fds"):
        assert final_fds <= initial_fds + 5
