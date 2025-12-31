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
