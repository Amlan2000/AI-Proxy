#!/bin/zsh

# -- Set proxy only for this session --
export HTTPS_PROXY="http://127.0.0.1:8080"

# -- Check if at least one argument is provided --
if [ -z "$1" ]; then
    echo "Usage: $0 <application> [additional args...]"
    echo "Supported applications: code, code-insiders, cursor"
    exit 1
fi

APP=$1
shift

case "${APP:l}" in
    "code")
        TITLE="VS Code Explorer"
        # We use single quotes here to prevent Zsh from interpreting the '!' character
        FILTER='~u githubcopilot.com & !~u githubcopilot.com/telemetry'
        ;;
    "code-insiders")
        TITLE="VS Code Insiders Explorer"
        FILTER='~u githubcopilot.com & !~u githubcopilot.com/telemetry'
        ;;
    "cursor")
        TITLE="Cursor Explorer"
        FILTER='~u api2.cursor.sh/aiserver'
        ;;
    *)
        echo "Unsupported application: $APP"
        exit 1
        ;;
esac

ARGS="$@"

# Launch the app in background
# 'nohup' keeps it running if you close this terminal window
nohup $APP $ARGS >/dev/null 2>&1 &

echo "Launched $APP with arguments \"$ARGS\""
echo "Starting mitmproxy with filter: $FILTER"

# -- FIXED APPLE-SCRIPT SECTION --
# Using a Here-Doc (EOF) avoids the quote-nesting errors
osascript <<EOF
tell application "Terminal"
    do script "mitmproxy --view-filter '$FILTER'"
    activate
end tell
EOF