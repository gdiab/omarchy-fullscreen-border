import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland

Item {
  id: root
  property color cueColor: "#829dd4"
  property int cueWidth: 3

  FileView {
    path: Quickshell.env("HOME") + "/.local/state/omarchy/fullscreen-border.json"
    watchChanges: true
    onFileChanged: reload()
    onLoaded: {
      try {
        var data = JSON.parse(text())
        if (/^#[0-9a-fA-F]{6}$/.test(data.color)) root.cueColor = data.color
        root.cueWidth = Math.max(2, Math.min(6, Number(data.width) || 3))
      } catch (error) { console.warn("Fullscreen Border: invalid color file", error) }
    }
  }

  function fullWindow(monitor) {
    if (!monitor || !monitor.activeWorkspace) return null
    // A scratchpad in front should not inherit the underlying workspace cue.
    var special = monitor.lastIpcObject.specialWorkspace
    if (special && special.id !== 0) return null
    var windows = monitor.activeWorkspace.toplevels.values
    // The screensaver covers the desktop, not an ordinary app. Check all
    // windows first: a fullscreen app underneath may appear earlier in IPC.
    for (var i = 0; i < windows.length; i++) {
      var candidate = windows[i].lastIpcObject
      if ((candidate.class === "org.omarchy.screensaver" || candidate.initialClass === "org.omarchy.screensaver")
          && candidate.mapped !== false && candidate.hidden !== true)
        return null
    }
    for (var i = 0; i < windows.length; i++) {
      var ipc = windows[i].lastIpcObject
      if (Number(ipc.fullscreen) >= 2 && ipc.mapped !== false && ipc.hidden !== true)
        return windows[i]
    }
    return null
  }

  // Quickshell's cached IPC details need refreshing when fullscreen changes.
  // Debounce compositor events; no timer runs while the desktop is idle.
  Connections {
    target: Hyprland
    function onRawEvent(event) {
      if (/^(fullscreen|workspacev2|focusedmon|activespecial|movewindowv2|openwindow|closewindow|configreloaded)$/.test(event.name))
        refresh.restart()
    }
  }
  Timer {
    id: refresh
    interval: 60
    onTriggered: {
      Hyprland.refreshMonitors()
      Hyprland.refreshWorkspaces()
      Hyprland.refreshToplevels()
    }
  }
  Component.onCompleted: refresh.start()

  Variants {
    model: Quickshell.screens
    PanelWindow {
      id: frame
      required property var modelData
      screen: modelData
      readonly property var monitor: Hyprland.monitorFor(modelData)
      readonly property var fullscreenWindow: root.fullWindow(monitor)
      visible: fullscreenWindow !== null
      anchors { top: true; bottom: true; left: true; right: true }
      color: "transparent"
      exclusionMode: ExclusionMode.Ignore
      WlrLayershell.namespace: "gdiab-fullscreen-border"
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      mask: Region {}

      Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.color: root.cueColor
        border.width: root.cueWidth
      }
    }
  }

  IpcHandler {
    target: "gdiab.fullscreen-border"
    function state(): string {
      var monitors = Hyprland.monitors.values
      var visible = []
      for (var i = 0; i < monitors.length; i++) {
        if (root.fullWindow(monitors[i])) visible.push(monitors[i].name)
      }
      return JSON.stringify({color: String(root.cueColor), width: root.cueWidth, monitors: visible})
    }
  }
}
