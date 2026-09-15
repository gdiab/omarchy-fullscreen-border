-- Persistent fullscreen cue. Re-evaluated on reload, including theme changes.
local theme = (os.getenv("HOME") or "") .. "/.local/state/omarchy/current/theme/colors.toml"
local palette = {}
local file = io.open(theme, "r")
if file then
  for line in file:lines() do
    local key, hex = line:match('^%s*([%w_]+)%s*=%s*"#(%x%x%x%x%x%x)"')
    if key then palette[key] = hex end
  end
  file:close()
end

local function rgb(hex)
  return {tonumber(hex:sub(1, 2), 16) / 255,
          tonumber(hex:sub(3, 4), 16) / 255,
          tonumber(hex:sub(5, 6), 16) / 255}
end
local function distance(a, b)
  return math.sqrt((a[1]-b[1])^2 + (a[2]-b[2])^2 + (a[3]-b[3])^2)
end
local function luminance(c)
  local function linear(x) return x <= 0.04045 and x / 12.92 or ((x + 0.055) / 1.055)^2.4 end
  return 0.2126*linear(c[1]) + 0.7152*linear(c[2]) + 0.0722*linear(c[3])
end
local normal = {}
for _, option in ipairs({"general.col.active_border", "general.col.inactive_border"}) do
  for _, value in ipairs(hl.get_config(option).colors) do
    local hex = value:match("^0x%x%x(%x%x%x%x%x%x)$")
    if hex then table.insert(normal, rgb(hex)) end
  end
end
local background = luminance(rgb(palette.background or "101315"))
local function suitability(hex)
  local c, separation = rgb(hex), 2
  for _, ordinary in ipairs(normal) do separation = math.min(separation, distance(c, ordinary)) end
  local light = luminance(c)
  local contrast = (math.max(light, background)+0.05)/(math.min(light, background)+0.05)
  return separation, contrast
end

-- Prefer a secondary color already in the theme; skip colors too close to
-- either ordinary border (including every stop of an active gradient).
local selected
for _, role in ipairs({"blue", "magenta", "yellow", "cyan", "orange", "red", "green",
                        "bright_blue", "bright_magenta", "bright_yellow"}) do
  local hex = palette[role]
  if hex then
    local separation, contrast = suitability(hex)
    if separation >= 0.40 and contrast >= 3 then selected = hex; break end
  end
end
-- Monochrome or unusual themes: choose the most distinct readable fallback.
if not selected then
  local best = -1
  for _, hex in ipairs({"829dd4", "c58cce", "d4b56a", "65b8b0", "bd5379", "4a69b0"}) do
    local separation, contrast = suitability(hex)
    local score = separation * math.min(contrast / 3, 1)
    if score > best then selected, best = hex, score end
  end
end

hl.window_rule({
  name = "theme-maximized-border",
  match = {fullscreen_state_internal = "1"},
  border_size = 3,
  border_color = "rgb(" .. selected .. ") rgb(" .. selected .. ")",
})

-- Keep Yoohoo's attention pulse, but within the fullscreen color family so
-- an unfocused maximized window never looks like an ordinary tiled window.
hl.window_rule({
  name = "theme-maximized-attention-border",
  match = {fullscreen_state_internal = "1", tag = "window-attention"},
  border_size = 5,
  border_color = "rgb(" .. selected .. ") rgb(" .. selected .. ")",
})
local pulse = rgb(selected)
local endpoint = background < 0.5 and 1 or 0
for i = 1, 3 do pulse[i] = math.floor((pulse[i] * 0.65 + endpoint * 0.35) * 255 + 0.5) end
local pulse_hex = string.format("%02x%02x%02x", pulse[1], pulse[2], pulse[3])
hl.window_rule({
  name = "theme-maximized-attention-pulse",
  match = {fullscreen_state_internal = "1", tag = "window-attention-pulse"},
  border_size = 5,
  border_color = "rgb(" .. pulse_hex .. ") rgb(" .. pulse_hex .. ")",
})

-- Share the exact same color with the true-fullscreen overlay. Only replace
-- the file when its content changes, so ordinary reloads do not churn it.
local path = (os.getenv("HOME") or "") .. "/.local/state/omarchy/fullscreen-border.json"
local content = '{"color":"#' .. selected .. '","width":3}\n'
local prior = io.open(path, "r")
local old = prior and prior:read("*a") or nil
if prior then prior:close() end
if old ~= content then
  local output = assert(io.open(path .. ".tmp", "w"))
  output:write(content)
  output:close()
  assert(os.rename(path .. ".tmp", path))
end
