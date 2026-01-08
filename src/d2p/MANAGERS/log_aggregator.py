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

"""
Log aggregation and tailing for services.
"""
import time
import os
from typing import Dict, List


class LogAggregator:
    """
    Aggregates and tails logs from multiple service log files.
    """

    def __init__(self, log_dir: str):
        """
        Initializes the log aggregator.

        :param log_dir: The directory where log files are stored.
        """
        self.log_dir = log_dir

    def tail_logs(self, service_names: List[str]):
        """
        Tails logs for the specified services and prints them to stdout.

        :param service_names: Names of the services to tail.
        """
        files = {}
        print(f"Tailing logs for: {', '.join(service_names)}")

        try:
            while True:
                for name in service_names:
                    if name not in files:
                        path = os.path.join(self.log_dir, f"{name}.log")
                        if os.path.exists(path):
                            f = open(path, "r")
                            f.seek(0, os.SEEK_END)
                            files[name] = f

                    if name in files:
                        line = files[name].readline()
                        if line:
                            print(f"{name:15} | {line.strip()}")

                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nStopping log tailing...")
        finally:
            for f in files.values():
                f.close()
