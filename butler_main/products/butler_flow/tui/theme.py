from __future__ import annotations


FLOW_TUI_CSS = """
Screen {
    background: #0c0c0c;
    color: #d4d4d4;
}

#root {
    layout: vertical;
}

#composer {
    dock: bottom;
    layout: vertical;
    height: auto;
}

#body {
    height: 1fr;
    min-height: 0;
}

#flow-screen,
#setup-screen,
#history-screen,
#flows-screen,
#settings-screen {
    height: 1fr;
    width: 1fr;
    min-width: 0;
}

#flow-sidebar,
#setup-left,
#history-left,
#flows-left,
#settings-left {
    width: 42;
    min-width: 34;
    border: solid #2f2f2f;
    padding: 0 1;
}

#setup-right,
#history-right,
#flows-right,
#settings-right,
#inspector-panel {
    width: 1fr;
    min-width: 0;
    border: solid #2f2f2f;
    padding: 0 1;
}

#flow-console,
#transcript {
    width: 1fr;
    min-width: 0;
    border: none;
    padding: 0 1;
}

#flow-header,
#inspector-header,
#setup-header,
#history-header,
#flows-header,
#settings-status {
    min-height: 6;
    border-bottom: solid #2f2f2f;
    padding: 1;
    color: #d4d4d4;
}

#setup-list,
#history-list,
#flows-list,
#settings-list {
    height: 1fr;
    border-bottom: solid #2f2f2f;
    padding: 1;
}

#setup-detail,
#history-detail,
#flows-detail,
#settings-preview,
#inspector-body,
#setup-hint,
#history-hint,
#flows-hint,
#settings-hint {
    width: 100%;
    min-width: 100%;
    padding: 1;
    color: #d4d4d4;
}

#setup-header,
#history-header,
#flows-header {
    min-height: 6;
    color: #9cdcfe;
    background: #111111;
}

#flow-header,
#inspector-header {
    color: #9cdcfe;
    background: #111111;
}

#inspector-panel {
    display: none;
    width: 42;
    min-width: 34;
}

#action-bar {
    height: 2;
    padding: 0 1;
    color: #808080;
    width: 100%;
}

#command-input {
    height: 3;
    min-height: 3;
    max-height: 8;
    border-top: solid #2f2f2f;
    background: #0c0c0c;
    color: #d4d4d4;
    padding: 0 1;
    width: 100%;
}

#mention-picker {
    display: none;
    min-height: 0;
    max-height: 7;
    padding: 0 1;
    border-top: solid #2f2f2f;
    background: #111111;
    color: #d4d4d4;
    width: 100%;
}

.panel-title {
    color: #9cdcfe;
    text-style: bold;
}

.event-error {
    color: #f14c4c;
}

.event-warning {
    color: #cca700;
}

.event-system {
    color: #9cdcfe;
}

.event-judge {
    color: #4ec9b0;
}
"""
