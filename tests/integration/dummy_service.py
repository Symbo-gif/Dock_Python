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

import os
import time
import sys


def main():
    print("Dummy service starting...")
    print(f"DEBUG: {os.environ.get('DEBUG')}")
    print(f"APP_ENV: {os.environ.get('APP_ENV')}")

    # Simulate work
    for i in range(5):
        print(f"Working... {i}")
        time.sleep(1)

    print("Dummy service finishing.")


if __name__ == "__main__":
    main()
