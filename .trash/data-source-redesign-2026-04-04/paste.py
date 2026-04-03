#!/usr/bin/env python3
"""
Automate Paste to Construct 3 for macOS
Usage: python3 automate_paste.py <json_file_path> [--paste]
"""

import sys
import subprocess
import os
import time

def copy_to_clipboard(text):
    """Copy text to macOS clipboard using pbcopy"""
    process = subprocess.Popen(
        'pbcopy', env={'LANG': 'en_US.UTF-8'}, stdin=subprocess.PIPE
    )
    process.communicate(text.encode('utf-8'))

def activate_chrome_and_paste():
    """Use AppleScript to activate Chrome and simulate Cmd+V"""
    script = '''
    tell application "Google Chrome"
        activate
    end tell
    delay 0.5
    tell application "System Events"
        keystroke "v" using command down
    end tell
    '''
    subprocess.run(['osascript', '-e', script])

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 automate_paste.py <json_file_path> [--paste]")
        sys.exit(1)

    file_path = sys.argv[1]
    auto_paste = "--paste" in sys.argv

    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        sys.exit(1)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 1. Copy to clipboard
        copy_to_clipboard(content)
        print(f"✅ Copied {file_path} to system clipboard!")

        # 2. Auto paste if requested
        if auto_paste:
            print("🚀 Switching to Chrome and pasting in 1 second...")
            time.sleep(1) # Give user a moment to see the message
            activate_chrome_and_paste()
            print("✨ Paste command sent.")
        else:
            print("💡 Tip: Add --paste to automatically switch to Chrome and paste.")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
