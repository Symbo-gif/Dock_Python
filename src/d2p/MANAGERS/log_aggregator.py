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
                            f = open(path, 'r')
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
